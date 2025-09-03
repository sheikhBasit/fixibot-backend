# services/admin_service.py
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
from bson import ObjectId
from fastapi import HTTPException
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
    
    @staticmethod
    async def generate_users_report(time_range: str = "30d", format: str = "json") -> Dict[str, Any]:
        """Generate comprehensive users report"""
        try:
            time_filter = await AdminService._parse_time_range(time_range)
            
            # User registration trends
            registration_pipeline = [
                {"$match": {"created_at": time_filter}},
                {"$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                    "count": {"$sum": 1},
                    "verified_count": {"$sum": {"$cond": [{"$eq": ["$is_verified", True]}, 1, 0]}},
                    "active_count": {"$sum": {"$cond": [{"$eq": ["$is_active", True]}, 1, 0]}}
                }},
                {"$sort": {"_id": 1}}
            ]
            
            # Role distribution
            role_pipeline = [
                {"$match": {"created_at": time_filter}},
                {"$group": {
                    "_id": "$role",
                    "count": {"$sum": 1},
                    "active_count": {"$sum": {"$cond": [{"$eq": ["$is_active", True]}, 1, 0]}}
                }}
            ]
            
            # User activity
            activity_pipeline = [
                {"$match": {"created_at": time_filter, "last_login": {"$exists": True}}},
                {"$group": {
                    "_id": None,
                    "avg_logins": {"$avg": "$login_count"},
                    "total_logins": {"$sum": "$login_count"},
                    "recent_active": {"$sum": {"$cond": [
                        {"$gte": ["$last_login", datetime.now() - timedelta(days=7)]}, 1, 0
                    ]}}
                }}
            ]
            
            results = await asyncio.gather(
                db.users_collection.aggregate(registration_pipeline).to_list(length=100),
                db.users_collection.aggregate(role_pipeline).to_list(length=10),
                db.users_collection.aggregate(activity_pipeline).to_list(length=1),
                db.users_collection.count_documents({"created_at": time_filter}),
                db.users_collection.count_documents({"is_verified": True, "created_at": time_filter}),
                db.users_collection.count_documents({"is_active": True, "created_at": time_filter})
            )
            
            registration_data, role_data, activity_data, total_users, verified_users, active_users = results
            
            report = {
                "time_range": time_range,
                "summary": {
                    "total_users": total_users,
                    "verified_users": verified_users,
                    "active_users": active_users,
                    "verification_rate": (verified_users / total_users * 100) if total_users > 0 else 0,
                    "activation_rate": (active_users / total_users * 100) if total_users > 0 else 0
                },
                "registration_trends": registration_data,
                "role_distribution": role_data,
                "activity_metrics": activity_data[0] if activity_data else {},
                "generated_at": datetime.now().isoformat()
            }
            
            return await AdminService._format_report(report, format)
            
        except Exception as e:
            logger.error(f"Error generating users report: {e}")
            raise

    @staticmethod
    async def generate_services_report(time_range: str = "30d", format: str = "json") -> Dict[str, Any]:
        """Generate comprehensive services report"""
        try:
            time_filter = await AdminService._parse_time_range(time_range)
            
            # Service request trends
            request_pipeline = [
                {"$match": {"created_at": time_filter}},
                {"$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                    "count": {"$sum": 1},
                    "completed_count": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}},
                    "revenue": {"$sum": {"$ifNull": ["$total_amount", 0]}}
                }},
                {"$sort": {"_id": 1}}
            ]
            
            # Status distribution
            status_pipeline = [
                {"$match": {"created_at": time_filter}},
                {"$group": {
                    "_id": "$status",
                    "count": {"$sum": 1},
                    "avg_duration": {"$avg": {
                        "$divide": [
                            {"$subtract": ["$completed_at", "$created_at"]},
                            1000 * 60 * 60  # Convert to hours
                        ]
                    }},
                    "total_revenue": {"$sum": {"$ifNull": ["$total_amount", 0]}}
                }}
            ]
            
            # Service type analysis
            type_pipeline = [
                {"$match": {"created_at": time_filter}},
                {"$group": {
                    "_id": "$service_type",
                    "count": {"$sum": 1},
                    "avg_cost": {"$avg": {"$ifNull": ["$total_amount", 0]}},
                    "completion_rate": {"$avg": {
                        "$cond": [{"$eq": ["$status", "completed"]}, 1, 0]
                    }}
                }},
                {"$sort": {"count": -1}}
            ]
            
            results = await asyncio.gather(
                db.mechanic_service_collection.aggregate(request_pipeline).to_list(length=100),
                db.mechanic_service_collection.aggregate(status_pipeline).to_list(length=10),
                db.mechanic_service_collection.aggregate(type_pipeline).to_list(length=20),
                db.mechanic_service_collection.count_documents({"created_at": time_filter}),
                db.mechanic_service_collection.count_documents({"status": "completed", "created_at": time_filter}),
                db.mechanic_service_collection.aggregate([
                    {"$match": {"created_at": time_filter}},
                    {"$group": {
                        "_id": None,
                        "total_revenue": {"$sum": {"$ifNull": ["$total_amount", 0]}},
                        "avg_revenue": {"$avg": {"$ifNull": ["$total_amount", 0]}}
                    }}
                ]).to_list(length=1)
            )
            
            request_data, status_data, type_data, total_services, completed_services, revenue_data = results
            
            report = {
                "time_range": time_range,
                "summary": {
                    "total_services": total_services,
                    "completed_services": completed_services,
                    "completion_rate": (completed_services / total_services * 100) if total_services > 0 else 0,
                    "total_revenue": revenue_data[0]["total_revenue"] if revenue_data else 0,
                    "avg_revenue": revenue_data[0]["avg_revenue"] if revenue_data else 0
                },
                "request_trends": request_data,
                "status_distribution": status_data,
                "service_type_analysis": type_data,
                "generated_at": datetime.now().isoformat()
            }
            
            return await AdminService._format_report(report, format)
            
        except Exception as e:
            logger.error(f"Error generating services report: {e}")
            raise

    @staticmethod
    async def generate_mechanics_report(time_range: str = "30d", format: str = "json") -> Dict[str, Any]:
        """Generate comprehensive mechanics report"""
        try:
            time_filter = await AdminService._parse_time_range(time_range)
            
            # Mechanic registration trends
            registration_pipeline = [
                {"$match": {"role": "mechanic", "created_at": time_filter}},
                {"$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                    "count": {"$sum": 1},
                    "verified_count": {"$sum": {"$cond": [{"$eq": ["$is_verified", True]}, 1, 0]}},
                    "active_count": {"$sum": {"$cond": [{"$eq": ["$is_available", True]}, 1, 0]}}
                }},
                {"$sort": {"_id": 1}}
            ]
            
            # Expertise distribution
            expertise_pipeline = [
                {"$match": {"role": "mechanic", "created_at": time_filter}},
                {"$unwind": "$expertise"},
                {"$group": {
                    "_id": "$expertise",
                    "count": {"$sum": 1},
                    "avg_rating": {"$avg": "$rating"},
                    "avg_experience": {"$avg": "$years_of_experience"}
                }},
                {"$sort": {"count": -1}}
            ]
            
            # Geographic distribution
            geo_pipeline = [
                {"$match": {"role": "mechanic", "created_at": time_filter}},
                {"$group": {
                    "_id": {"province": "$province", "city": "$city"},
                    "count": {"$sum": 1},
                    "avg_rating": {"$avg": "$rating"},
                    "total_services": {"$sum": "$completed_services_count"}
                }},
                {"$sort": {"count": -1}}
            ]
            
            # Performance metrics
            performance_pipeline = [
                {"$match": {"role": "mechanic", "created_at": time_filter}},
                {"$group": {
                    "_id": None,
                    "avg_rating": {"$avg": "$rating"},
                    "avg_response_time": {"$avg": "$avg_response_time"},
                    "avg_completion_time": {"$avg": "$avg_completion_time"},
                    "total_services_completed": {"$sum": "$completed_services_count"}
                }}
            ]
            
            results = await asyncio.gather(
                db.users_collection.aggregate(registration_pipeline).to_list(length=100),
                db.users_collection.aggregate(expertise_pipeline).to_list(length=20),
                db.users_collection.aggregate(geo_pipeline).to_list(length=50),
                db.users_collection.aggregate(performance_pipeline).to_list(length=1),
                db.users_collection.count_documents({"role": "mechanic", "created_at": time_filter}),
                db.users_collection.count_documents({"role": "mechanic", "is_verified": True, "created_at": time_filter}),
                db.users_collection.count_documents({"role": "mechanic", "is_available": True, "created_at": time_filter})
            )
            
            reg_data, exp_data, geo_data, perf_data, total_mechanics, verified_mechanics, available_mechanics = results
            
            report = {
                "time_range": time_range,
                "summary": {
                    "total_mechanics": total_mechanics,
                    "verified_mechanics": verified_mechanics,
                    "available_mechanics": available_mechanics,
                    "verification_rate": (verified_mechanics / total_mechanics * 100) if total_mechanics > 0 else 0,
                    "availability_rate": (available_mechanics / total_mechanics * 100) if total_mechanics > 0 else 0
                },
                "registration_trends": reg_data,
                "expertise_distribution": exp_data,
                "geographic_distribution": geo_data,
                "performance_metrics": perf_data[0] if perf_data else {},
                "generated_at": datetime.now().isoformat()
            }
            
            return await AdminService._format_report(report, format)
            
        except Exception as e:
            logger.error(f"Error generating mechanics report: {e}")
            raise

    @staticmethod
    async def generate_financial_report(time_range: str = "30d", format: str = "json") -> Dict[str, Any]:
        """Generate comprehensive financial report"""
        try:
            time_filter = await AdminService._parse_time_range(time_range)
            
            # Revenue trends
            revenue_pipeline = [
                {"$match": {"status": "completed", "completed_at": time_filter}},
                {"$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$completed_at"}},
                    "daily_revenue": {"$sum": {"$ifNull": ["$total_amount", 0]}},
                    "service_count": {"$sum": 1},
                    "avg_ticket": {"$avg": {"$ifNull": ["$total_amount", 0]}}
                }},
                {"$sort": {"_id": 1}}
            ]
            
            # Revenue by service type
            revenue_by_type_pipeline = [
                {"$match": {"status": "completed", "completed_at": time_filter}},
                {"$group": {
                    "_id": "$service_type",
                    "total_revenue": {"$sum": {"$ifNull": ["$total_amount", 0]}},
                    "service_count": {"$sum": 1},
                    "avg_revenue": {"$avg": {"$ifNull": ["$total_amount", 0]}}
                }},
                {"$sort": {"total_revenue": -1}}
            ]
            
            # Platform commission calculation
            commission_pipeline = [
                {"$match": {"status": "completed", "completed_at": time_filter}},
                {"$group": {
                    "_id": None,
                    "total_revenue": {"$sum": {"$ifNull": ["$total_amount", 0]}},
                    "platform_commission": {"$sum": {
                        "$multiply": [
                            {"$ifNull": ["$total_amount", 0]},
                            0.15  # 15% platform commission
                        ]
                    }},
                    "mechanic_earnings": {"$sum": {
                        "$multiply": [
                            {"$ifNull": ["$total_amount", 0]},
                            0.85  # 85% to mechanic
                        ]
                    }}
                }}
            ]
            
            results = await asyncio.gather(
                db.mechanic_service_collection.aggregate(revenue_pipeline).to_list(length=100),
                db.mechanic_service_collection.aggregate(revenue_by_type_pipeline).to_list(length=20),
                db.mechanic_service_collection.aggregate(commission_pipeline).to_list(length=1),
                db.mechanic_service_collection.count_documents({"status": "completed", "completed_at": time_filter}),
                db.mechanic_service_collection.aggregate([
                    {"$match": {"status": "completed", "completed_at": time_filter}},
                    {"$group": {
                        "_id": None,
                        "total_revenue": {"$sum": {"$ifNull": ["$total_amount", 0]}}
                    }}
                ]).to_list(length=1)
            )
            
            revenue_data, type_data, commission_data, completed_services, total_revenue_data = results
            
            report = {
                "time_range": time_range,
                "summary": {
                    "total_completed_services": completed_services,
                    "total_revenue": total_revenue_data[0]["total_revenue"] if total_revenue_data else 0,
                    "platform_commission": commission_data[0]["platform_commission"] if commission_data else 0,
                    "mechanic_earnings": commission_data[0]["mechanic_earnings"] if commission_data else 0,
                    "avg_service_value": (total_revenue_data[0]["total_revenue"] / completed_services) if completed_services > 0 else 0
                },
                "revenue_trends": revenue_data,
                "revenue_by_service_type": type_data,
                "financial_metrics": commission_data[0] if commission_data else {},
                "generated_at": datetime.now().isoformat()
            }
            
            return await AdminService._format_report(report, format)
            
        except Exception as e:
            logger.error(f"Error generating financial report: {e}")
            raise

    @staticmethod
    async def export_report(report_data: Dict[str, Any], export_format: str) -> Any:
        """Export report in various formats"""
        try:
            if export_format == "csv":
                return await AdminService._convert_to_csv(report_data)
            elif export_format == "pdf":
                return await AdminService._convert_to_pdf(report_data)
            elif export_format == "excel":
                return await AdminService._convert_to_excel(report_data)
            else:
                return report_data  # Return JSON by default
                
        except Exception as e:
            logger.error(f"Error exporting report: {e}")
            raise

    @staticmethod
    async def _format_report(report_data: Dict[str, Any], format: str) -> Dict[str, Any]:
        """Format report based on requested format"""
        if format == "csv":
            return await AdminService._convert_to_csv(report_data)
        elif format == "pdf":
            return await AdminService._convert_to_pdf(report_data)
        elif format == "excel":
            return await AdminService._convert_to_excel(report_data)
        else:
            return report_data  # JSON format

    @staticmethod
    async def _convert_to_csv(report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert report data to CSV format (simplified)"""
        # This would be implemented with a proper CSV library
        return {
            "format": "csv",
            "filename": f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "data": report_data,
            "download_url": f"/api/reports/download/{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        }

    @staticmethod
    async def _convert_to_pdf(report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert report data to PDF format (simplified)"""
        # This would be implemented with a proper PDF generation library
        return {
            "format": "pdf",
            "filename": f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            "data": report_data,
            "download_url": f"/api/reports/download/{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        }

    @staticmethod
    async def _convert_to_excel(report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert report data to Excel format (simplified)"""
        # This would be implemented with a proper Excel library
        return {
            "format": "excel",
            "filename": f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            "data": report_data,
            "download_url": f"/api/reports/download/{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        }
    
    @staticmethod
    async def get_system_settings() -> Dict[str, Any]:
        """Get all system settings"""
        try:
            settings = await db.settings_collection.find_one({"type": "system"})
            if not settings:
                # Return default settings if none exist
                default_settings = {
                    "app_name": settings.APP_NAME,
                    "maintenance_mode": False,
                    "max_file_size": 10,  # MB
                    "allowed_file_types": ["image/jpeg", "image/png", "image/gif"],
                    "session_timeout": 24,  # hours
                    "backup_enabled": True,
                    "backup_frequency": "daily"
                }
                await db.settings_collection.insert_one({
                    "type": "system",
                    "settings": default_settings,
                    "updated_at": datetime.now()
                })
                return default_settings
            return settings.get("settings", {})
        except Exception as e:
            logger.error(f"Error getting system settings: {e}")
            raise

    @staticmethod
    async def update_system_settings(new_settings: Dict[str, Any]) -> bool:
        """Update system settings"""
        try:
            result = await db.settings_collection.update_one(
                {"type": "system"},
                {"$set": {
                    "settings": new_settings,
                    "updated_at": datetime.now()
                }},
                upsert=True
            )
            return result.modified_count > 0 or result.upserted_id is not None
        except Exception as e:
            logger.error(f"Error updating system settings: {e}")
            raise

    @staticmethod
    async def get_email_settings() -> Dict[str, Any]:
        """Get email settings"""
        try:
            settings = await db.settings_collection.find_one({"type": "email"})
            if not settings:
                # Return default email settings
                default_settings = {
                    "smtp_host": "",
                    "smtp_port": 587,
                    "smtp_username": "",
                    "smtp_password": "",
                    "from_email": "fixibot038@gmail.com",
                    "from_name": "FixiBot",
                    "email_verification_enabled": True,
                    "notification_emails_enabled": True
                }
                await db.settings_collection.insert_one({
                    "type": "email",
                    "settings": default_settings,
                    "updated_at": datetime.now()
                })
                return default_settings
            return settings.get("settings", {})
        except Exception as e:
            logger.error(f"Error getting email settings: {e}")
            raise

    @staticmethod
    async def update_email_settings(new_settings: Dict[str, Any]) -> bool:
        """Update email settings"""
        try:
            result = await db.settings_collection.update_one(
                {"type": "email"},
                {"$set": {
                    "settings": new_settings,
                    "updated_at": datetime.now()
                }},
                upsert=True
            )
            return result.modified_count > 0 or result.upserted_id is not None
        except Exception as e:
            logger.error(f"Error updating email settings: {e}")
            raise

    @staticmethod
    async def get_notification_settings() -> Dict[str, Any]:
        """Get notification settings"""
        try:
            settings = await db.settings_collection.find_one({"type": "notifications"})
            if not settings:
                # Return default notification settings
                default_settings = {
                    "email_notifications": True,
                    "push_notifications": False,
                    "sms_notifications": False,
                    "admin_alerts": True,
                    "new_user_notifications": True,
                    "new_service_notifications": True,
                    "payment_notifications": True,
                    "system_alerts": True
                }
                await db.settings_collection.insert_one({
                    "type": "notifications",
                    "settings": default_settings,
                    "updated_at": datetime.now()
                })
                return default_settings
            return settings.get("settings", {})
        except Exception as e:
            logger.error(f"Error getting notification settings: {e}")
            raise

    @staticmethod
    async def update_notification_settings(new_settings: Dict[str, Any]) -> bool:
        """Update notification settings"""
        try:
            result = await db.settings_collection.update_one(
                {"type": "notifications"},
                {"$set": {
                    "settings": new_settings,
                    "updated_at": datetime.now()
                }},
                upsert=True
            )
            return result.modified_count > 0 or result.upserted_id is not None
        except Exception as e:
            logger.error(f"Error updating notification settings: {e}")
            raise
    

    @staticmethod
    async def get_audit_logs(skip: int = 0, limit: int = 50, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get audit logs with optional filtering"""
        try:
            query = filters or {}
            
            logs = await db.audit_logs_collection.find(query)\
                .sort("timestamp", -1)\
                .skip(skip)\
                .limit(limit)\
                .to_list(length=limit)
                
            return logs
        except Exception as e:
            logger.error(f"Error getting audit logs: {e}")
            raise

    @staticmethod
    async def get_audit_log(log_id: str) -> Dict[str, Any]:
        """Get specific audit log by ID"""
        try:
            log = await db.audit_logs_collection.find_one({"_id": ObjectId(log_id)})
            if not log:
                raise HTTPException(status_code=404, detail="Audit log not found")
            return log
        except Exception as e:
            logger.error(f"Error getting audit log: {e}")
            raise

    @staticmethod
    async def get_audit_action_stats(time_range: str = "7d") -> Dict[str, Any]:
        """Get audit action statistics"""
        try:
            time_filter = await AdminService._parse_time_range(time_range)
            
            pipeline = [
                {"$match": {"timestamp": time_filter}},
                {"$group": {
                    "_id": "$action",
                    "count": {"$sum": 1},
                    "users": {"$addToSet": "$user_id"},
                    "last_performed": {"$max": "$timestamp"}
                }},
                {"$sort": {"count": -1}}
            ]
            
            stats = await db.audit_logs_collection.aggregate(pipeline).to_list(length=50)
            
            return {
                "time_range": time_range,
                "total_actions": sum(item["count"] for item in stats),
                "unique_users": len(set(user for item in stats for user in item.get("users", []))),
                "action_breakdown": stats,
                "generated_at": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting audit action stats: {e}")
            raise

    @staticmethod
    async def get_user_activity_audit(user_id: str, time_range: str = "30d") -> Dict[str, Any]:
        """Get user activity audit report"""
        try:
            time_filter = await AdminService._parse_time_range(time_range)
            
            pipeline = [
                {"$match": {"user_id": user_id, "timestamp": time_filter}},
                {"$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                    "action_count": {"$sum": 1},
                    "actions": {"$push": {
                        "action": "$action",
                        "timestamp": "$timestamp",
                        "details": "$details"
                    }},
                    "unique_actions": {"$addToSet": "$action"}
                }},
                {"$sort": {"_id": 1}},
                {"$project": {
                    "date": "$_id",
                    "action_count": 1,
                    "unique_action_count": {"$size": "$unique_actions"},
                    "actions": {"$slice": ["$actions", 10]},  # Limit to last 10 actions per day
                    "_id": 0
                }}
            ]
            
            user_activity = await db.audit_logs_collection.aggregate(pipeline).to_list(length=100)
            
            # Get user info
            user = await db.users_collection.find_one({"_id": ObjectId(user_id)})
            
            return {
                "user_info": {
                    "user_id": user_id,
                    "name": f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
                    "email": user.get('email', ''),
                    "role": user.get('role', '')
                } if user else {"user_id": user_id},
                "time_range": time_range,
                "activity_summary": {
                    "total_actions": sum(item["action_count"] for item in user_activity),
                    "days_active": len(user_activity),
                    "unique_actions": len(set(action for item in user_activity for action in item.get("unique_actions", [])))
                },
                "daily_activity": user_activity,
                "generated_at": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting user activity audit: {e}")
            raise

    @staticmethod
    async def _parse_time_range(time_range: str) -> Dict[str, datetime]:
        """Parse time range string into date filter"""
        now = datetime.now()

        if time_range == "1d":
            start_date = now - timedelta(days=1)
        elif time_range == "7d":
            start_date = now - timedelta(days=7)
        elif time_range == "30d":
            start_date = now - timedelta(days=30)
        elif time_range == "90d":
            start_date = now - timedelta(days=90)
        elif time_range == "365d":
            start_date = now - timedelta(days=365)
        else:
            start_date = now - timedelta(days=30)  # Default to 30 days

        return {"$gte": start_date}
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
