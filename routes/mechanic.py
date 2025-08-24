from datetime import datetime, time
import re
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Form
from fastapi.security import OAuth2PasswordBearer
from typing import Optional, List, Union
from models.mechanic import MechanicIn, MechanicOut, MechanicUpdate, ExpertiseEnum, WeekdayEnum, WorkingHours
from models.user import UserInDB
from services.mechanics import MechanicService
from services.cloudinary import upload_image
from utils.user import get_current_user
import logging

router = APIRouter(prefix="/mechanics", tags=["Mechanics"])
logger = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

@router.post("/register", response_model=MechanicOut, status_code=status.HTTP_201_CREATED)
async def register_mechanic(
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: Optional[str] = Form(None),
    phone_number: str = Form(...),
    cnic: str = Form(...),
    province: str = Form(...),
    city: str = Form(...),
    address: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    expertise: List[ExpertiseEnum] = Form(...),
    years_of_experience: int = Form(...),
    profile_picture: Optional[Union[UploadFile,str]] = File(None),
    cnic_front: Optional[Union[UploadFile,str]] = File(None),  # Make CNIC optional
    cnic_back: Optional[Union[UploadFile,str]] = File(None), 
    workshop_name: Optional[str] = Form(None),
    working_days: Optional[List[WeekdayEnum]] = Form(None),
    start_time: Optional[str] = Form(None),
    end_time: Optional[str] = Form(None),
):
    """Register a new mechanic."""
    try:
        # Handle file upload if present
        profile_pic_url = None
        if profile_picture:
            profile_pic_url = await upload_image(profile_picture,expected_type='user')
        cnic_front_url = None
        if cnic_front:
            cnic_front_url = await upload_image(cnic_front, expected_type='cnic')
        
        cnic_back_url = None
        if cnic_back:
            cnic_back_url = await upload_image(cnic_back, expected_type='cnic')

        working_hours = None
        if start_time and end_time:
            working_hours = WorkingHours(start_time=start_time, end_time=end_time)
        # Create mechanic data model
        mechanic_data = MechanicIn(
            first_name=first_name,
            last_name=last_name,
            email=email.lower() if email else None,
            phone_number=phone_number,
            cnic=cnic,
            province=province.lower(),
            city=city.lower(),
            address=address,
            latitude=latitude,
            longitude=longitude,
            expertise=expertise,
            years_of_experience=years_of_experience,
            profile_picture=profile_pic_url,
            cnic_front=cnic_front_url,
            cnic_back=cnic_back_url,
            workshop_name=workshop_name.lower() if workshop_name else None,
            working_days=working_days or [],
            working_hours=working_hours
        )
        
        # Create mechanic through service
        return await MechanicService.create_mechanic(mechanic_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering mechanic: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error registering mechanic"
        )

