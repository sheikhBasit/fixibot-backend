# from typing import List
# from bson import ObjectId
# from fastapi import HTTPException
# from pymongo import DESCENDING
# from models.vehicle import VehicleOut, VehicleSearch, VehicleUpdate, VehicleWithOwnerOut
# from models.user import UserOut
# from utils.py_object import PyObjectId
# from database import db
# from utils.time import utc_now
# import logging

# logger = logging.getLogger("vehicle_service")


# class VehicleService:
#     @staticmethod
#     async def create_vehicle(data: dict) -> VehicleOut:
#         """Create a new vehicle record."""
#         try:
#             result = await db.vehicles_collection.insert_one(data)
#             vehicle = await db.vehicles_collection.find_one({"_id": result.inserted_id})
#             logger.info(
#                 "Vehicle created",
#                 extra={
#                     "vehicle_id": str(vehicle["_id"]),
#                     "user_id": str(vehicle["user_id"]),
#                     "category": vehicle.get("category")
#                 }
#             )
#             return VehicleOut(**vehicle)
#         except Exception as e:
#             logger.error(f"Error creating vehicle: {e}")
#             raise HTTPException(status_code=500, detail="Error creating vehicle")

#     @staticmethod
#     async def admin_get_all_vehicles_with_owner(
#         skip: int = 0,
#         limit: int = 100,
#         sort_by: str = "created_at",
#         sort_order: str = "desc"
#     ) -> List[VehicleWithOwnerOut]:
#         """Admin: Get all vehicles with owner info."""
#         try:
#             sort_direction = DESCENDING if sort_order == "desc" else 1
#             vehicles_cursor = db.vehicles_collection.find({}) \
#                 .sort(sort_by, sort_direction) \
#                 .skip(skip).limit(limit)
#             vehicles = await vehicles_cursor.to_list(length=limit)
#             user_ids = list({v["user_id"] for v in vehicles if v.get("user_id")})
#             users = {
#                 u["_id"]: u
#                 for u in await db.users_collection.find({"_id": {"$in": user_ids}}).to_list(length=len(user_ids))
#             }
#             result = []
#             for v in vehicles:
#                 owner = users.get(v["user_id"])
#                 if owner and isinstance(owner.get("_id"), ObjectId):
#                     owner = {**owner, "_id": str(owner["_id"])}
#                 v["owner"] = UserOut(**owner) if owner else None
#                 result.append(VehicleWithOwnerOut(**v))
#             logger.info(f"Admin retrieved {len(result)} vehicles with owner info")
#             return result
#         except Exception as e:
#             logger.error(f"Admin vehicle retrieval with owner failed: {e}")
#             raise HTTPException(status_code=500, detail="Error retrieving vehicles with owner info")

#     @staticmethod
#     async def admin_get_vehicle_with_owner(vehicle_id: str) -> VehicleWithOwnerOut:
#         """Admin: Get a single vehicle with owner info."""
#         try:
#             vehicle = await db.vehicles_collection.find_one({"_id": ObjectId(vehicle_id)})
#             if not vehicle:
#                 raise HTTPException(status_code=404, detail="Vehicle not found")
#             owner = await db.users_collection.find_one({"_id": vehicle["user_id"]})
#             if owner and isinstance(owner.get("_id"), ObjectId):
#                 owner = {**owner, "_id": str(owner["_id"])}
#             vehicle["owner"] = UserOut(**owner) if owner else None
#             return VehicleWithOwnerOut(**vehicle)
#         except Exception as e:
#             logger.error(f"Admin get vehicle with owner failed: {e}")
#             raise HTTPException(status_code=500, detail="Error retrieving vehicle with owner info")

#     @staticmethod
#     async def get_by_id(vehicle_id: str, user_id: PyObjectId) -> VehicleOut:
#         """Get a vehicle by ID, ensuring user ownership."""
#         try:
#             vehicle = await db.vehicles_collection.find_one({
#                 "_id": ObjectId(vehicle_id),
#                 "user_id": user_id
#             })
#             if not vehicle:
#                 raise HTTPException(status_code=404, detail="Vehicle not found")
#             return VehicleOut(**vehicle)
#         except Exception as e:
#             logger.error(f"Failed to get vehicle {vehicle_id}: {e}")
#             raise

