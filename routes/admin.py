from datetime import datetime
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from models.user import UserInDB, UserRole
from services.admin import AdminService
from services.mechanics import MechanicService
from utils.user import get_current_user
from services.users import UserService
from config import settings
import shutil
import os

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.patch("/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    is_active: bool,
    current_user: UserInDB = Depends(get_current_user)
):
    """Admin: Activate or deactivate a user account"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return await AdminService.update_user_status(user_id, is_active)

# @router.patch("/users/{user_id}/role")
# async def update_user_role(
#     user_id: str,
#     new_role: UserRole,
#     current_user: UserInDB = Depends(get_current_user)
# ):
#     """Admin: Change a user's role"""
#     if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
#         raise HTTPException(status_code=403, detail="Admin access required")
    
#     return await UserService.update_user_role(user_id, new_role)
# @router.get("/mechanics/pending")
# async def get_pending_mechanics(
#     skip: int = 0,
#     limit: int = 50,
#     current_user: UserInDB = Depends(get_current_user)
# ):
#     """Admin: Get mechanics pending verification"""
#     if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
#         raise HTTPException(status_code=403, detail="Admin access required")
    
#     return await MechanicService.get_pending_verification(skip=skip, limit=limit)

# @router.get("/mechanics/unverified")
# async def get_unverified_mechanics(
#     skip: int = 0,
#     limit: int = 50,
#     current_user: UserInDB = Depends(get_current_user)
# ):
#     """Admin: Get all unverified mechanics"""
#     if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
#         raise HTTPException(status_code=403, detail="Admin access required")
    
#     return await MechanicService.get_unverified_mechanics(skip=skip, limit=limit)

@router.get("/search")
async def admin_global_search(
    query: str,
    entity_type: str = "all",  # all, users, mechanics, vehicles, services
    limit: int = 20,
    current_user: UserInDB = Depends(get_current_user)
):
    """Admin: Unified search across all entities"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # You'll need to implement this service function
    return await AdminService.global_search(query, entity_type, limit)


# from services.vectorstore import process_pdf_with_images
# from services.vector_cache import VectorCache

# @router.post("/system/vectorstore/rebuild")
# async def rebuild_vectorstore(
#     force: bool = False,
#     current_user: UserInDB = Depends(get_current_user)
# ):
#     """Admin: Force rebuild of AI knowledge base vectorstore"""
#     if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
#         raise HTTPException(status_code=403, detail="Admin access required")
    
#     try:
#         # Clear cache and reprocess
#         cache = VectorCache(settings.VECTOR_CACHE_DIR)
#         cache_key = cache.get_cache_key(settings.KNOWLEDGE_BASE_PDF)
#         cache.clear_cache(cache_key)
        
#         # Reprocess PDF
#         vectorstore, image_data_store = process_pdf_with_images(
#             settings.KNOWLEDGE_BASE_PDF,
#             cache_dir=settings.VECTOR_CACHE_DIR,
#             force_reprocess=True
#         )
        
#         # Update app state
#         request.app.state.vectorstore = vectorstore
#         request.app.state.image_data_store = image_data_store
        
#         return {"status": "success", "message": "Vectorstore rebuilt successfully"}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to rebuild vectorstore: {str(e)}")


@router.get("/system/logs")
async def get_system_logs(
    lines: int = 100,
    log_type: str = "app",  # app, error, access
    current_user: UserInDB = Depends(get_current_user)
):
    """Admin: Retrieve recent application logs"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # You'll need to implement this service function
    return await AdminService.get_recent_logs(lines, log_type)


# @router.get("/content/knowledge-base")
# async def get_knowledge_base_status(
#     current_user: UserInDB = Depends(get_current_user)
# ):
#     """Admin: Check status of AI knowledge base"""
#     if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
#         raise HTTPException(status_code=403, detail="Admin access required")
    
#     kb_path = settings.KNOWLEDGE_BASE_PDF
#     exists = os.path.exists(kb_path)
    
#     return {
#         "exists": exists,
#         "path": kb_path,
#         "size": os.path.getsize(kb_path) if exists else 0,
#         "last_modified": os.path.getmtime(kb_path) if exists else None
#     }

# @router.post("/content/knowledge-base")
# async def upload_knowledge_base(
#     file: UploadFile = File(...),
#     current_user: UserInDB = Depends(get_current_user)
# ):
#     """Admin: Upload new knowledge base PDF"""
#     if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
#         raise HTTPException(status_code=403, detail="Admin access required")
    
#     if not file.filename.endswith('.pdf'):
#         raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
#     # Save the file
#     kb_path = settings.KNOWLEDGE_BASE_PDF
#     with open(kb_path, "wb") as buffer:
#         shutil.copyfileobj(file.file, buffer)
    
#     return {"status": "success", "message": "Knowledge base updated successfully"}

