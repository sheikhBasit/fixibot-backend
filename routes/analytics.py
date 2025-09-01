# Add to your routes
from fastapi import APIRouter, Depends, HTTPException
from models.user import UserInDB, UserRole
from utils.user import get_current_user
from services.analytics import AnalyticsService

router = APIRouter(prefix="/admin/analytics", tags=["Admin Analytics"])

@router.get("/users")
async def get_user_analytics(
    time_range: str = "7d",
    current_user: UserInDB = Depends(get_current_user)
):
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return await AnalyticsService.get_user_metrics(time_range)

@router.get("/mechanics")
async def get_mechanic_analytics(
    time_range: str = "7d",
    current_user: UserInDB = Depends(get_current_user)
):
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return await AnalyticsService.get_mechanic_metrics(time_range)

@router.get("/services")
async def get_service_analytics(
    time_range: str = "7d",
    current_user: UserInDB = Depends(get_current_user)
):
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return await AnalyticsService.get_service_metrics(time_range)

@router.get("/chats")
async def get_chat_analytics(
    time_range: str = "7d",
    current_user: UserInDB = Depends(get_current_user)
):
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return await AnalyticsService.get_chat_metrics(time_range)

@router.get("/system")
async def get_system_analytics(
    current_user: UserInDB = Depends(get_current_user)
):
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return await AnalyticsService.get_system_metrics()