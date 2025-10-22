from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query, Form, File, UploadFile
from typing import List, Optional
from bson import ObjectId
from models.vehicle import (
    VehicleIn, VehicleOut, VehicleUpdate, VehicleSearch, VehicleWithOwnerOut,
    VehicleCategory, MotorcycleSubType, CarSubType, FuelType, TransmissionType
)
from models.user import UserInDB, UserRole
from utils.user import get_current_user
from services.cloudinary import upload_image
from services.vehicle import VehicleService
from utils.time import utc_now

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


@router.get("/categories", summary="Get available vehicle categories and sub-types")
async def get_vehicle_categories():
    """Returns available categories and sub-types for vehicle selection."""
    return {
        "categories": [
            {
                "value": VehicleCategory.MOTORCYCLE,
                "label": "Motorcycle",
                "sub_types": [
                    {"value": st.value, "label": st.name.replace("_", " ").title()} 
                    for st in MotorcycleSubType
                ]
            },
            {
                "value": VehicleCategory.CAR,
                "label": "Car",
                "sub_types": [
                    {"value": st.value, "label": st.name.replace("_", " ").title()} 
                    for st in CarSubType
                ]
            }
        ],
        "fuel_types": [
            {"value": ft.value, "label": ft.name.title()} 
            for ft in FuelType
        ],
        "transmission_types": [
            {"value": tt.value, "label": tt.name.replace("_", " ").title()} 
            for tt in TransmissionType
        ]
    }


@router.post("/create", response_model=VehicleOut, summary="Register a new vehicle with images")
async def create_vehicle(
    user_id: str = Form(...),
    model: str = Form(...),
    brand: Optional[str] = Form(None),
    year: Optional[int] = Form(None),
    category: str = Form(...),
    sub_type: Optional[str] = Form(None),
    fuel_type: Optional[str] = Form(None),
    transmission: Optional[str] = Form(None),
    history: Optional[str] = Form(None),
    is_primary: bool = Form(False),
    is_active: bool = Form(True),
    mileage_km: int = Form(0),
    registration_number: Optional[str] = Form(None),
    images: Optional[List[UploadFile]] = File(None),
    current_user: UserInDB = Depends(get_current_user),
):
    """
    Create a new vehicle with hierarchical type selection.
    
    category: 'motorcycle' or 'car'
    sub_type: Depends on category selected
      - For motorcycle: sports_bike, superbike, scooter, electric_motorcycle, adventure_bike, cruiser, standard_motorcycle
      - For car: suv, sedan, electric_car, hybrid, van, hatchback, supercar
    """
    # Upload images if provided
    uploaded_urls = []
    if images:
        for img in images:
            url = await upload_image(img, expected_type='vehicle')
            uploaded_urls.append(url)
    
    # Create vehicle data
    try:
        vehicle_in = VehicleIn(
            user_id=ObjectId(user_id),
            model=model,
            brand=brand,
            year=year,
            category=category,
            sub_type=sub_type,
            fuel_type=fuel_type,
            transmission=transmission,
            history=history,
            is_primary=is_primary,
            is_active=is_active,
            mileage_km=mileage_km,
            registration_number=registration_number,
            images=uploaded_urls
        )
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    
    # Convert to dict and add timestamp
    vehicle_dict = vehicle_in.model_dump()
    vehicle_dict["created_at"] = datetime.now(timezone.utc)
    
    # Persist to DB
    return await VehicleService.create_vehicle(vehicle_dict)


@router.get("/all", response_model=List[VehicleOut], summary="Get all user registered vehicles")
async def get_user_vehicles(current_user: UserInDB = Depends(get_current_user)):
    """Get all active vehicles for the current user."""
    search_query = VehicleSearch()
    vehicles = await VehicleService.search_vehicles(
        search=search_query,
        user_id=current_user.id,
    )
    return vehicles


@router.get("/admin/all", response_model=List[VehicleWithOwnerOut], summary="Admin: Get all vehicles in the system (with owner info)")
async def admin_get_all_vehicles(
    skip: int = 0,
    limit: int = 100,
    current_user: UserInDB = Depends(get_current_user)
):
    """Admin endpoint to retrieve all vehicles with owner information."""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Access forbidden: Admins only")
    return await VehicleService.admin_get_all_vehicles_with_owner(skip=skip, limit=limit)


@router.get("/admin/{vehicle_id}", response_model=VehicleWithOwnerOut, summary="Admin: Get a vehicle by ID (with owner info)")
async def admin_get_vehicle_by_id(vehicle_id: str, current_user: UserInDB = Depends(get_current_user)):
    """Admin endpoint to retrieve a specific vehicle with owner information."""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Access forbidden: Admins only")
    return await VehicleService.admin_get_vehicle_with_owner(vehicle_id)


@router.get("/{vehicle_id}", response_model=VehicleOut, summary="Get a vehicle by ID")
async def get_vehicle_by_id(vehicle_id: str, current_user: UserInDB = Depends(get_current_user)):
    """Retrieve a specific vehicle by ID for the current user."""
    return await VehicleService.get_by_id(vehicle_id, current_user.id)


@router.put("/{vehicle_id}", response_model=VehicleOut, summary="Update your vehicle information")
async def update_vehicle(vehicle_id: str, update: VehicleUpdate, current_user: UserInDB = Depends(get_current_user)):
    """Update vehicle information. Only owner or admin can update."""
    return await VehicleService.update_vehicle(vehicle_id, current_user.id, update)


@router.delete("/{vehicle_id}", summary="Delete a registered vehicle")
async def delete_vehicle(vehicle_id: str, current_user: UserInDB = Depends(get_current_user)):
    """Permanently delete a vehicle. Only owner can delete."""
    return await VehicleService.delete_vehicle(vehicle_id, current_user.id)


@router.post("/search", response_model=List[VehicleOut], summary="Search your vehicles with filters and pagination")
async def search_vehicles(
    search: VehicleSearch,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, le=100, description="Maximum number of records to return"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order: 'asc' or 'desc'"),
    current_user: UserInDB = Depends(get_current_user)
):
    """Search vehicles with advanced filtering by category, sub_type, fuel type, transmission, year, and mileage."""
    return await VehicleService.search_vehicles(
        search=search,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order
    )


@router.patch("/{vehicle_id}/deactivate", summary="Soft delete (deactivate) your vehicle")
async def soft_delete_vehicle(vehicle_id: str, current_user: UserInDB = Depends(get_current_user)):
    """Deactivate a vehicle without permanently deleting it."""
    return await VehicleService.update_vehicle(vehicle_id, current_user.id, VehicleUpdate(is_active=False))


@router.patch("/{vehicle_id}/activate", summary="Recover (activate) your previously deactivated vehicle")
async def activate_vehicle(vehicle_id: str, current_user: UserInDB = Depends(get_current_user)):
    """Reactivate a previously deactivated vehicle."""
    return await VehicleService.update_vehicle(vehicle_id, current_user.id, VehicleUpdate(is_active=True))


@router.get("/admin/by-user/{user_id}", response_model=List[VehicleOut], summary="Admin: Get all vehicles of a specific user")
async def get_vehicles_by_user(user_id: str, current_user: UserInDB = Depends(get_current_user)):
    """Admin endpoint to get all vehicles owned by a specific user."""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admins only")
    search_query = VehicleSearch()
    return await VehicleService.search_vehicles(
        search=search_query,
        user_id=ObjectId(user_id)
    )