#     @staticmethod
#     async def update_vehicle(vehicle_id: str, user_id: PyObjectId, update: VehicleUpdate) -> VehicleOut:
#         """Update a vehicle record."""
#         try:
#             update_data = update.model_dump(exclude_unset=True, by_alias=True)
#             update_data["updated_at"] = utc_now()

#             result = await db.vehicles_collection.update_one(
#                 {"_id": ObjectId(vehicle_id), "user_id": user_id},
#                 {"$set": update_data}
#             )

#             if result.modified_count == 0:
#                 raise HTTPException(status_code=400, detail="No changes made")

#             updated = await db.vehicles_collection.find_one({"_id": ObjectId(vehicle_id)})
#             logger.info(f"Vehicle {vehicle_id} updated")
#             return VehicleOut(**updated)
#         except Exception as e:
#             logger.error(f"Error updating vehicle {vehicle_id}: {e}")
#             raise

#     @staticmethod
#     async def delete_vehicle(vehicle_id: str, user_id: PyObjectId):
#         """Delete a vehicle record permanently."""
#         try:
#             result = await db.vehicles_collection.delete_one({
#                 "_id": ObjectId(vehicle_id),
#                 "user_id": user_id
#             })
#             if result.deleted_count == 1:
#                 logger.info(f"Vehicle {vehicle_id} deleted")
#                 return {"message": "Vehicle deleted successfully"}
#             raise HTTPException(status_code=404, detail="Vehicle not found")
#         except Exception as e:
#             logger.error(f"Error deleting vehicle {vehicle_id}: {e}")
#             raise

#     @staticmethod
#     async def search_vehicles(
#         search: VehicleSearch,
#         user_id: PyObjectId,
#         skip: int = 0,
#         limit: int = 10,
#         sort_by: str = "created_at",
#         sort_order: str = "desc",
#         is_active: bool = None
#     ) -> List[VehicleOut]:
#         """Search vehicles with advanced filtering."""
#         try:
#             query = {"user_id": user_id}

#             # Brand search (case-insensitive)
#             if search.brand:
#                 query["brand"] = {"$regex": search.brand, "$options": "i"}
            
#             # Model search (case-insensitive)
#             if search.model:
#                 query["model"] = {"$regex": search.model, "$options": "i"}
            
#             # Category filter
#             if search.category:
#                 query["category"] = search.category
            
#             # Sub-type filter
#             if search.sub_type:
#                 query["sub_type"] = search.sub_type
            
#             # Fuel type filter
#             if search.fuel_type:
#                 query["fuel_type"] = search.fuel_type
            
#             # Transmission filter
#             if search.transmission:
#                 query["transmission"] = search.transmission
            
#             # Primary vehicle filter
#             if search.is_primary is not None:
#                 query["is_primary"] = search.is_primary
            
#             # Active status filter
#             if search.is_active is not None:
#                 query["is_active"] = search.is_active
            
#             # Year range filter
#             if search.year_from or search.year_to:
#                 query["year"] = {}
#                 if search.year_from:
#                     query["year"]["$gte"] = search.year_from
#                 if search.year_to:
#                     query["year"]["$lte"] = search.year_to
            
#             # Mileage range filter
#             if search.mileage_min or search.mileage_max:
#                 query["mileage_km"] = {}
#                 if search.mileage_min:
#                     query["mileage_km"]["$gte"] = search.mileage_min
#                 if search.mileage_max:
#                     query["mileage_km"]["$lte"] = search.mileage_max

#             sort_direction = DESCENDING if sort_order == "desc" else 1

#             vehicles_cursor = db.vehicles_collection.find(query)\
#                 .sort(sort_by, sort_direction)\
#                 .skip(skip).limit(limit)

#             vehicles = await vehicles_cursor.to_list(length=limit)
#             logger.info(f"Search returned {len(vehicles)} vehicles for user {user_id}")
#             return [VehicleOut(**v) for v in vehicles]

