from bson import ObjectId
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List
from models.mechanic_service import (
    MechanicServiceIn,
    MechanicServiceOut,
    MechanicServiceUpdate,
    MechanicServiceSearch,
    MechanicServiceWithUserAndMechanicOut,
    MechanicServiceWithMechanicOut
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


# User: Get current user's mechanic services with mechanic info
@router.get("/user/my-services", response_model=List[MechanicServiceWithMechanicOut], summary="Get current user's service history (with mechanic info)")
async def get_my_mechanic_services(
    skip: int = Query(0, ge=0, description="Records to skip"),
    limit: int = Query(50, le=100, description="Records per page"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: int = Query(-1, description="Sort order (1 for ascending, -1 for descending)"),
    current_user: UserInDB = Depends(get_current_user)
):
    return await MechanicService.get_by_current_user_with_mechanic(
        str(current_user.id), 
        skip, 
        limit, 
        sort_by, 
        sort_order
    )


# User: Get a single mechanic service by ID with mechanic info
@router.get("/{service_id}", response_model=MechanicServiceWithMechanicOut, summary="Get mechanic service by ID (with mechanic info)")
async def get_mechanic_service_by_id(
    service_id: str,
    current_user: UserInDB = Depends(get_current_user)
):  
    return await MechanicService.get_by_id_with_mechanic(service_id, current_user)


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



# Admin: Get all mechanic services with user and mechanic info
@router.get("/admin/all", response_model=List[MechanicServiceWithUserAndMechanicOut], summary="Admin: View all mechanic services (with user and mechanic info)")
async def get_all_mechanic_services_admin(current_user: UserInDB = Depends(get_current_user)):
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return await MechanicService.get_all_admin_with_user_and_mechanic()

# Admin: Get a single mechanic service with user and mechanic info
@router.get("/admin/{service_id}", response_model=MechanicServiceWithUserAndMechanicOut, summary="Admin: Get mechanic service by ID (with user and mechanic info)")
async def get_mechanic_service_admin_by_id(service_id: str, current_user: UserInDB = Depends(get_current_user)):
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return await MechanicService.get_by_id_admin_with_user_and_mechanic(service_id)


@router.get("/admin/by-user/{user_id}", response_model=List[MechanicServiceOut], summary="Admin: View services by user")
async def get_services_by_user_admin(user_id: str, current_user: UserInDB = Depends(get_current_user)):
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return await MechanicService.get_by_user_admin(user_id)


@router.get("/admin/by-mechanic/{mechanic_id}", response_model=List[MechanicServiceWithMechanicOut], summary="Admin: View services by mechanic")
async def get_services_by_mechanic_admin(mechanic_id: str, current_user: UserInDB = Depends(get_current_user)):
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return await MechanicService.get_by_mechanic_id(mechanic_id, current_user)


@router.get("/admin/by-vehicle/{vehicle_id}", response_model=List[MechanicServiceWithMechanicOut], summary="Admin: View services by vehicle")
async def get_services_by_vehicle_admin(vehicle_id: str, current_user: UserInDB = Depends(get_current_user)):
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return await MechanicService.get_by_vehicle_id(vehicle_id, current_user)


