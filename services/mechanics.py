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
        update_data: MechanicUpdate
    ) -> MechanicOut:
        """Update mechanic information with comprehensive validation and error handling."""
        try:
            # Validate mechanic ID format
            try:
                mechanic_oid = PyObjectId(mechanic_id)
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid mechanic ID format"
                )

            # Get only the fields that were actually set in the update
            update_dict = update_data.model_dump(exclude_unset=True, exclude_none=True)
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

            # Helper function to validate CNIC/image values
            def is_valid_image_value(value):
                """Check if a value represents a valid image URL/identifier."""
                if value is None:
                    return False
                if isinstance(value, str):
                    value = value.strip().lower()
                    # Reject empty strings and common placeholder values
                    if value in ["", "null", "undefined", "none", "empty", "n/a"]:
                        return False
                    # Basic URL validation (can be enhanced)
                    if value.startswith(('http://', 'https://', '/', 'data:')):
                        return True
                    # Allow other non-empty strings that might be file paths or identifiers
                    return len(value) > 0
                # Allow non-string values that might be valid (e.g., file objects in some contexts)
                return True

            # Check if trying to verify the mechanic
            # if update_dict.get("is_verified") is True:
            #     # Check both update data and existing data for valid CNIC images
            #     update_cnic_front = update_dict.get("cnic_front")
            #     update_cnic_back = update_dict.get("cnic_back")
            #     existing_cnic_front = current_mechanic.get("cnic_front")
            #     existing_cnic_back = current_mechanic.get("cnic_back")
                
            #     # Determine which CNIC images to use (update takes precedence over existing)
            #     # final_cnic_front = update_cnic_front if is_valid_image_value(update_cnic_front) else existing_cnic_front
            #     # final_cnic_back = update_cnic_back if is_valid_image_value(update_cnic_back) else existing_cnic_back
                
            #     # Validate that both CNIC images are present and valid
            #     # has_valid_cnic_front = is_valid_image_value(final_cnic_front)
            #     # has_valid_cnic_back = is_valid_image_value(final_cnic_back)
                
            #     # if not (has_valid_cnic_front and has_valid_cnic_back):
            #     #     missing_images = []
            #     #     if not has_valid_cnic_front:
            #     #         missing_images.append("CNIC front image")
            #     #     if not has_valid_cnic_back:
            #     #         missing_images.append("CNIC back image")
                    
            #     #     raise HTTPException(
            #     #         status_code=status.HTTP_400_BAD_REQUEST,
            #     #         detail=f"{' and '.join(missing_images)} are required for verification"
            #     #     )

            # Add update timestamp
            update_dict["updated_at"] = utc_now()

            # Handle location updates - regenerate GeoJSON point if lat/long are provided
            latitude_provided = "latitude" in update_dict
            longitude_provided = "longitude" in update_dict
            
            if latitude_provided or longitude_provided:
                # Use provided values or fall back to existing values
                final_latitude = update_dict.get("latitude", current_mechanic.get("latitude"))
                final_longitude = update_dict.get("longitude", current_mechanic.get("longitude"))
                
                if final_latitude is not None and final_longitude is not None:
                    update_dict["location"] = {
                        "type": "Point",
                        "coordinates": [final_longitude, final_latitude]
                    }
                    # Remove individual coordinate fields to avoid data duplication
                    if latitude_provided:
                        update_dict.pop("latitude", None)
                    if longitude_provided:
                        update_dict.pop("longitude", None)
                else:
                    # If incomplete coordinates provided, remove location to avoid invalid data
                    update_dict.pop("location", None)
                    if latitude_provided:
                        update_dict.pop("latitude", None)
                    if longitude_provided:
                        update_dict.pop("longitude", None)

            # Validate and check for conflicts with unique fields
            conflict_checks = {}
            
            # Email validation and conflict check
            if "email" in update_dict:
                email = update_dict["email"]
                if email and not re.match(r'^[^@]+@[^@]+\.[^@]+', email):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid email format"
                    )
                if email:  # Only check non-empty emails
                    conflict_checks["email"] = email.lower()
            
            # Phone number validation and conflict check
            if "phone_number" in update_dict:
                phone = update_dict["phone_number"]
                if phone and not re.match(r'^[\d\s\+\-\(\)]{7,15}$', phone):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid phone number format"
                    )
                if phone:  # Only check non-empty phone numbers
                    conflict_checks["phone_number"] = phone

            # CNIC validation
            if "cnic" in update_dict:
                cnic = update_dict["cnic"]
                if cnic and not re.match(r'^\d{5}-\d{7}-\d{1}$|^\d{13,15}$', cnic):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid CNIC format. Use 35202-1234567-1 or 3520212345671 format"
                    )
                if cnic:  # Only check non-empty CNIC
                    conflict_checks["cnic"] = cnic

            # Check for conflicts with other mechanics
            if conflict_checks:
                conflict_query = {"_id": {"$ne": mechanic_oid}}
                conflict_query.update({"$or": [{k: v} for k, v in conflict_checks.items()]})
                
                existing_conflict = await db.mechanics_collection.find_one(conflict_query)
                if existing_conflict:
                    conflicting_fields = []
                    for field, value in conflict_checks.items():
                        if existing_conflict.get(field) == value:
                            conflicting_fields.append(field)
                    
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"{', '.join(conflicting_fields)} already in use by another mechanic"
                    )

            # Handle expertise validation
            if "expertise" in update_dict:
                expertise = update_dict["expertise"]
                if expertise and not isinstance(expertise, list):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Expertise must be a list"
                    )
                if expertise and len(expertise) == 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="At least one expertise is required"
                    )

            # Handle working hours validation
            if "working_hours" in update_dict and update_dict["working_hours"]:
                try:
                    # Ensure working_hours is properly formatted
                    wh = update_dict["working_hours"]
                    if isinstance(wh, dict):
                        WorkingHours(**wh)  # Validate structure
                except ValueError as e:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid working hours: {str(e)}"
                    )

            # Perform the database update
            try:
                result = await db.mechanics_collection.update_one(
                    {"_id": mechanic_oid},
                    {"$set": update_dict}
                )
            except Exception as db_error:
                logger.error(f"Database update error for mechanic {mechanic_id}: {db_error}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database error during update"
                )

            if result.modified_count == 0:
                # Check if document still exists
                existing_doc = await db.mechanics_collection.find_one({"_id": mechanic_oid})
                if not existing_doc:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Mechanic not found during update"
                    )
                
                # Check if any fields would actually change
                would_change = False
                for field, new_value in update_dict.items():
                    if field == "updated_at":
                        continue  # Skip timestamp comparison
                    current_value = existing_doc.get(field)
                    if new_value != current_value:
                        would_change = True
                        break
                
                if would_change:
                    logger.warning(f"Update for mechanic {mechanic_id} resulted in 0 modifications but changes were expected")
                
                # Return current data regardless
                return await MechanicService.get_mechanic_by_id(mechanic_id)

            # Return updated mechanic data
            return await MechanicService.get_mechanic_by_id(mechanic_id)

        except HTTPException:
            # Re-raise known HTTP exceptions
            raise
        except pymongo.errors.PyMongoError as mongo_error:
            # Handle MongoDB-specific errors
            logger.error(f"MongoDB error updating mechanic {mechanic_id}: {mongo_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database operation failed"
            )
        except ValueError as ve:
            # Handle validation errors from Pydantic or custom validation
            logger.error(f"Validation error for mechanic {mechanic_id}: {ve}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation error: {str(ve)}"
            )
        except Exception as e:
            # Catch-all for any other errors
            logger.error(f"Unexpected error updating mechanic {mechanic_id}: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred during update"
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