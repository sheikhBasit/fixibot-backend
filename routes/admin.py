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