#         except Exception as e:
#             logger.error(f"Vehicle search failed for user {user_id}: {e}")
#             raise HTTPException(status_code=500, detail="Error searching vehicles")

#     @staticmethod
#     async def get_all_vehicles(
#         skip: int = 0,
#         limit: int = 100,
#         sort_by: str = "created_at",
#         sort_order: str = "desc"
#     ) -> List[VehicleOut]:
#         """Get all vehicles in the system (admin only)."""
#         try:
#             sort_direction = DESCENDING if sort_order == "desc" else 1

#             vehicles_cursor = db.vehicles_collection.find({})\
#                 .sort(sort_by, sort_direction)\
#                 .skip(skip).limit(limit)

#             vehicles = await vehicles_cursor.to_list(length=limit)
#             logger.info(f"Admin retrieved {len(vehicles)} vehicles")
#             return [VehicleOut(**v) for v in vehicles]

#         except Exception as e:
#             logger.error(f"Admin vehicle retrieval failed: {e}")
#             raise HTTPException(status_code=500, detail="Error retrieving vehicles")

#     @staticmethod
#     async def get_vehicles_by_category(
#         user_id: PyObjectId,
#         category: str,
#         skip: int = 0,
#         limit: int = 10
#     ) -> List[VehicleOut]:
#         """Get vehicles filtered by category (motorcycle or car)."""
#         try:
#             query = {"user_id": user_id, "category": category}
#             vehicles_cursor = db.vehicles_collection.find(query)\
#                 .sort("created_at", DESCENDING)\
#                 .skip(skip).limit(limit)
#             vehicles = await vehicles_cursor.to_list(length=limit)
#             logger.info(f"Retrieved {len(vehicles)} vehicles in category {category} for user {user_id}")
#             return [VehicleOut(**v) for v in vehicles]
#         except Exception as e:
#             logger.error(f"Failed to get vehicles by category: {e}")
#             raise HTTPException(status_code=500, detail="Error retrieving vehicles by category")

#     @staticmethod
#     async def get_vehicles_by_fuel_type(
#         user_id: PyObjectId,
#         fuel_type: str,
#         skip: int = 0,
#         limit: int = 10
#     ) -> List[VehicleOut]:
#         """Get vehicles filtered by fuel type."""
#         try:
#             query = {"user_id": user_id, "fuel_type": fuel_type}
#             vehicles_cursor = db.vehicles_collection.find(query)\
#                 .sort("created_at", DESCENDING)\
#                 .skip(skip).limit(limit)
#             vehicles = await vehicles_cursor.to_list(length=limit)
#             logger.info(f"Retrieved {len(vehicles)} vehicles with fuel type {fuel_type} for user {user_id}")
#             return [VehicleOut(**v) for v in vehicles]
#         except Exception as e:
#             logger.error(f"Failed to get vehicles by fuel type: {e}")
#             raise HTTPException(status_code=500, detail="Error retrieving vehicles by fuel type")

#     @staticmethod
#     async def get_vehicles_by_transmission(
#         user_id: PyObjectId,
#         transmission: str,
#         skip: int = 0,
#         limit: int = 10
#     ) -> List[VehicleOut]:
#         """Get vehicles filtered by transmission type."""
#         try:
#             query = {"user_id": user_id, "transmission": transmission}
#             vehicles_cursor = db.vehicles_collection.find(query)\
#                 .sort("created_at", DESCENDING)\
#                 .skip(skip).limit(limit)
#             vehicles = await vehicles_cursor.to_list(length=limit)
#             logger.info(f"Retrieved {len(vehicles)} vehicles with {transmission} transmission for user {user_id}")
#             return [VehicleOut(**v) for v in vehicles]
#         except Exception as e:
#             logger.error(f"Failed to get vehicles by transmission: {e}")
#             raise HTTPException(status_code=500, detail="Error retrieving vehicles by transmission")




from typing import List
from bson import ObjectId
from fastapi import HTTPException
from pymongo import DESCENDING
from models.vehicle import VehicleOut, VehicleSearch, VehicleUpdate, VehicleWithOwnerOut
from models.user import UserOut
from utils.py_object import PyObjectId
from database import db
from utils.time import utc_now
import logging

