# services/admin_service.py
from datetime import datetime, timedelta
from typing import List, Dict, Any
from bson import ObjectId
from database import db
import os
import logging
from config import settings

logger = logging.getLogger(__name__)

class AdminService:
    @staticmethod
    async def get_dashboard_overview() -> Dict[str, Any]:
        """Get comprehensive dashboard overview statistics"""
        try:
            # Get counts for all entities
            users_count = await db.users_collection.count_documents({})
            mechanics_count = await db.mechanics_collection.count_documents({})
            vehicles_count = await db.vehicles_collection.count_documents({})
            services_count = await db.mechanic_service_collection.count_documents({})
            chats_count = await db.chat_sessions_collection.count_documents({})
            feedback_count = await db.feedback_collection.count_documents({})
            
            # Get today's counts
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_users = await db.users_collection.count_documents({"created_at": {"$gte": today}})
            today_services = await db.mechanic_service_collection.count_documents({"created_at": {"$gte": today}})
            today_chats = await db.chat_sessions_collection.count_documents({"created_at": {"$gte": today}})
            
            # Get pending verification count
            pending_verification = await db.mechanics_collection.count_documents({"is_verified": False})
            
            # Get active services count (status: pending, in_progress)
            active_services = await db.mechanic_service_collection.count_documents({
                "status": {"$in": ["pending", "in_progress"]}
            })
            
            return {
                "total_users": users_count,
                "total_mechanics": mechanics_count,
                "total_vehicles": vehicles_count,
                "total_services": services_count,
                "total_chats": chats_count,
                "total_feedback": feedback_count,
                "today_users": today_users,
                "today_services": today_services,
                "today_chats": today_chats,
                "pending_verification": pending_verification,
                "active_services": active_services,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting dashboard overview: {e}")
            raise

    @staticmethod
    async def global_search(query: str, entity_type: str, limit: int = 20) -> Dict[str, List]:
        """Unified search across all entities"""
        results = {}
        
        try:
            if entity_type in ["all", "users"]:
                users = await db.users_collection.find({
                    "$or": [
                        {"first_name": {"$regex": query, "$options": "i"}},
                        {"last_name": {"$regex": query, "$options": "i"}},
                        {"email": {"$regex": query, "$options": "i"}},
                        {"phone_number": {"$regex": query, "$options": "i"}}
                    ]
                }).limit(limit).to_list(length=limit)
                results["users"] = users
            
            if entity_type in ["all", "mechanics"]:
                mechanics = await db.mechanics_collection.find({
                    "$or": [
                        {"first_name": {"$regex": query, "$options": "i"}},
                        {"last_name": {"$regex": query, "$options": "i"}},
                        {"email": {"$regex": query, "$options": "i"}},
                        {"phone_number": {"$regex": query, "$options": "i"}},
                        {"workshop_name": {"$regex": query, "$options": "i"}},
                        {"city": {"$regex": query, "$options": "i"}}
                    ]
                }).limit(limit).to_list(length=limit)
                results["mechanics"] = mechanics
            
            if entity_type in ["all", "vehicles"]:
                vehicles = await db.vehicles_collection.find({
                    "$or": [
                        {"model": {"$regex": query, "$options": "i"}},
                        {"brand": {"$regex": query, "$options": "i"}},
                        {"type": {"$regex": query, "$options": "i"}}
                    ]
                }).limit(limit).to_list(length=limit)
                results["vehicles"] = vehicles
            
            if entity_type in ["all", "services"]:
                services = await db.mechanic_service_collection.find({
                    "$or": [
                        {"service_type": {"$regex": query, "$options": "i"}},
                        {"description": {"$regex": query, "$options": "i"}},
                        {"status": {"$regex": query, "$options": "i"}}
                    ]
                }).limit(limit).to_list(length=limit)
                results["services"] = services
            
            return results
            
        except Exception as e:
            logger.error(f"Error in global search: {e}")
            raise

    @staticmethod
    async def get_recent_logs(lines: int = 100, log_type: str = "app") -> List[str]:
        """Get recent application logs (placeholder implementation)"""
        # This is a placeholder - you'd integrate with your actual logging system
        try:
            log_file = ""
            if log_type == "app":
                log_file = "app.log"
            elif log_type == "error":
                log_file = "error.log"
            elif log_type == "access":
                log_file = "access.log"
            
            # Simulated log retrieval - replace with actual log file reading
            return [f"Log entry {i} - {datetime.now()}" for i in range(min(lines, 10))]
            
        except Exception as e:
            logger.error(f"Error retrieving logs: {e}")
            return [f"Error retrieving logs: {str(e)}"]

    # @staticmethod
    # async def get_pending_mechanics(skip: int = 0, limit: int = 50) -> List[Dict]:
    #     """Get mechanics pending verification"""
    #     try:
    #         mechanics = await db.mechanics_collection.find(
    #             {"is_verified": False}
    #         ).skip(skip).limit(limit).to_list(length=limit)
    #         return mechanics
    #     except Exception as e:
    #         logger.error(f"Error getting pending mechanics: {e}")
    #         raise

    # @staticmethod
    # async def get_unverified_mechanics(skip: int = 0, limit: int = 50) -> List[Dict]:
    #     """Get all unverified mechanics"""
    #     try:
    #         mechanics = await db.mechanics_collection.find(
    #             {"is_verified": False}
    #         ).skip(skip).limit(limit).to_list(length=limit)
    #         return mechanics
    #     except Exception as e:
    #         logger.error(f"Error getting unverified mechanics: {e}")
    #         raise

    @staticmethod
    async def update_user_status(user_id: str, is_active: bool) -> bool:
        """Update user active status"""
        try:
            result = await db.users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"is_active": is_active, "updated_at": datetime.now()}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating user status: {e}")
            raise

    # @staticmethod
    # async def update_user_role(user_id: str, new_role: str) -> bool:
    #     """Update user role"""
    #     try:
    #         result = await db.users_collection.update_one(
    #             {"_id": ObjectId(user_id)},
    #             {"$set": {"role": new_role, "updated_at": datetime.now()}}
    #         )
    #         return result.modified_count > 0
    #     except Exception as e:
    #         logger.error(f"Error updating user role: {e}")
    #         raise

    # @staticmethod
    # async def get_knowledge_base_status() -> Dict[str, Any]:
    #     """Check status of AI knowledge base"""
    #     try:
    #         kb_path = settings.KNOWLEDGE_BASE_PDF
    #         exists = os.path.exists(kb_path)
            
    #         status_info = {
    #             "exists": exists,
    #             "path": kb_path,
    #             "size": os.path.getsize(kb_path) if exists else 0,
    #             "last_modified": os.path.getmtime(kb_path) if exists else None,
    #             "readable": os.access(kb_path, os.R_OK) if exists else False
    #         }
            
    #         return status_info
    #     except Exception as e:
    #         logger.error(f"Error getting knowledge base status: {e}")
    #         raise