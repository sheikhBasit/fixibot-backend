from datetime import datetime, timezone
import re

from bson import ObjectId
import pymongo
from models.mechanic import ExpertiseEnum, MechanicIn, MechanicOut, MechanicUpdate, WorkingHours
from database import db
from utils.py_object import PyObjectId

from fastapi import HTTPException, status
import logging
from typing import Optional, List
from utils.time import utc_now

logger = logging.getLogger("mechanic_services")

class MechanicService:

    @staticmethod
    async def delete_mechanic(mechanic_id: str) -> bool:
        """Delete a mechanic by ID (admin only)."""
        try:
            result = await db.mechanics_collection.delete_one({"_id": PyObjectId(mechanic_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting mechanic {mechanic_id}: {e}")
            return False
    @staticmethod
    async def create_mechanic(mechanic_data: MechanicIn) -> MechanicOut:
        """Create a new mechanic in the database."""
        try:
            # Check for existing mechanic with same CNIC, phone or email
            existing_query = {
                "$or": [
                    {"cnic": mechanic_data.cnic},
                    {"phone_number": mechanic_data.phone_number}
                ]
            }
            if mechanic_data.email:
                existing_query["$or"].append({"email": mechanic_data.email.lower()})

            existing_mechanic = await db.mechanics_collection.find_one(existing_query)
            if existing_mechanic:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Mechanic with this CNIC, phone or email already exists"
                )

            # Prepare mechanic document - ensure location is generated
            mechanic_dict = mechanic_data.model_dump(by_alias=True, exclude_none=True)
            mechanic_dict.update({
                "created_at": utc_now(),
                "updated_at": utc_now(),
                "is_verified": False,
                "is_available": True
            })

            # Ensure location field is properly set
            if "location" not in mechanic_dict:
                mechanic_dict["location"] = {
                    "type": "Point",
                    "coordinates": [mechanic_data.longitude, mechanic_data.latitude]
                }

            # Insert into database
            result = await db.mechanics_collection.insert_one(mechanic_dict)
            if not result.inserted_id:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create mechanic"
                )

            # Return created mechanic
            created_mechanic = await MechanicService.get_mechanic_by_id(str(result.inserted_id))
            return created_mechanic

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating mechanic: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error creating mechanic"
            )    

    @staticmethod
    async def get_mechanic_by_id(mechanic_id: str) -> MechanicOut:
        """Get mechanic by ID from database."""
        try:
            mechanic = await db.mechanics_collection.find_one({"_id": PyObjectId(mechanic_id)})
            if not mechanic:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Mechanic not found"
                )
            
            # Handle missing created_at field for existing documents
            if "created_at" not in mechanic:
                # Set a default created_at value (e.g., current time or a reasonable past date)
                mechanic["created_at"] = datetime.now(timezone.utc)
                # Optionally update the document in the database
                await db.mechanics_collection.update_one(
                    {"_id": PyObjectId(mechanic_id)},
                    {"$set": {"created_at": mechanic["created_at"]}}
                )
            
            return MechanicOut(**mechanic)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching mechanic by ID {mechanic_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error fetching mechanic"
            )

    @staticmethod
    async def get_mechanic_by_email_or_phone(
        email: Optional[str] = None,
        phone: Optional[str] = None
    ) -> Optional[MechanicOut]:
        """Get mechanic by email or phone number."""
        try:
            query = {}
            if email:
                query["email"] = email.lower()
            if phone:
                query["phone_number"] = phone

            if not query:
                return None

            mechanic = await db.mechanics_collection.find_one(query)
            return MechanicOut(**mechanic) if mechanic else None
        except Exception as e:
            logger.error(f"Error fetching mechanic by email/phone: {e}")
            return None


    @staticmethod
    async def update_mechanic(
        mechanic_id: str,
        update_data: 'MechanicUpdate'
    ) -> 'MechanicOut':
        """Update mechanic information with comprehensive validation and error handling."""
        try:
            # Validate mechanic ID format
            try:
                mechanic_oid = ObjectId(mechanic_id)
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid mechanic ID format"
                )

            # Get only the fields that were actually set in the update
            update_dict = update_data.model_dump(exclude_unset=True, exclude_none=True)
            
            # --- DEBUG: Print the incoming update data
            print(f"DEBUG: update_dict from Pydantic: {update_dict}")
            print(f"DEBUG: Mechanic ID: {update_data}")
            if not update_dict:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No update data provided"
                )

            # Get current mechanic data
            current_mechanic = await db.mechanics_collection.find_one({"_id": mechanic_oid})
            if not current_mechanic:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Mechanic not found"
                )

            # --- DEBUG: Print the existing mechanic data
            print(f"DEBUG: Current mechanic data from DB: {current_mechanic}")

            # Add update timestamp
            update_dict["updated_at"] = utc_now()
            
            # --- CORRECTED LOCATION UPDATE LOGIC ---
            latitude_provided = "latitude" in update_dict
            longitude_provided = "longitude" in update_dict
            
            if latitude_provided or longitude_provided:
                # Get existing location coordinates safely from the nested structure
                current_location_coords = current_mechanic.get("location", {}).get("coordinates", [None, None])
                current_longitude = current_location_coords[0]
                current_latitude = current_location_coords[1]
                
                # Use provided values, or fall back to existing values
                final_longitude = update_dict.get("longitude", current_longitude)
                final_latitude = update_dict.get("latitude", current_latitude)

                # --- DEBUG: Show the final coordinates to be saved
                print(f"DEBUG: Final Longitude: {final_longitude}, Final Latitude: {final_latitude}")

                if final_latitude is not None and final_longitude is not None:
                    # Update the location field with a new GeoJSON point
                    update_dict["location"] = {
                        "type": "Point",
                        "coordinates": [final_longitude, final_latitude]
                    }
                    # Remove individual coordinate fields to prevent duplication
                    update_dict.pop("latitude", None)
                    update_dict.pop("longitude", None)
                else:
                    # If incomplete coordinates, we should not update the location field
                    pass

            # Perform the database update
            try:
                result = await db.mechanics_collection.update_one(
                    {"_id": mechanic_oid},
                    {"$set": update_dict}
                )
            except Exception as db_error:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database error during update"
                )

            # Return updated mechanic data
            return await MechanicService.get_mechanic_by_id(mechanic_id)

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred: {str(e)}"
            )




    @staticmethod
    async def list_mechanics(
        skip: int = 0,
        limit: int = 100,
        verified: Optional[bool] = None,
        available: Optional[bool] = None,
        city: Optional[str] = None
    ) -> List[MechanicOut]:
        """List mechanics with optional filters."""
        try:
            # Build query
            query = {}
            if verified is not None:
                query["is_verified"] = verified
            if available is not None:
                query["is_available"] = available
            if city:
                query["city"] = city.lower()
            
            # Get mechanics with projection to ensure all required fields
            cursor = db.mechanics_collection.find(query).skip(skip).limit(limit)
            mechanics = await cursor.to_list(length=limit)
            
            # Handle missing created_at field for existing documents
            validated_mechanics = []
            for mechanic in mechanics:
                try:
                    # Add default created_at if missing
                    if "created_at" not in mechanic:
                        mechanic["created_at"] = datetime.now(timezone.utc)
                    
                    # Convert ObjectId to string for Pydantic validation
                    if "_id" in mechanic and isinstance(mechanic["_id"], ObjectId):
                        mechanic["_id"] = str(mechanic["_id"])
                    
                    # Validate and convert to MechanicOut
                    validated_mechanics.append(MechanicOut(**mechanic))
                except Exception as e:
                    logger.error(f"Error processing mechanic {mechanic.get('_id', 'unknown')}: {e}")
                    continue  # Skip invalid records but continue processing others
            
            return validated_mechanics
            
        except pymongo.errors.PyMongoError as mongo_error:
            logger.error(f"MongoDB error listing mechanics: {mongo_error}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service temporarily unavailable"
            )
        except Exception as e:
            logger.error(f"Unexpected error listing mechanics: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error retrieving mechanics"
            )

    @staticmethod
    async def search_mechanics(
        city: str,
        expertise: Optional[List[ExpertiseEnum]] = None,
        min_experience: int = 0,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        max_distance_km: float = 10
    ) -> List[MechanicOut]:
        """Search mechanics by location and expertise using MongoDB geospatial queries."""
        try:
            # Base query for verified and available mechanics
            query = {
                "city": city.lower(),
                "is_verified": True,
                "is_available": True,
                "years_of_experience": {"$gte": min_experience}
            }

            # Add expertise filter if provided
            if expertise:
                query["expertise"] = {"$all": expertise}

            # Add geospatial query if coordinates provided
            if latitude is not None and longitude is not None:
                query["location"] = {
                    "$near": {
                        "$geometry": {
                            "type": "Point",
                            "coordinates": [longitude, latitude]  # GeoJSON: [long, lat]
                        },
                        "$maxDistance": max_distance_km * 1000  # Convert km to meters
                    }
                }

            # Execute query - MongoDB handles spatial search efficiently
            cursor = db.mechanics_collection.find(query)
            mechanics = await cursor.to_list(length=100)

            # Handle missing fields
            validated_mechanics = []
            for mechanic in mechanics:
                fixed_mechanic = await MechanicService._fix_missing_fields(mechanic, str(mechanic["_id"]))
                validated_mechanics.append(MechanicOut(**fixed_mechanic))

            return validated_mechanics
            
        except Exception as e:
            logger.error(f"Error searching mechanics: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error searching mechanics"
            )
    
    @staticmethod
    async def create_geospatial_index():
        """Create 2dsphere index for location field."""
        try:
            # Check if index already exists
            existing_indexes = await db.mechanics_collection.index_information()
            if "location_2dsphere" not in existing_indexes:
                await db.mechanics_collection.create_index([("location", "2dsphere")])
                print("Created 2dsphere index on location field")
            else:
                print("2dsphere index already exists")
        except Exception as e:
            print(f"Error creating geospatial index: {e}")

    @staticmethod
    async def migrate_existing_to_geospatial():
        """Add location field to existing mechanics that don't have it."""
        try:
            # Find documents without location field
            query = {
                "location": {"$exists": False},
                "longitude": {"$exists": True},
                "latitude": {"$exists": True}
            }
            
            cursor = db.mechanics_collection.find(query)
            mechanics_to_update = await cursor.to_list(length=None)
            
            update_operations = []
            for mechanic in mechanics_to_update:
                update_operations.append((
                    {"_id": mechanic["_id"]},
                    {"$set": {
                        "location": {
                            "type": "Point",
                            "coordinates": [mechanic["longitude"], mechanic["latitude"]]
                        }
                    }}
                ))
            
            # Batch update
            if update_operations:
                for filter_query, update in update_operations:
                    await db.mechanics_collection.update_one(filter_query, update)
                
                print(f"Migrated {len(update_operations)} documents to include location field")
            else:
                print("No documents need migration")
                
        except Exception as e:
            print(f"Error during migration: {e}")

    @staticmethod
    async def _fix_missing_fields(mechanic_data: dict, mechanic_id: str = None) -> dict:
        """Fix missing required fields in mechanic data."""
        data = mechanic_data.copy()

        # Set default created_at if missing
        if "created_at" not in data:
            data["created_at"] = datetime.now(timezone.utc)
            if mechanic_id:
                await db.mechanics_collection.update_one(
                    {"_id": PyObjectId(mechanic_id)},
                    {"$set": {"created_at": data["created_at"]}}
                )

        # Set default updated_at if missing
        if "updated_at" not in data:
            data["updated_at"] = datetime.now(timezone.utc)
            if mechanic_id:
                await db.mechanics_collection.update_one(
                    {"_id": PyObjectId(mechanic_id)},
                    {"$set": {"updated_at": data["updated_at"]}}
                )

        # Add location field if missing but lat/long exist
        if ("location" not in data and 
            "longitude" in data and 
            "latitude" in data and 
            data["longitude"] is not None and 
            data["latitude"] is not None):
            
            data["location"] = {
                "type": "Point",
                "coordinates": [data["longitude"], data["latitude"]]
            }
            if mechanic_id:
                await db.mechanics_collection.update_one(
                    {"_id": PyObjectId(mechanic_id)},
                    {"$set": {"location": data["location"]}}
                )

        # Set default values for other required fields
        if "is_verified" not in data:
            data["is_verified"] = False
        if "is_available" not in data:
            data["is_available"] = True
        if "working_days" not in data:
            data["working_days"] = []

        return data

    @staticmethod
    async def verify_mechanic(mechanic_id: str, verify: bool = True) -> bool:
        """Verify or unverify a mechanic."""
        try:
            result = await db.mechanics_collection.update_one(
                {"_id": PyObjectId(mechanic_id)},
                {"$set": {"is_verified": verify, "updated_at": utc_now()}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error verifying mechanic {mechanic_id}: {e}")
            return False