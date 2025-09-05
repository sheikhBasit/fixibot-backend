from bson import ObjectId
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List
from models.mechanic_service import (
    MechanicServiceIn,
    MechanicServiceOut,
    MechanicServiceUpdate,
    MechanicServiceSearch
)
from models.user import UserInDB, UserRole
from services.mechanic_service import MechanicService
from utils.user import get_current_user

router = APIRouter(prefix="/mechanic-services", tags=["Mechanic Services"])


@router.post("/", response_model=MechanicServiceOut, summary="Request a new mechanic service")
async def create_mechanic_service(
    service: MechanicServiceIn,
    current_user: UserInDB = Depends(get_current_user)
):
    return await MechanicService.create(service)

@router.get("/user/my-services", response_model=List[MechanicServiceOut], summary="Get current user's service history")
async def get_my_mechanic_services(
    skip: int = Query(0, ge=0, description="Records to skip"),
    limit: int = Query(50, le=100, description="Records per page"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: int = Query(-1, description="Sort order (1 for ascending, -1 for descending)"),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Get the service history for the currently authenticated user with pagination and sorting.
    """
    return await MechanicService.get_by_current_user(
        str(current_user.id), 
        skip, 
        limit, 
        sort_by, 
        sort_order
    )

@router.get("/{service_id}", response_model=MechanicServiceOut, summary="Get mechanic service by ID")
async def get_mechanic_service_by_id(
    service_id: str,
    current_user: UserInDB = Depends(get_current_user)
):
    return await MechanicService.get_by_id(service_id)


@router.put("/{service_id}", response_model=MechanicServiceOut, summary="Update mechanic service details")
async def update_mechanic_service(
    service_id: str,
    update: MechanicServiceUpdate,
    current_user: UserInDB = Depends(get_current_user)
):
    return await MechanicService.update(service_id, update)


@router.delete("/{service_id}", summary="Delete a mechanic service")
async def delete_mechanic_service(
    service_id: str,
    current_user: UserInDB = Depends(get_current_user)
):
    return await MechanicService.delete(service_id)


@router.post("/search", response_model=List[MechanicServiceOut], summary="Search mechanic services with filters")
async def search_mechanic_services(
    search: MechanicServiceSearch,
    skip: int = Query(0, ge=0, description="Records to skip"),
    limit: int = Query(10, le=100, description="Records per page"),
    current_user: UserInDB = Depends(get_current_user)
):
    return await MechanicService.search(search=search, skip=skip, limit=limit)


@router.get("/admin/all", response_model=List[MechanicServiceOut], summary="Admin: View all mechanic services")
async def get_all_mechanic_services_admin(current_user: UserInDB = Depends(get_current_user)):
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return await MechanicService.get_all_admin()


@router.get("/admin/by-user/{user_id}", response_model=List[MechanicServiceOut], summary="Admin: View services by user")
async def get_services_by_user_admin(user_id: str, current_user: UserInDB = Depends(get_current_user)):
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return await MechanicService.get_by_user_admin(user_id)