@router.get("/overview")
async def get_admin_overview(
    current_user: UserInDB = Depends(get_current_user)
):
    """Admin: Get dashboard overview statistics"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # You'll need to implement this service function
    return await AdminService.get_dashboard_overview()

# Report Routes
@router.get("/reports/users")
async def generate_users_report(
    time_range: str = "30d",
    format: str = "json",
    current_user: UserInDB = Depends(get_current_user)
):
    """Admin: Generate comprehensive users report"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return await AdminService.generate_users_report(time_range, format)

@router.get("/reports/services")
async def generate_services_report(
    time_range: str = "30d",
    format: str = "json",
    current_user: UserInDB = Depends(get_current_user)
):
    """Admin: Generate comprehensive services report"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return await AdminService.generate_services_report(time_range, format)

@router.get("/reports/mechanics")
async def generate_mechanics_report(
    time_range: str = "30d",
    format: str = "json",
    current_user: UserInDB = Depends(get_current_user)
):
    """Admin: Generate comprehensive mechanics report"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return await AdminService.generate_mechanics_report(time_range, format)

@router.get("/reports/financial")
async def generate_financial_report(
    time_range: str = "30d",
    format: str = "json",
    current_user: UserInDB = Depends(get_current_user)
):
    """Admin: Generate comprehensive financial report"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return await AdminService.generate_financial_report(time_range, format)

@router.get("/reports/export/{format}")
async def export_report(
    format: str,
    report_type: str,
    time_range: str = "30d",
    current_user: UserInDB = Depends(get_current_user)
):
    """Admin: Export report in various formats"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Generate the appropriate report based on type
    if report_type == "users":
        report_data = await AdminService.generate_users_report(time_range, "json")
    elif report_type == "services":
        report_data = await AdminService.generate_services_report(time_range, "json")
    elif report_type == "mechanics":
        report_data = await AdminService.generate_mechanics_report(time_range, "json")
    elif report_type == "financial":
        report_data = await AdminService.generate_financial_report(time_range, "json")
    else:
        raise HTTPException(status_code=400, detail="Invalid report type")
    
    return await AdminService.export_report(report_data, format)

# Settings Routes
@router.get("/settings")
async def get_system_settings(
    current_user: UserInDB = Depends(get_current_user)
):
    """Admin: Get all system settings"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return await AdminService.get_system_settings()

@router.put("/settings")
async def update_system_settings(
    settings_data: Dict[str, Any],
    current_user: UserInDB = Depends(get_current_user)
):
    """Admin: Update system settings"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    success = await AdminService.update_system_settings(settings_data)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update system settings")
    
    return {"status": "success", "message": "System settings updated successfully"}

@router.get("/settings/email")
async def get_email_settings(
    current_user: UserInDB = Depends(get_current_user)
):
    """Admin: Get email settings"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return await AdminService.get_email_settings()

@router.put("/settings/email")
async def update_email_settings(
    settings_data: Dict[str, Any],
    current_user: UserInDB = Depends(get_current_user)
):
    """Admin: Update email settings"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    success = await AdminService.update_email_settings(settings_data)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update email settings")
    
    return {"status": "success", "message": "Email settings updated successfully"}

@router.get("/settings/notifications")
async def get_notification_settings(
    current_user: UserInDB = Depends(get_current_user)
):
    """Admin: Get notification settings"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return await AdminService.get_notification_settings()

@router.put("/settings/notifications")
async def update_notification_settings(
    settings_data: Dict[str, Any],
    current_user: UserInDB = Depends(get_current_user)
):
    """Admin: Update notification settings"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    success = await AdminService.update_notification_settings(settings_data)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update notification settings")
    
    return {"status": "success", "message": "Notification settings updated successfully"}

# Audit Log Routes
@router.get("/audit/logs")
async def get_audit_logs(
    skip: int = 0,
    limit: int = 50,
    action: Optional[str] = None,
    user_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: UserInDB = Depends(get_current_user)
):
    """Admin: Get audit logs with filtering"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Build filters
    filters = {}
    if action:
        filters["action"] = action
    if user_id:
        filters["user_id"] = user_id
    if start_date or end_date:
        date_filter = {}
        if start_date:
            date_filter["$gte"] = start_date
        if end_date:
            date_filter["$lte"] = end_date
        filters["timestamp"] = date_filter
    
    return await AdminService.get_audit_logs(skip, limit, filters)

@router.get("/audit/logs/{log_id}")
async def get_audit_log(
    log_id: str,
    current_user: UserInDB = Depends(get_current_user)
):
    """Admin: Get specific audit log by ID"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return await AdminService.get_audit_log(log_id)

@router.get("/audit/actions")
async def get_audit_action_stats(
    time_range: str = "7d",
    current_user: UserInDB = Depends(get_current_user)
):
    """Admin: Get audit action statistics"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return await AdminService.get_audit_action_stats(time_range)

@router.get("/audit/users/{user_id}")
async def get_user_activity_audit(
    user_id: str,
    time_range: str = "30d",
    current_user: UserInDB = Depends(get_current_user)
):
    """Admin: Get user activity audit report"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return await AdminService.get_user_activity_audit(user_id, time_range)