logger = logging.getLogger("vehicle_service")


class VehicleService:
    @staticmethod
    async def create_vehicle(data: dict) -> VehicleOut:
        """Create a new vehicle record."""
        try:
            result = await db.vehicles_collection.insert_one(data)
            vehicle = await db.vehicles_collection.find_one({"_id": result.inserted_id})
            
            # Convert ObjectId to string for Pydantic validation
            if vehicle and "_id" in vehicle and isinstance(vehicle["_id"], ObjectId):
                vehicle["_id"] = str(vehicle["_id"])
            if vehicle and "user_id" in vehicle and isinstance(vehicle["user_id"], ObjectId):
                vehicle["user_id"] = str(vehicle["user_id"])
            
            logger.info(
                "Vehicle created",
                extra={
                    "vehicle_id": str(vehicle["_id"]),
                    "user_id": str(vehicle["user_id"]),
                    "category": vehicle.get("category")
                }
            )
            return VehicleOut(**vehicle)
        except Exception as e:
            logger.error(f"Error creating vehicle: {e}")
            raise HTTPException(status_code=500, detail="Error creating vehicle")

    @staticmethod
    async def admin_get_all_vehicles_with_owner(
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> List[VehicleWithOwnerOut]:
        """Admin: Get all vehicles with owner info."""
        try:
            sort_direction = DESCENDING if sort_order == "desc" else 1
            vehicles_cursor = db.vehicles_collection.find({}) \
                .sort(sort_by, sort_direction) \
                .skip(skip).limit(limit)
            vehicles = await vehicles_cursor.to_list(length=limit)
            
            # Convert ObjectIds to strings
            for vehicle in vehicles:
                if "_id" in vehicle and isinstance(vehicle["_id"], ObjectId):
                    vehicle["_id"] = str(vehicle["_id"])
                if "user_id" in vehicle and isinstance(vehicle["user_id"], ObjectId):
                    vehicle["user_id"] = str(vehicle["user_id"])
            
            user_ids = list({v["user_id"] for v in vehicles if v.get("user_id")})
            users = {
                u["_id"]: u
                for u in await db.users_collection.find({"_id": {"$in": user_ids}}).to_list(length=len(user_ids))
            }
            
            result = []
            for v in vehicles:
                owner = users.get(v["user_id"])
                if owner and isinstance(owner.get("_id"), ObjectId):
                    owner = {**owner, "_id": str(owner["_id"])}
                v["owner"] = UserOut(**owner) if owner else None
                result.append(VehicleWithOwnerOut(**v))
                
            logger.info(f"Admin retrieved {len(result)} vehicles with owner info")
            return result
        except Exception as e:
            logger.error(f"Admin vehicle retrieval with owner failed: {e}")
            raise HTTPException(status_code=500, detail="Error retrieving vehicles with owner info")

    @staticmethod
    async def admin_get_vehicle_with_owner(vehicle_id: str) -> VehicleWithOwnerOut:
        """Admin: Get a single vehicle with owner info."""
        try:
            vehicle = await db.vehicles_collection.find_one({"_id": ObjectId(vehicle_id)})
            if not vehicle:
                raise HTTPException(status_code=404, detail="Vehicle not found")
            
            # Convert ObjectId to string
            if "_id" in vehicle and isinstance(vehicle["_id"], ObjectId):
                vehicle["_id"] = str(vehicle["_id"])
            if "user_id" in vehicle and isinstance(vehicle["user_id"], ObjectId):
                vehicle["user_id"] = str(vehicle["user_id"])
            
            owner = await db.users_collection.find_one({"_id": ObjectId(vehicle["user_id"])})
            if owner and isinstance(owner.get("_id"), ObjectId):
                owner = {**owner, "_id": str(owner["_id"])}
            vehicle["owner"] = UserOut(**owner) if owner else None
            
            return VehicleWithOwnerOut(**vehicle)
        except Exception as e:
            logger.error(f"Admin get vehicle with owner failed: {e}")
            raise HTTPException(status_code=500, detail="Error retrieving vehicle with owner info")

    @staticmethod
    async def get_by_id(vehicle_id: str, user_id: PyObjectId) -> VehicleOut:
        """Get a vehicle by ID, ensuring user ownership."""
        try:
            # Convert string user_id to ObjectId if needed
            if isinstance(user_id, str):
                try:
                    user_id = ObjectId(user_id)
                except:
                    raise HTTPException(status_code=400, detail="Invalid user ID format")
            
            vehicle = await db.vehicles_collection.find_one({
                "_id": ObjectId(vehicle_id),
                "user_id": user_id
            })
            if not vehicle:
                raise HTTPException(status_code=404, detail="Vehicle not found")
            
            # Convert ObjectId to string
            if "_id" in vehicle and isinstance(vehicle["_id"], ObjectId):
                vehicle["_id"] = str(vehicle["_id"])
            if "user_id" in vehicle and isinstance(vehicle["user_id"], ObjectId):
                vehicle["user_id"] = str(vehicle["user_id"])
                
            return VehicleOut(**vehicle)
        except Exception as e:
            logger.error(f"Failed to get vehicle {vehicle_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Error retrieving vehicle: {str(e)}")

    @staticmethod
    async def update_vehicle(vehicle_id: str, user_id: PyObjectId, update: VehicleUpdate) -> VehicleOut:
        """Update a vehicle record."""
        try:
            # Convert string user_id to ObjectId if needed
            if isinstance(user_id, str):
                try:
                    user_id = ObjectId(user_id)
                except:
                    raise HTTPException(status_code=400, detail="Invalid user ID format")
            
            update_data = update.model_dump(exclude_unset=True, by_alias=True)
            update_data["updated_at"] = utc_now()

            result = await db.vehicles_collection.update_one(
                {"_id": ObjectId(vehicle_id), "user_id": user_id},
                {"$set": update_data}
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=400, detail="No changes made")

            updated = await db.vehicles_collection.find_one({"_id": ObjectId(vehicle_id)})
            
            # Convert ObjectId to string
            if updated and "_id" in updated and isinstance(updated["_id"], ObjectId):
                updated["_id"] = str(updated["_id"])
            if updated and "user_id" in updated and isinstance(updated["user_id"], ObjectId):
                updated["user_id"] = str(updated["user_id"])
                
            logger.info(f"Vehicle {vehicle_id} updated")
            return VehicleOut(**updated)
        except Exception as e:
            logger.error(f"Error updating vehicle {vehicle_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Error updating vehicle: {str(e)}")

    @staticmethod
    async def delete_vehicle(vehicle_id: str, user_id: PyObjectId):
        """Delete a vehicle record permanently."""
        try:
            # Convert string user_id to ObjectId if needed
            if isinstance(user_id, str):
                try:
                    user_id = ObjectId(user_id)
                except:
                    raise HTTPException(status_code=400, detail="Invalid user ID format")
            
            result = await db.vehicles_collection.delete_one({
                "_id": ObjectId(vehicle_id),
                "user_id": user_id
            })
            if result.deleted_count == 1:
                logger.info(f"Vehicle {vehicle_id} deleted")
                return {"message": "Vehicle deleted successfully"}
            raise HTTPException(status_code=404, detail="Vehicle not found")
        except Exception as e:
            logger.error(f"Error deleting vehicle {vehicle_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Error deleting vehicle: {str(e)}")

    @staticmethod
    async def search_vehicles(
        search: VehicleSearch,
        user_id: PyObjectId,
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> List[VehicleOut]:
        """Search vehicles with advanced filtering."""
        try:
            print(f"🔍 Searching vehicles for user: {user_id}")
            
            # Convert string user_id to ObjectId if needed
            if isinstance(user_id, str):
                try:
                    user_id = ObjectId(user_id)
                except:
                    raise HTTPException(status_code=400, detail="Invalid user ID format")
            
            # Build query filter
            query_filter = {"user_id": user_id}
            
            # Add optional filters
            if search.brand:
                query_filter["brand"] = {"$regex": search.brand, "$options": "i"}
            if search.model:
                query_filter["model"] = {"$regex": search.model, "$options": "i"}
            if search.category:
                query_filter["category"] = search.category
            if search.sub_type:
                query_filter["sub_type"] = search.sub_type
            if search.fuel_type:
                query_filter["fuel_type"] = search.fuel_type
            if search.transmission:
                query_filter["transmission"] = search.transmission
            if search.year_from is not None or search.year_to is not None:
                query_filter["year"] = {}
                if search.year_from is not None:
                    query_filter["year"]["$gte"] = search.year_from
                if search.year_to is not None:
                    query_filter["year"]["$lte"] = search.year_to
            if search.mileage_min is not None or search.mileage_max is not None:
                query_filter["mileage_km"] = {}
                if search.mileage_min is not None:
                    query_filter["mileage_km"]["$gte"] = search.mileage_min
                if search.mileage_max is not None:
                    query_filter["mileage_km"]["$lte"] = search.mileage_max
            if search.is_active is not None:
                query_filter["is_active"] = search.is_active
            if search.is_primary is not None:
                query_filter["is_primary"] = search.is_primary
            
            print(f"🔍 Query filter: {query_filter}")
            
            # Build sort
            sort_direction = DESCENDING if sort_order == "desc" else 1
            sort_criteria = [(sort_by, sort_direction)]
            
            # Execute query
            cursor = db.vehicles_collection.find(query_filter).skip(skip).limit(limit).sort(sort_criteria)
            vehicles = await cursor.to_list(length=limit)
            
            print(f"✅ Found {len(vehicles)} vehicles")
            
            # Convert ObjectId to string and validate
            validated_vehicles = []
            for vehicle in vehicles:
                # Convert ObjectId to string
                if "_id" in vehicle and isinstance(vehicle["_id"], ObjectId):
                    vehicle["_id"] = str(vehicle["_id"])
                if "user_id" in vehicle and isinstance(vehicle["user_id"], ObjectId):
                    vehicle["user_id"] = str(vehicle["user_id"])
                
                # Validate against Pydantic model
                try:
                    validated_vehicle = VehicleOut(**vehicle)
                    validated_vehicles.append(validated_vehicle)
                except Exception as e:
                    print(f"❌ Validation error for vehicle {vehicle.get('_id')}: {e}")
                    logger.error(f"Validation error for vehicle {vehicle.get('_id')}: {e}")
                    continue
            
            logger.info(f"Search returned {len(validated_vehicles)} vehicles for user {user_id}")
            return validated_vehicles
            
        except Exception as e:
            logger.error(f"Vehicle search failed for user {user_id}: {e}")
            print(f"❌ Error in search_vehicles: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error searching vehicles: {str(e)}")

    @staticmethod
    async def get_all_vehicles(
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> List[VehicleOut]:
        """Get all vehicles in the system (admin only)."""
        try:
            sort_direction = DESCENDING if sort_order == "desc" else 1

            vehicles_cursor = db.vehicles_collection.find({})\
                .sort(sort_by, sort_direction)\
                .skip(skip).limit(limit)

            vehicles = await vehicles_cursor.to_list(length=limit)
            
            # Convert ObjectIds to strings
            for vehicle in vehicles:
                if "_id" in vehicle and isinstance(vehicle["_id"], ObjectId):
                    vehicle["_id"] = str(vehicle["_id"])
                if "user_id" in vehicle and isinstance(vehicle["user_id"], ObjectId):
                    vehicle["user_id"] = str(vehicle["user_id"])
            
            logger.info(f"Admin retrieved {len(vehicles)} vehicles")
            return [VehicleOut(**v) for v in vehicles]

        except Exception as e:
            logger.error(f"Admin vehicle retrieval failed: {e}")
            raise HTTPException(status_code=500, detail="Error retrieving vehicles")

    @staticmethod
    async def get_vehicles_by_category(
        user_id: PyObjectId,
        category: str,
        skip: int = 0,
        limit: int = 10
    ) -> List[VehicleOut]:
        """Get vehicles filtered by category (motorcycle or car)."""
        try:
            # Convert string user_id to ObjectId if needed
            if isinstance(user_id, str):
                try:
                    user_id = ObjectId(user_id)
                except:
                    raise HTTPException(status_code=400, detail="Invalid user ID format")
            
            query = {"user_id": user_id, "category": category}
            vehicles_cursor = db.vehicles_collection.find(query)\
                .sort("created_at", DESCENDING)\
                .skip(skip).limit(limit)
            vehicles = await vehicles_cursor.to_list(length=limit)
            
            # Convert ObjectIds to strings
            for vehicle in vehicles:
                if "_id" in vehicle and isinstance(vehicle["_id"], ObjectId):
                    vehicle["_id"] = str(vehicle["_id"])
                if "user_id" in vehicle and isinstance(vehicle["user_id"], ObjectId):
                    vehicle["user_id"] = str(vehicle["user_id"])
            
            logger.info(f"Retrieved {len(vehicles)} vehicles in category {category} for user {user_id}")
            return [VehicleOut(**v) for v in vehicles]
        except Exception as e:
            logger.error(f"Failed to get vehicles by category: {e}")
            raise HTTPException(status_code=500, detail="Error retrieving vehicles by category")

    @staticmethod
    async def get_vehicles_by_fuel_type(
        user_id: PyObjectId,
        fuel_type: str,
        skip: int = 0,
        limit: int = 10
    ) -> List[VehicleOut]:
        """Get vehicles filtered by fuel type."""
        try:
            # Convert string user_id to ObjectId if needed
            if isinstance(user_id, str):
                try:
                    user_id = ObjectId(user_id)
                except:
                    raise HTTPException(status_code=400, detail="Invalid user ID format")
            
            query = {"user_id": user_id, "fuel_type": fuel_type}
            vehicles_cursor = db.vehicles_collection.find(query)\
                .sort("created_at", DESCENDING)\
                .skip(skip).limit(limit)
            vehicles = await vehicles_cursor.to_list(length=limit)
            
            # Convert ObjectIds to strings
            for vehicle in vehicles:
                if "_id" in vehicle and isinstance(vehicle["_id"], ObjectId):
                    vehicle["_id"] = str(vehicle["_id"])
                if "user_id" in vehicle and isinstance(vehicle["user_id"], ObjectId):
                    vehicle["user_id"] = str(vehicle["user_id"])
            
            logger.info(f"Retrieved {len(vehicles)} vehicles with fuel type {fuel_type} for user {user_id}")
            return [VehicleOut(**v) for v in vehicles]
        except Exception as e:
            logger.error(f"Failed to get vehicles by fuel type: {e}")
            raise HTTPException(status_code=500, detail="Error retrieving vehicles by fuel type")

    @staticmethod
    async def get_vehicles_by_transmission(
        user_id: PyObjectId,
        transmission: str,
        skip: int = 0,
        limit: int = 10
    ) -> List[VehicleOut]:
        """Get vehicles filtered by transmission type."""
        try:
            # Convert string user_id to ObjectId if needed
            if isinstance(user_id, str):
                try:
                    user_id = ObjectId(user_id)
                except:
                    raise HTTPException(status_code=400, detail="Invalid user ID format")
            
            query = {"user_id": user_id, "transmission": transmission}
            vehicles_cursor = db.vehicles_collection.find(query)\
                .sort("created_at", DESCENDING)\
                .skip(skip).limit(limit)
            vehicles = await vehicles_cursor.to_list(length=limit)
            
            # Convert ObjectIds to strings
            for vehicle in vehicles:
                if "_id" in vehicle and isinstance(vehicle["_id"], ObjectId):
                    vehicle["_id"] = str(vehicle["_id"])
                if "user_id" in vehicle and isinstance(vehicle["user_id"], ObjectId):
                    vehicle["user_id"] = str(vehicle["user_id"])
            
            logger.info(f"Retrieved {len(vehicles)} vehicles with {transmission} transmission for user {user_id}")
            return [VehicleOut(**v) for v in vehicles]
        except Exception as e:
            logger.error(f"Failed to get vehicles by transmission: {e}")
            raise HTTPException(status_code=500, detail="Error retrieving vehicles by transmission")