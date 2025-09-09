from models.mechanic_service import MechanicServiceWithUserAndMechanicOut, MechanicServiceWithMechanicOut
from models.user import UserOut
from models.mechanic import MechanicOut
from typing import List
from bson import ObjectId
from fastapi import HTTPException
from datetime import datetime, timezone
from models.vehicle import VehicleOut
from models.mechanic_service import (
    MechanicServiceIn,
    MechanicServiceOut,
    MechanicServiceUpdate,
    MechanicServiceSearch
)
from database import db
import logging

logger = logging.getLogger("mechanic_service")

class MechanicService:
    @staticmethod
    async def get_by_vehicle_id(vehicle_id: str, current_user, skip: int = 0, limit: int = 50) -> list:
        query = {"vehicle_id": ObjectId(vehicle_id)}
        # Only restrict by user_id if not admin
        if getattr(current_user, "role", None) not in ["admin", "super_admin", "ADMIN", "SUPER_ADMIN"]:
            query["user_id"] = ObjectId(str(current_user.id))
        services = await db.mechanic_service_collection.find(query).skip(skip).limit(limit).to_list(length=limit)
        mechanic_ids = list({svc["mechanic_id"] for svc in services})
        mechanics = {m["_id"]: m for m in await db.mechanics_collection.find({"_id": {"$in": mechanic_ids}}).to_list(length=len(mechanic_ids))}
        vehicle = await db.vehicles_collection.find_one({"_id": ObjectId(vehicle_id)})
        result = []
        for svc in services:
            mechanic = mechanics.get(svc["mechanic_id"])
            svc["vehicle"] = VehicleOut(**vehicle) if vehicle else None
            svc["mechanic"] = MechanicOut(**mechanic) if mechanic else None
            result.append(MechanicServiceWithMechanicOut(**svc))
        return result
    @staticmethod
    async def get_by_mechanic_id(mechanic_id: str, current_user, skip: int = 0, limit: int = 50) -> list:
        query = {"mechanic_id": ObjectId(mechanic_id)}
        # Only restrict by user_id if not admin
        if getattr(current_user, "role", None) not in ["admin", "super_admin", "ADMIN", "SUPER_ADMIN"]:
            query["user_id"] = ObjectId(str(current_user.id))
        services = await db.mechanic_service_collection.find(query).skip(skip).limit(limit).to_list(length=limit)
        vehicle_ids = list({svc["vehicle_id"] for svc in services})
        vehicles = {v["_id"]: v for v in await db.vehicles_collection.find({"_id": {"$in": vehicle_ids}}).to_list(length=len(vehicle_ids))}
        mechanic = await db.mechanics_collection.find_one({"_id": ObjectId(mechanic_id)})
        result = []
        for svc in services:
            vehicle = vehicles.get(svc["vehicle_id"])
            svc["vehicle"] = VehicleOut(**vehicle) if vehicle else None
            svc["mechanic"] = MechanicOut(**mechanic) if mechanic else None
            result.append(MechanicServiceWithMechanicOut(**svc))
        return result
    @staticmethod
    async def get_by_current_user_with_mechanic(user_id: str, skip: int = 0, limit: int = 50, sort_by: str = "created_at", sort_order: int = -1) -> List[MechanicServiceWithMechanicOut]:
        try:
            if db.mechanic_service_collection is None:
                raise HTTPException(status_code=500, detail="Database not initialized")
            obj_id = ObjectId(user_id)
            services = await db.mechanic_service_collection.find({"user_id": obj_id})\
                .sort(sort_by, sort_order)\
                .skip(skip)\
                .limit(limit)\
                .to_list(length=limit)
            mechanic_ids = list({svc["mechanic_id"] for svc in services})
            vehicle_ids = list({svc["vehicle_id"] for svc in services})
            mechanics = {m["_id"]: m for m in await db.mechanics_collection.find({"_id": {"$in": mechanic_ids}}).to_list(length=len(mechanic_ids))}
            vehicles = {v["_id"]: v for v in await db.vehicles_collection.find({"_id": {"$in": vehicle_ids}}).to_list(length=len(vehicle_ids))}
            result = []
            for svc in services:
                mechanic = mechanics.get(svc["mechanic_id"])
                vehicle = vehicles.get(svc["vehicle_id"])
                svc["mechanic"] = MechanicOut(**mechanic) if mechanic else None
                svc["vehicle"] = VehicleOut(**vehicle) if vehicle else None
                result.append(MechanicServiceWithMechanicOut(**svc))
            return result
        except Exception as e:
            logger.error(f"Error fetching mechanic services for current user {user_id} with mechanic info: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch your service history with mechanic info")

    @staticmethod
    async def get_by_id_with_mechanic(service_id: str, current_user) -> MechanicServiceWithMechanicOut:
        obj_id = ObjectId(service_id)
        query = {"_id": obj_id}
        # Only restrict by user_id if not admin
        if getattr(current_user, "role", None) not in ["admin", "super_admin", "ADMIN", "SUPER_ADMIN"]:
            query["user_id"] = ObjectId(str(current_user.id))
        svc = await db.mechanic_service_collection.find_one(query)
        if not svc:
            raise HTTPException(status_code=404, detail="Service not found")
        vehicle = await db.vehicles_collection.find_one({"_id": svc["vehicle_id"]})
        mechanic = await db.mechanics_collection.find_one({"_id": svc["mechanic_id"]})
        svc["mechanic"] = MechanicOut(**mechanic) if mechanic else None
        svc["vehicle"] = VehicleOut(**vehicle) if vehicle else None
        return MechanicServiceWithMechanicOut(**svc)
    @staticmethod
    async def get_all_admin_with_user_and_mechanic(limit: int = 1000) -> List[MechanicServiceWithUserAndMechanicOut]:
        try:
            docs = await db.mechanic_service_collection.find().limit(limit).to_list(length=limit)
            valid_docs = [doc for doc in docs if all(k in doc for k in ["user_id", "mechanic_id", "vehicle_id", "issue_description", "created_at"])]
            vehicle_ids = list({doc["vehicle_id"] for doc in valid_docs})
            user_ids = list({doc["user_id"] for doc in valid_docs})
            mechanic_ids = list({doc["mechanic_id"] for doc in valid_docs})
            users = {u["_id"]: u for u in await db.users_collection.find({"_id": {"$in": user_ids}}).to_list(length=len(user_ids))}
            mechanics = {m["_id"]: m for m in await db.mechanics_collection.find({"_id": {"$in": mechanic_ids}}).to_list(length=len(mechanic_ids))}
            vehicles = {v["_id"]: v for v in await db.vehicles_collection.find({"_id": {"$in": vehicle_ids}}).to_list(length=len(vehicle_ids))}
            result = []
            for doc in valid_docs:
                user = users.get(doc["user_id"])
                if user and isinstance(user.get("_id"), ObjectId):
                    user = {**user, "_id": str(user["_id"])}
                mechanic = mechanics.get(doc["mechanic_id"])
                vehicle = vehicles.get(doc["vehicle_id"])
                doc["user"] = UserOut(**user) if user else None
                doc["mechanic"] = MechanicOut(**mechanic) if mechanic else None
                doc["vehicle"] = VehicleOut(**vehicle) if vehicle else None
                result.append(MechanicServiceWithUserAndMechanicOut(**doc))
            return result
        except Exception as e:
            logger.error(f"Error fetching all mechanic services with user and mechanic: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch mechanic services with user and mechanic info")

    @staticmethod
    async def get_by_id_admin_with_user_and_mechanic(service_id: str) -> MechanicServiceWithUserAndMechanicOut:
        try:
            obj_id = ObjectId(service_id)
            doc = await db.mechanic_service_collection.find_one({"_id": obj_id})
            if not doc:
                raise HTTPException(status_code=404, detail="Service not found")
            user = await db.users_collection.find_one({"_id": doc["user_id"]})
            if user and isinstance(user.get("_id"), ObjectId):
                user = {**user, "_id": str(user["_id"])}
                vehicle = await db.vehicles_collection.find_one({"_id": doc["vehicle_id"]})
                mechanic = await db.mechanics_collection.find_one({"_id": doc["mechanic_id"]})
                doc["user"] = UserOut(**user) if user else None
                doc["mechanic"] = MechanicOut(**mechanic) if mechanic else None
                doc["vehicle"] = VehicleOut(**vehicle) if vehicle else None
                return MechanicServiceWithUserAndMechanicOut(**doc)
        except Exception as e:
            logger.error(f"Error fetching mechanic service {service_id} with user and mechanic: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch mechanic service with user and mechanic info")
    collection = db.mechanic_service_collection

    @staticmethod
    async def create(data: MechanicServiceIn) -> MechanicServiceOut:
        if db.mechanic_service_collection is None:
            raise HTTPException(status_code=500, detail="Database not initialized")
        
        try:
            payload = data.model_dump(by_alias=True)
            payload["created_at"] = datetime.now(timezone.utc)
            payload["updated_at"] = None

            result = await db.mechanic_service_collection.insert_one(payload)
            saved = await db.mechanic_service_collection.find_one({"_id": result.inserted_id})

            await db.mechanic_service_collection.insert_one({
                "entity": "mechanic_service",
                "entity_id": str(result.inserted_id),
                "action": "created",
                "performed_by": str(payload["user_id"]),
                "timestamp": datetime.now(timezone.utc)
            })

            return MechanicServiceOut(**saved)
        except Exception as e:
            logger.error(f"Failed to create service: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def get_by_id(service_id: str) -> MechanicServiceOut:
        try:
            obj_id = ObjectId(service_id)
            record = await db.mechanic_service_collection.find_one({"_id": obj_id})
            if not record:
                raise HTTPException(status_code=404, detail="Service not found")
            return MechanicServiceOut(**record)
        except Exception as e:
            logger.error(f"Failed to fetch service {service_id}: {e}")
            raise HTTPException(status_code=400, detail="Invalid service ID")

    @staticmethod
    async def update(service_id: str, update: MechanicServiceUpdate) -> MechanicServiceOut:
        try:
            obj_id = ObjectId(service_id)
            update_data = update.model_dump(exclude_unset=True, by_alias=True)
            result = await db.mechanic_service_collection.update_one(
                {"_id": obj_id}, {"$set": update_data}
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=400, detail="No changes made")

            updated = await db.mechanic_service_collection.find_one({"_id": obj_id})
            await db.mechanic_service_collection.insert_one({
            "entity": "mechanic_service",
            "entity_id": service_id,
            "action": "updated",
            "performed_by": str(updated["user_id"]),
            "timestamp": datetime.now(timezone.utc)
        })

            logger.info(f"Updated service {service_id}")
            return MechanicServiceOut(**updated)
        except Exception as e:
            logger.error(f"Update error for service {service_id}: {e}")
            raise

    @staticmethod
    async def delete(service_id: str):
        try:
            obj_id = ObjectId(service_id)
            service = await db.mechanic_service_collection.find_one({"_id": obj_id})
            if not service:
                raise HTTPException(status_code=404, detail="Service not found")

            result = await db.mechanic_service_collection.delete_one({"_id": obj_id})
            await db.mechanic_service_collection.insert_one({
            "entity": "mechanic_service",
            "entity_id": service_id,
            "action": "deleted",
            "performed_by": str(service["user_id"]),
            "timestamp": datetime.now(timezone.utc)
        })
            if result.deleted_count != 1:
                raise HTTPException(status_code=404, detail="Service not found")
            logger.info(f"Deleted service {service_id}")
            return {"message": "Service deleted successfully"}
        except Exception as e:
            logger.error(f"Deletion error for service {service_id}: {e}")
            raise

    @staticmethod
    async def search(search: MechanicServiceSearch, skip: int, limit: int) -> List[MechanicServiceOut]:
        try:
            query = {}
            if search.user_id:
                query["user_id"] = search.user_id
            if search.mechanic_id:
                query["mechanic_id"] = search.mechanic_id
            if search.status:
                query["status"] = search.status
            if search.service_type:
                query["service_type"] = search.service_type
            if search.region:
                query["region"] = {"$regex": search.region, "$options": "i"}
            if search.date_from or search.date_to:
                query["created_at"] = {}
                if search.date_from:
                    query["created_at"]["$gte"] = search.date_from
                if search.date_to:
                    query["created_at"]["$lte"] = search.date_to

            services = await db.mechanic_service_collection.find(query).skip(skip).limit(limit).to_list(length=limit)
            return [MechanicServiceOut(**svc) for svc in services]
        except Exception as e:
            logger.error(f"Search error: {e}")
            raise HTTPException(status_code=500, detail="Search operation failed")
    
    @staticmethod
    async def get_all_admin(limit: int = 1000) -> List[MechanicServiceOut]:
        try:
            docs = await db.mechanic_service_collection.find().limit(limit).to_list(length=limit)
            
            # Filter out invalid documents
            valid_docs = [doc for doc in docs if all(k in doc for k in ["user_id", "mechanic_id", "vehicle_id", "issue_description", "created_at"])]
            
            return [MechanicServiceOut(**svc) for svc in valid_docs]
        except Exception as e:
            logger.error(f"Error fetching all mechanic services for admin: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch mechanic services")


    @staticmethod
    async def get_by_user_admin(user_id: str, limit: int = 100) -> List[MechanicServiceOut]:
        try:
            if db.mechanic_service_collection is None:
                raise HTTPException(status_code=500, detail="Database not initialized")
            
            obj_id = ObjectId(user_id)
            services = await db.mechanic_service_collection.find({"user_id": obj_id}).limit(limit).to_list(length=limit)
            return [MechanicServiceOut(**svc) for svc in services]
        except Exception as e:
            logger.error(f"Error fetching mechanic services for user {user_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch services for the specified user")

    @staticmethod
    async def get_by_current_user(user_id: str, skip: int = 0, limit: int = 50, sort_by: str = "created_at", sort_order: int = -1) -> List[MechanicServiceOut]:
        try:
            if db.mechanic_service_collection is None:
                raise HTTPException(status_code=500, detail="Database not initialized")
            
            obj_id = ObjectId(user_id)
            services = await db.mechanic_service_collection.find({"user_id": obj_id})\
                .sort(sort_by, sort_order)\
                .skip(skip)\
                .limit(limit)\
                .to_list(length=limit)
            return [MechanicServiceOut(**svc) for svc in services]
        except Exception as e:
            logger.error(f"Error fetching mechanic services for current user {user_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch your service history")