@router.patch("/me", response_model=MechanicOut)
async def update_mechanic_profile(
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    phone_number: Optional[str] = Form(None),
    province: Optional[str] = Form(None),
    city: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    expertise: Optional[List[ExpertiseEnum]] = Form(None),
    years_of_experience: Optional[int] = Form(None),
    workshop_name: Optional[str] = Form(None),
    is_available: Optional[bool] = Form(None),
    working_days: Optional[List[WeekdayEnum]] = Form(None),
    start_time: Optional[str] = Form(None),
    end_time: Optional[str] = Form(None),
    profile_picture: Optional[Union[UploadFile,str]] = File(None),
    cnic_front: Optional[Union[UploadFile,str]] = File(None),
    cnic_back: Optional[Union[UploadFile,str]] = File(None),
    current_user: UserInDB = Depends(get_current_user),
):
    """Update current mechanic's profile (partial update)."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Validate time format if provided
    if start_time or end_time:
        time_pattern = r"^\d{2}:\d{2}$"
        if start_time and not re.match(time_pattern, start_time):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_time must be in HH:MM format (e.g., '09:00')"
            )
        if end_time and not re.match(time_pattern, end_time):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="end_time must be in HH:MM format (e.g., '18:00')"
            )
    
    
    # Handle file uploads if present
    profile_pic_url = None
    if profile_picture:
        profile_pic_url = await upload_image(profile_picture, expected_type='user')
    
    cnic_front_url = None
    if cnic_front:
        cnic_front_url = await upload_image(cnic_front, expected_type='cnic')
    
    cnic_back_url = None
    if cnic_back:
        cnic_back_url = await upload_image(cnic_back, expected_type='cnic')
    
    working_hours = None
    if start_time and end_time:
        try:
            # WorkingHours now expects strings, not time objects
            working_hours = WorkingHours(start_time=start_time, end_time=end_time)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid working hours: {str(e)}"
            )
    
    # Convert empty strings to None to preserve existing values
    def clean_form_value(value, value_type=None):
        """
        Clean incoming form value.
        - Converts empty strings or 'null'/'undefined' to None
        - Optionally casts to specified type if value is valid
        """
        if value in ["", "null", "undefined", None]:
            return None
        if value_type:
            try:
                return value_type(value)
            except (ValueError, TypeError):
                return None
        return value

    
    # Create update data model - convert empty strings to None
    update_data = MechanicUpdate(
        first_name=clean_form_value(first_name),
        last_name=clean_form_value(last_name),
        email=clean_form_value(email.lower() if email else None),
        phone_number=clean_form_value(phone_number),
        province=clean_form_value(province.lower() if province else None),
        city=clean_form_value(city.lower() if city else None),
        address=clean_form_value(address),
        latitude=latitude,
        longitude=longitude,
        expertise=expertise,
        years_of_experience=years_of_experience,
        workshop_name=clean_form_value(workshop_name.lower() if workshop_name else None),
        is_available=is_available,
        working_days=working_days,
        working_hours=working_hours,
        profile_picture=profile_pic_url,
        cnic_front=cnic_front_url,
        cnic_back=cnic_back_url
    )
    
    return await MechanicService.update_mechanic(str(current_user.id), update_data)

@router.patch("/{mechanic_id}", response_model=MechanicOut)
async def update_mechanic_admin(
    mechanic_id: str,
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    phone_number: Optional[str] = Form(None),
    province: Optional[str] = Form(None),
    city: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    expertise: Optional[List[ExpertiseEnum]] = Form(None),
    years_of_experience: Optional[int] = Form(None),
    workshop_name: Optional[str]=Form(None),
    is_verified: Optional[bool] = Form(None),
    is_available: Optional[bool] = Form(None),
    working_days: Optional[List[WeekdayEnum]] = Form(None),
    start_time: Optional[str] = Form(None),
    end_time: Optional[str] = Form(None),
    profile_picture: Optional[Union[UploadFile,str]] = File(None),
    cnic_front: Optional[Union[UploadFile,str]] = File(None),
    cnic_back: Optional[Union[UploadFile,str]] = File(None),
    current_user: UserInDB = Depends(get_current_user),
):
    """Update any mechanic's profile (admin only, partial update)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    # Validate time format if provided
    if start_time or end_time:
        time_pattern = r"^\d{2}:\d{2}$"
        if start_time and not re.match(time_pattern, start_time):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_time must be in HH:MM format (e.g., '09:00')"
            )
        if end_time and not re.match(time_pattern, end_time):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="end_time must be in HH:MM format (e.g., '18:00')"
            )
    
    
    # Handle file uploads if present
    profile_pic_url = None
    if profile_picture:
        profile_pic_url = await upload_image(profile_picture, expected_type='user')
    
    cnic_front_url = None
    if cnic_front:
        cnic_front_url = await upload_image(cnic_front, expected_type='cnic')
    
    cnic_back_url = None
    if cnic_back:
        cnic_back_url = await upload_image(cnic_back, expected_type='cnic')
    
    # Handle working hours if provided
    working_hours = None
    if start_time and end_time:
        try:
            # WorkingHours now expects strings, not time objects
            working_hours = WorkingHours(start_time=start_time, end_time=end_time)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid working hours: {str(e)}"
            )
    
    # Convert empty strings to None to preserve existing values
    def clean_form_value(value, value_type=None):
        """
        Clean incoming form value.
        - Converts empty strings or 'null'/'undefined' to None
        - Optionally casts to specified type if value is valid
        """
        if value in ["", "null", "undefined", None]:
            return None
        if value_type:
            try:
                return value_type(value)
            except (ValueError, TypeError):
                return None
        return value

    
    # Create update data model - convert empty strings to None
    update_data = MechanicUpdate(
        first_name=clean_form_value(first_name),
        last_name=clean_form_value(last_name),
        email=clean_form_value(email.lower() if email else None),
        phone_number=clean_form_value(phone_number),
        province=clean_form_value(province.lower() if province else None),
        city=clean_form_value(city.lower() if city else None),
        address=clean_form_value(address),
        latitude=latitude,
        longitude=longitude,
        expertise=expertise,
        years_of_experience=clean_form_value(years_of_experience, int), 
        workshop_name=clean_form_value(workshop_name.lower() if workshop_name else None),
        is_verified=is_verified,
        is_available=is_available,
        working_days=working_days,
        working_hours=working_hours,
        profile_picture=profile_pic_url,
        cnic_front=cnic_front_url,
        cnic_back=cnic_back_url
    )
    
    return await MechanicService.update_mechanic(mechanic_id, update_data)

@router.get("/{mechanic_id}", response_model=MechanicOut)
async def get_mechanic(mechanic_id: str):
    """Get mechanic by ID."""
    return await MechanicService.get_mechanic_by_id(mechanic_id)



@router.get("/", response_model=List[MechanicOut])
async def list_mechanics(
    skip: int = 0,
    limit: int = 100,
    verified: Optional[bool] = None,
    available: Optional[bool] = None,
    city: Optional[str] = None,
    current_user: UserInDB = Depends(get_current_user)
):
    """List mechanics with optional filters."""
    return await MechanicService.list_mechanics(
        skip=skip,
        limit=limit,
        verified=verified,
        available=available,
        city=city.lower() if city else None
    )

@router.get("/search/nearby", response_model=List[MechanicOut])
async def search_nearby_mechanics(
    city: str,
    expertise: Optional[str] = Query(None, description="Comma-separated list of expertise"),
    min_experience: int = 0,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    max_distance_km: float = 10,
    current_user: UserInDB = Depends(get_current_user)
):
    """Search mechanics by location and expertise."""
    # Convert comma-separated expertise string to list
    expertise_list = None
    if expertise:
        try:
            expertise_list = [ExpertiseEnum(item.strip()) for item in expertise.split(",")]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid expertise value provided"
            )
    
    return await MechanicService.search_mechanics(
        city=city.lower(),
        expertise=expertise_list,
        min_experience=min_experience,
        latitude=latitude,
        longitude=longitude,
        max_distance_km=max_distance_km
    )

@router.post("/{mechanic_id}/verify", status_code=status.HTTP_204_NO_CONTENT)
async def verify_mechanic(
    mechanic_id: str,
    verify: bool = True,
    current_user: UserInDB = Depends(get_current_user)
):
    """Verify or unverify a mechanic (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    success = await MechanicService.verify_mechanic(mechanic_id, verify)
    if not success:
        raise HTTPException(status_code=404, detail="Mechanic not found")