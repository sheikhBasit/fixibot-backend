from fastapi import APIRouter,  Depends, Query, UploadFile, File
from typing import List, Optional


from models.ai_service import (
    AIServiceIn, AIServiceOut, AIServiceUpdate, AIServiceSearch
)
from models.user import UserInDB
from utils.user import get_current_user
from services.ai_service import AIService as AIServiceLogic

router = APIRouter(prefix="/ai-services", tags=["AI Services"])

# ✅ Create AI service
@router.post("/", response_model=AIServiceOut, summary="Create a new AI-guided service request")
async def create_ai_service(
    service: AIServiceIn,
    current_user: UserInDB = Depends(get_current_user),
    files: Optional[List[UploadFile]] = File(None),
):
    return await AIServiceLogic.create(service, current_user, files)

# 🔍 Retrieve AI service
@router.get("/{service_id}", response_model=AIServiceOut, summary="Get AI service by ID")
async def get_ai_service(service_id: str, current_user: UserInDB = Depends(get_current_user)):
    return await AIServiceLogic.get_by_id(service_id)

# 🛠️ Update AI service
@router.put("/{service_id}", response_model=AIServiceOut, summary="Update existing AI service")
async def update_ai_service(
    service_id: str,
    update: AIServiceUpdate,
    current_user: UserInDB = Depends(get_current_user),
    files: Optional[List[UploadFile]] = File(None),
):
    return await AIServiceLogic.update(service_id, update, current_user, files)

# 🗑️ Delete AI service
@router.delete("/{service_id}", summary="Delete an AI service", status_code=204)
async def delete_ai_service(service_id: str, current_user: UserInDB = Depends(get_current_user)):
    await AIServiceLogic.delete(service_id, current_user)
    return

# 🔎 Search AI services
@router.post("/search", response_model=List[AIServiceOut], summary="Search AI services with filters")
async def search_ai_services(
    search: AIServiceSearch,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100),
    current_user: UserInDB = Depends(get_current_user),
):
    return await AIServiceLogic.search(search, skip, limit)

# 🔐 Admin-only endpoints
@router.get("/admin/all", response_model=List[AIServiceOut], summary="Admin: List all AI services")
async def admin_list_ai_services(current_user: UserInDB = Depends(get_current_user)):
    return await AIServiceLogic.admin_get_all(current_user)

@router.get("/admin/by-user/{user_id}", response_model=List[AIServiceOut],
            summary="Admin: List AI services for a user")
async def admin_list_services_by_user(user_id: str, current_user: UserInDB = Depends(get_current_user)):
    return await AIServiceLogic.admin_get_by_user(user_id, current_user)