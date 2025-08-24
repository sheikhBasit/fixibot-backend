# vehicle_service.py

from typing import List
from bson import ObjectId
from fastapi import HTTPException
from pymongo import DESCENDING
from models.vehicle import  VehicleOut, VehicleSearch, VehicleUpdate
from utils.py_object import PyObjectId

from database import db
from utils.time import utc_now
import logging

logger = logging.getLogger("vehicle_service")

class VehicleService:
    @staticmethod
    async def create_vehicle(data: dict) -> VehicleOut:
        try:
            result = await db.vehicles_collection.insert_one(data)
            vehicle = await db.vehicles_collection.find_one({"_id": result.inserted_id})
            logger.info("Vehicle created", extra={"vehicle_id": str(vehicle["_id"]), "user_id": str(vehicle["user_id"])})
            return VehicleOut(**vehicle)
        except Exception as e:
            logger.error(f"Error creating vehicle: {e}")
            raise HTTPException(status_code=500, detail="Error creating vehicle")

    @staticmethod
    async def get_by_id(vehicle_id: str, user_id: PyObjectId) -> VehicleOut:
        try:
            vehicle = await db.vehicles_collection.find_one({
                "_id": ObjectId(vehicle_id),
                "user_id": user_id
            })
            if not vehicle:
                raise HTTPException(status_code=404, detail="Vehicle not found")
            return VehicleOut(**vehicle)
        except Exception as e:
            logger.error(f"Failed to get vehicle {vehicle_id}: {e}")
            raise

    @staticmethod
    async def update_vehicle(vehicle_id: str, user_id: PyObjectId, update: VehicleUpdate) -> VehicleOut:
        try:
            update_data = update.model_dump(exclude_unset=True, by_alias=True)
            update_data["updated_at"] = utc_now()

            result = await db.vehicles_collection.update_one(
                {"_id": ObjectId(vehicle_id), "user_id": user_id},
                {"$set": update_data}
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=400, detail="No changes made")

            updated = await db.vehicles_collection.find_one({"_id": ObjectId(vehicle_id)})
            logger.info(f"Vehicle {vehicle_id} updated")
            return VehicleOut(**updated)
        except Exception as e:
            logger.error(f"Error updating vehicle {vehicle_id}: {e}")
            raise

    @staticmethod
    async def delete_vehicle(vehicle_id: str, user_id: PyObjectId):
        try:
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
            raise

    @staticmethod
    async def search_vehicles(
        search: VehicleSearch,
        user_id: PyObjectId,
        skip: int = 0,
        limit: int = 10,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        is_active: bool = None
    ) -> List[VehicleOut]:
        try:
            query = {"user_id": user_id}

            if search.brand:
                query["brand"] = {"$regex": search.brand, "$options": "i"}
            if search.model:
                query["model"] = {"$regex": search.model, "$options": "i"}
            if search.type:
                query["type"] = search.type
            if search.fuel_type:
                query["fuel_type"] = search.fuel_type
            if search.transmission:
                query["transmission"] = search.transmission
            if search.is_primary is not None:
                query["is_primary"] = search.is_primary
            if search.is_active is not None:
                query["is_active"] = search.is_active
            if search.year_from or search.year_to:
                query["year"] = {}
                if search.year_from:
                    query["year"]["$gte"] = search.year_from
                if search.year_to:
                    query["year"]["$lte"] = search.year_to
            if search.mileage_min or search.mileage_max:
                query["mileage_km"] = {}
                if search.mileage_min:
                    query["mileage_km"]["$gte"] = search.mileage_min
                if search.mileage_max:
                    query["mileage_km"]["$lte"] = search.mileage_max

            sort_direction = DESCENDING if sort_order == "desc" else 1

            vehicles_cursor = db.vehicles_collection.find(query)\
                .sort(sort_by, sort_direction)\
                .skip(skip).limit(limit)

            vehicles = await vehicles_cursor.to_list(length=limit)
            logger.info(f"Search returned {len(vehicles)} vehicles for user {user_id}")
            return [VehicleOut(**v) for v in vehicles]

        except Exception as e:
            logger.error(f"Vehicle search failed for user {user_id}: {e}")
            raise HTTPException(status_code=500, detail="Error searching vehicles")
        
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
            logger.info(f"Admin retrieved {len(vehicles)} vehicles")
            return [VehicleOut(**v) for v in vehicles]

        except Exception as e:
            logger.error(f"Admin vehicle retrieval failed: {e}")
            raise HTTPException(status_code=500, detail="Error retrieving vehicles")    