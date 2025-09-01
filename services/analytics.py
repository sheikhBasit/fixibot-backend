from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from bson import ObjectId
from database import db
import logging
from collections import defaultdict
import asyncio

logger = logging.getLogger(__name__)

class AnalyticsService:
    @staticmethod
    async def get_user_metrics(time_range: str = "7d") -> Dict[str, Any]:
        """
        Get user analytics metrics for the specified time range
        """
        try:
            time_filter = await AnalyticsService._parse_time_range(time_range)
            
            # Get user registration trends
            registration_pipeline = [
                {"$match": {"created_at": time_filter}},
                {"$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                    "count": {"$sum": 1}
                }},
                {"$sort": {"_id": 1}}
            ]
            
            # Get user role distribution
            role_pipeline = [
                {"$match": {"created_at": time_filter}},
                {"$group": {
                    "_id": "$role",
                    "count": {"$sum": 1}
                }}
            ]
            
            # Get verification status
            verification_pipeline = [
                {"$match": {"created_at": time_filter}},
                {"$group": {
                    "_id": "$is_verified",
                    "count": {"$sum": 1}
                }}
            ]
            
            # Execute all pipelines concurrently
            results = await asyncio.gather(
                db.users_collection.aggregate(registration_pipeline).to_list(length=100),
                db.users_collection.aggregate(role_pipeline).to_list(length=10),
                db.users_collection.aggregate(verification_pipeline).to_list(length=5),
                db.users_collection.count_documents({"created_at": time_filter}),
                db.users_collection.count_documents({}),
                db.users_collection.count_documents({"last_login": {"$gte": datetime.now(timezone.utc) - timedelta(days=1)}})
            )
            
            registration_data, role_data, verification_data, period_count, total_count, active_today = results
            
            return {
                "registration_trends": [
                    {"date": item["_id"], "count": item["count"]} 
                    for item in registration_data
                ],
                "role_distribution": [
                    {"role": item["_id"], "count": item["count"]} 
                    for item in role_data
                ],
                "verification_status": [
                    {"verified": item["_id"], "count": item["count"]} 
                    for item in verification_data
                ],
                "summary": {
                    "total_users": total_count,
                    "new_users_period": period_count,
                    "active_today": active_today,
                    "verification_rate": (
                        next((item["count"] for item in verification_data if item["_id"] == True), 0) / total_count * 100
                        if total_count > 0 else 0
                    )
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting user metrics: {str(e)}")
            raise

    @staticmethod
    async def get_mechanic_metrics(time_range: str = "7d") -> Dict[str, Any]:
        """
        Get mechanic analytics metrics
        """
        try:
            time_filter = await AnalyticsService._parse_time_range(time_range)
            
            # Mechanic registration trends
            registration_pipeline = [
                {"$match": {"created_at": time_filter, "role": "mechanic"}},
                {"$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                    "count": {"$sum": 1}
                }},
                {"$sort": {"_id": 1}}
            ]
            
            # Verification status
            verification_pipeline = [
                {"$match": {"role": "mechanic", "created_at": time_filter}},
                {"$group": {
                    "_id": "$is_verified",
                    "count": {"$sum": 1}
                }}
            ]
            
            # Expertise distribution
            expertise_pipeline = [
                {"$match": {"role": "mechanic", "created_at": time_filter}},
                {"$unwind": "$expertise"},
                {"$group": {
                    "_id": "$expertise",
                    "count": {"$sum": 1}
                }},
                {"$sort": {"count": -1}}
            ]
            
            # Geographic distribution
            geo_pipeline = [
                {"$match": {"role": "mechanic", "created_at": time_filter}},
                {"$group": {
                    "_id": {"province": "$province", "city": "$city"},
                    "count": {"$sum": 1}
                }},
                {"$sort": {"count": -1}}
            ]
            
            results = await asyncio.gather(
                db.users_collection.aggregate(registration_pipeline).to_list(length=100),
                db.users_collection.aggregate(verification_pipeline).to_list(length=5),
                db.users_collection.aggregate(expertise_pipeline).to_list(length=20),
                db.users_collection.aggregate(geo_pipeline).to_list(length=50),
                db.users_collection.count_documents({"role": "mechanic", "created_at": time_filter}),
                db.users_collection.count_documents({"role": "mechanic"}),
                db.users_collection.count_documents({"role": "mechanic", "is_available": True})
            )
            
            reg_data, ver_data, exp_data, geo_data, period_count, total_count, available_count = results
            
            return {
                "registration_trends": [
                    {"date": item["_id"], "count": item["count"]} 
                    for item in reg_data
                ],
                "verification_status": [
                    {"verified": item["_id"], "count": item["count"]} 
                    for item in ver_data
                ],
                "expertise_distribution": [
                    {"expertise": item["_id"], "count": item["count"]} 
                    for item in exp_data
                ],
                "geographic_distribution": [
                    {"location": f"{item['_id']['city']}, {item['_id']['province']}", "count": item["count"]} 
                    for item in geo_data
                ],
                "summary": {
                    "total_mechanics": total_count,
                    "new_mechanics_period": period_count,
                    "available_mechanics": available_count,
                    "verification_rate": (
                        next((item["count"] for item in ver_data if item["_id"] == True), 0) / total_count * 100
                        if total_count > 0 else 0
                    )
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting mechanic metrics: {str(e)}")
            raise

    @staticmethod
    async def get_service_metrics(time_range: str = "7d") -> Dict[str, Any]:
        """
        Get service request analytics
        """
        try:
            time_filter = await AnalyticsService._parse_time_range(time_range)
            
            # Service request trends
            request_pipeline = [
                {"$match": {"created_at": time_filter}},
                {"$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                    "count": {"$sum": 1}
                }},
                {"$sort": {"_id": 1}}
            ]
            
            # Service status distribution
            status_pipeline = [
                {"$match": {"created_at": time_filter}},
                {"$group": {
                    "_id": "$status",
                    "count": {"$sum": 1}
                }}
            ]
            
            # Service type distribution
            type_pipeline = [
                {"$match": {"created_at": time_filter}},
                {"$group": {
                    "_id": "$service_type",
                    "count": {"$sum": 1}
                }},
                {"$sort": {"count": -1}}
            ]
            
            # Average completion time
            completion_pipeline = [
                {"$match": {"status": "completed", "created_at": time_filter}},
                {"$project": {
                    "duration": {
                        "$divide": [
                            {"$subtract": ["$completed_at", "$created_at"]},
                            1000 * 60  # Convert to minutes
                        ]
                    }
                }},
                {"$group": {
                    "_id": None,
                    "avg_duration": {"$avg": "$duration"},
                    "min_duration": {"$min": "$duration"},
                    "max_duration": {"$max": "$duration"}
                }}
            ]
            
            results = await asyncio.gather(
                db.mechanic_service_collection.aggregate(request_pipeline).to_list(length=100),
                db.mechanic_service_collection.aggregate(status_pipeline).to_list(length=10),
                db.mechanic_service_collection.aggregate(type_pipeline).to_list(length=20),
                db.mechanic_service_collection.aggregate(completion_pipeline).to_list(length=1),
                db.mechanic_service_collection.count_documents({"created_at": time_filter}),
                db.mechanic_service_collection.count_documents({}),
                db.mechanic_service_collection.count_documents({"status": "completed", "created_at": time_filter})
            )
            
            req_data, status_data, type_data, comp_data, period_count, total_count, completed_count = results
            
            completion_stats = comp_data[0] if comp_data else {}
            
            return {
                "request_trends": [
                    {"date": item["_id"], "count": item["count"]} 
                    for item in req_data
                ],
                "status_distribution": [
                    {"status": item["_id"], "count": item["count"]} 
                    for item in status_data
                ],
                "type_distribution": [
                    {"service_type": item["_id"], "count": item["count"]} 
                    for item in type_data
                ],
                "completion_metrics": completion_stats,
                "summary": {
                    "total_services": total_count,
                    "new_services_period": period_count,
                    "completed_services": completed_count,
                    "completion_rate": (
                        completed_count / period_count * 100 
                        if period_count > 0 else 0
                    )
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting service metrics: {str(e)}")
            raise

    @staticmethod
    async def get_chat_metrics(time_range: str = "7d") -> Dict[str, Any]:
        """
        Get chat session analytics
        """
        try:
            time_filter = await AnalyticsService._parse_time_range(time_range)
            
            # Chat session trends
            session_pipeline = [
                {"$match": {"created_at": time_filter}},
                {"$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                    "count": {"$sum": 1}
                }},
                {"$sort": {"_id": 1}}
            ]
            
            # Message count per session
            message_pipeline = [
                {"$match": {"created_at": time_filter}},
                {"$project": {
                    "message_count": {"$size": "$chat_history"}
                }},
                {"$group": {
                    "_id": None,
                    "avg_messages": {"$avg": "$message_count"},
                    "total_messages": {"$sum": "$message_count"},
                    "max_messages": {"$max": "$message_count"}
                }}
            ]
            
            # Sessions with images
            image_pipeline = [
                {"$match": {"created_at": time_filter, "image_history": {"$exists": True, "$ne": []}}},
                {"$group": {
                    "_id": None,
                    "count": {"$sum": 1}
                }}
            ]
            
            results = await asyncio.gather(
                db.chat_sessions_collection.aggregate(session_pipeline).to_list(length=100),
                db.chat_sessions_collection.aggregate(message_pipeline).to_list(length=1),
                db.chat_sessions_collection.aggregate(image_pipeline).to_list(length=1),
                db.chat_sessions_collection.count_documents({"created_at": time_filter}),
                db.chat_sessions_collection.count_documents({}),
                db.chat_sessions_collection.count_documents({"updated_at": {"$gte": datetime.now(timezone.utc) - timedelta(hours=1)}})
            )
            
            session_data, message_data, image_data, period_count, total_count, active_hour = results
            
            message_stats = message_data[0] if message_data else {}
            image_sessions = image_data[0]["count"] if image_data else 0
            
            return {
                "session_trends": [
                    {"date": item["_id"], "count": item["count"]} 
                    for item in session_data
                ],
                "message_metrics": message_stats,
                "image_usage": {
                    "sessions_with_images": image_sessions,
                    "image_usage_rate": (
                        image_sessions / period_count * 100 
                        if period_count > 0 else 0
                    )
                },
                "summary": {
                    "total_sessions": total_count,
                    "new_sessions_period": period_count,
                    "active_last_hour": active_hour,
                    "avg_messages_per_session": message_stats.get("avg_messages", 0)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting chat metrics: {str(e)}")
            raise

    @staticmethod
    async def get_system_metrics() -> Dict[str, Any]:
        """
        Get system performance metrics
        """
        try:
            # Get database metrics
            db_metrics = await AnalyticsService._get_database_metrics()
            
            # Get collection sizes
            collection_sizes = await AnalyticsService._get_collection_sizes()
            
            # Get recent error logs (you might want to implement this based on your logging)
            error_stats = await AnalyticsService._get_error_stats()
            
            return {
                "database_metrics": db_metrics,
                "collection_sizes": collection_sizes,
                "error_stats": error_stats,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting system metrics: {str(e)}")
            raise

    @staticmethod
    async def _parse_time_range(time_range: str) -> Dict[str, Any]:
        """Parse time range string into MongoDB date filter"""
        now = datetime.now(timezone.utc)
        
        if time_range == "1d":
            start_date = now - timedelta(days=1)
        elif time_range == "7d":
            start_date = now - timedelta(days=7)
        elif time_range == "30d":
            start_date = now - timedelta(days=30)
        elif time_range == "90d":
            start_date = now - timedelta(days=90)
        else:
            start_date = now - timedelta(days=7)  # Default to 7 days
        
        return {"$gte": start_date}

    @staticmethod
    async def _get_database_metrics() -> Dict[str, Any]:
        """Get database performance metrics"""
        try:
            # Get database stats
            db_stats = await db.client.admin.command("dbStats")
            
            # Get server status
            server_status = await db.client.admin.command("serverStatus")
            
            return {
                "data_size": db_stats.get("dataSize", 0),
                "storage_size": db_stats.get("storageSize", 0),
                "index_size": db_stats.get("indexSize", 0),
                "collections": db_stats.get("collections", 0),
                "connections": server_status.get("connections", {}),
                "memory": server_status.get("mem", {})
            }
        except Exception as e:
            logger.warning(f"Could not get database metrics: {str(e)}")
            return {}

    @staticmethod
    async def _get_collection_sizes() -> List[Dict[str, Any]]:
        """Get sizes of all collections"""
        collections = [
            "users", "mechanics", "vehicles", "chat_sessions", 
            "mechanic_services", "feedback"
        ]
        
        sizes = []
        for collection_name in collections:
            try:
                collection = db.client[db.database_name][collection_name]
                stats = await collection.aggregate([
                    {"$collStats": {"storageStats": {}}}
                ]).to_list(length=1)
                
                if stats:
                    sizes.append({
                        "collection": collection_name,
                        "count": stats[0].get("count", 0),
                        "size": stats[0].get("storageSize", 0),
                        "avg_document_size": stats[0].get("avgObjSize", 0)
                    })
            except Exception as e:
                logger.warning(f"Could not get stats for {collection_name}: {str(e)}")
                continue
        
        return sizes

    @staticmethod
    async def _get_error_stats() -> Dict[str, Any]:
        """Get error statistics (placeholder - implement based on your error logging)"""
        # This would typically query your error logs collection
        return {
            "total_errors_last_24h": 0,
            "error_types": [],
            "most_common_error": None
        }