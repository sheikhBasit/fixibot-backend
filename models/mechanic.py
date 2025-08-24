from datetime import time
from bson import ObjectId
from pydantic import (
    BaseModel, 
    Field, 
    EmailStr, 
    field_validator,
    model_validator,
    computed_field,
    ConfigDict
)
from typing import Optional, List, Annotated
from enum import Enum
from datetime import datetime
from utils.py_object import PyObjectId



class ExpertiseEnum(str, Enum):
    """Enum representing mechanic's areas of expertise."""
    ENGINE = "engine"
    ELECTRICAL = "electrical"
    BODYWORK = "bodywork"
    TRANSMISSION = "transmission"
    BRAKES = "brakes"
    SUSPENSION = "suspension"
    AIR_CONDITIONING = "air_conditioning"
    DIAGNOSTICS = "diagnostics"
    OIL_CHANGE = "oil_change"
    TIRE_REPAIR = "tire_repair"
    EXHAUST_SYSTEM = "exhaust_system"
    BATTERY_REPLACEMENT = "battery_replacement"
    RADIATOR_REPAIR = "radiator_repair"
    FUEL_SYSTEM = "fuel_system"
    ELECTRONICS = "electronics"
    PAINTING = "painting"

    @classmethod
    def premium_services(cls) -> List['ExpertiseEnum']:
        """Identify services that typically command higher rates."""
        return [cls.ENGINE, cls.TRANSMISSION, cls.ELECTRONICS, cls.PAINTING]


class WeekdayEnum(str, Enum):
    """Enum representing days of the week."""
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class WorkingHours(BaseModel):
    """Model representing a mechanic's working hours."""
    start_time: Annotated[
        str,
        Field(
            ...,
            pattern=r"^\d{2}:\d{2}$",
            description="Start time in HH:MM format (24-hour)",
            examples=["09:00"]
        )
    ]
    end_time: Annotated[
        str,
        Field(
            ...,
            pattern=r"^\d{2}:\d{2}$",
            description="End time in HH:MM format (24-hour)",
            examples=["18:00"]
        )
    ]

    @field_validator('end_time')
    @classmethod
    def validate_time_range(cls, v: str, info) -> str:  # Change parameter type to str
        """Ensure end time is after start time."""
        if 'start_time' in info.data and v <= info.data['start_time']:
            raise ValueError('End time must be after start time')
        return v

    @computed_field
    @property
    def duration_hours(self) -> float:
        """Calculate working duration in hours."""
        # Parse string times to calculate duration
        start_h, start_m = map(int, self.start_time.split(':'))
        end_h, end_m = map(int, self.end_time.split(':'))
        return (end_h - start_h) + (end_m - start_m) / 60



class MechanicBase(BaseModel):
    """Base model containing shared mechanic fields and validations."""
    first_name: Annotated[
        str,
        Field(
            ...,
            min_length=2,
            max_length=100,
            description="Mechanic's first name",
            examples=["Ali"]
        )
    ]
    last_name: Annotated[
        str,
        Field(
            ...,
            min_length=2,
            max_length=100,
            description="Mechanic's last name",
            examples=["Khan"]
        )
    ]
    cnic: Annotated[
        str,
        Field(
            ...,
            min_length=13,
            max_length=15,
            pattern=r"^\d{5}-\d{7}-\d{1}$|^\d{13,15}$",
            description="CNIC in either 35202-1234567-1 or 3520212345671 format",
            examples=["35202-1234567-1"]
        )
    ]
    phone_number: Annotated[
        str,
        Field(
            ...,
            min_length=7,
            max_length=15,
            pattern=r"^[\d\s\+\-\(\)]+$",
            description="Phone number in international format",
            examples=["+923001234567"]
        )
    ]
    email: Annotated[
        Optional[EmailStr],
        Field(
            None,
            description="Mechanic's email address",
            examples=["mechanic@example.com"]
        )
    ]
    expertise: Annotated[
        List[ExpertiseEnum],
        Field(
            ...,
            min_length=1,
            description="List of mechanic's areas of expertise",
            examples=[["engine", "electrical"]]
        )
    ]
    province: Annotated[
        str,
        Field(
            ...,
            min_length=2,
            max_length=50,
            description="Province where mechanic operates",
            examples=["Punjab"]
        )
    ]
    city: Annotated[
        str,
        Field(
            ...,
            min_length=2,
            max_length=50,
            description="City where mechanic operates",
            examples=["Lahore"]
        )
    ]
    address: Annotated[
        str,
        Field(
            ...,
            min_length=5,
            max_length=200,
            description="Detailed workshop address",
            examples=["123 Main Street, Gulberg"]
        )
    ]
    latitude: Annotated[
        float,
        Field(
            ...,
            ge=-90,
            le=90,
            description="Geographic latitude of workshop",
            examples=[31.5204]
        )
    ]
    longitude: Annotated[
        float,
        Field(
            ...,
            ge=-180,
            le=180,
            description="Geographic longitude of workshop",
            examples=[74.3587]
        )
    ]
    location: Annotated[
        Optional[dict],
        Field(
            None,
            description="GeoJSON location point for spatial queries",
            examples=[{"type": "Point", "coordinates": [74.3587, 31.5204]}]
        )
    ]
    years_of_experience: Annotated[
        int,
        Field(
            0,
            ge=0,
            le=50,
            description="Years of professional experience",
            examples=[5]
        )
    ]
    working_days: Annotated[
        List[WeekdayEnum],
        Field(
            default_factory=list,
            description="Days when mechanic is available",
            examples=[["monday", "tuesday", "wednesday"]]
        )
    ]
    working_hours: Annotated[
        Optional[WorkingHours],
        Field(
            None,
            description="Daily working hours"
        )
    ]
    @model_validator(mode='after')
    def validate_location_data(self) -> 'MechanicBase':
        """Generate GeoJSON location from latitude/longitude."""
        if self.latitude is not None and self.longitude is not None:
            self.location = {
                "type": "Point",
                "coordinates": [self.longitude, self.latitude]  # GeoJSON: [long, lat]
            }
        return self
    @field_validator("email", "province", "city", "address", mode="before")
    @classmethod
    def normalize_text_fields(cls, v: Optional[str]) -> Optional[str]:
        """Normalize text fields to lowercase."""
        return v.lower() if v else v

    @field_validator("expertise")
    @classmethod
    def validate_expertise(cls, v: List[ExpertiseEnum]) -> List[ExpertiseEnum]:
        """Ensure at least one expertise is provided."""
        if not v:
            raise ValueError("At least one expertise is required")
        return sorted(list(set(v)))  # Remove duplicates and sort

    @model_validator(mode='after')
    def validate_working_days_hours(self) -> 'MechanicBase':
        """Ensure working hours are provided if working days are specified."""
        if self.working_days and not self.working_hours:
            raise ValueError("Working hours must be specified when providing working days")
        return self


class MechanicRegistration(MechanicBase):
    """Model for mechanic registration with additional verification fields."""
    cnic_front: Annotated[
        Optional[str],
        Field(
            None,
            description="URL to CNIC front image",
            examples=["https://example.com/cnic_front.jpg"]
        )
    ]
    cnic_back: Annotated[
        Optional[str],
        Field(
            None,
            description="URL to CNIC back image",
            examples=["https://example.com/cnic_back.jpg"]
        )
    ]
    profile_picture: Annotated[
        Optional[str],
        Field(
            None,
            description="URL to profile picture",
            examples=["https://example.com/profile.jpg"]
        )
    ]
    workshop_name: Annotated[
        Optional[str],
        Field(
            None,
            min_length=2,
            max_length=100,
            description="Name of the workshop",
            examples=["Ali Auto Repair"]
        )
    ]
    is_verified: Annotated[
        bool,
        Field(
            False,
            description="Whether the mechanic has been verified by admin"
        )
    ]
    is_available: Annotated[
        bool,
        Field(
            True,
            description="Current availability status"
        )
    ]

    @field_validator("workshop_name", mode="before")
    @classmethod
    def normalize_workshop_name(cls, v: Optional[str]) -> Optional[str]:
        """Normalize workshop name."""
        return v.lower() if v else v

    # @model_validator(mode='after')
    # def validate_verification_requirements(self) -> 'MechanicRegistration':
    #     """Ensure verification documents are provided."""
    #     if not self.is_verified and (not self.cnic_front or not self.cnic_back):
    #         raise ValueError("CNIC images are required for verification")
    #     return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "first_name": "Ahmed",
                "last_name": "Ali",
                "cnic": "35202-1234567-1",
                "phone_number": "+923001234567",
                "email": "ahmed@example.com",
                "expertise": ["engine", "electrical"],
                "province": "Punjab",
                "city": "Lahore",
                "address": "Street 123, Model Town",
                "latitude": 31.5204,
                "longitude": 74.3587,
                "cnic_front": "https://example.com/cnic_front.jpg",
                "cnic_back": "https://example.com/cnic_back.jpg",
                "profile_picture": "https://example.com/profile.jpg",
                "workshop_name": "ali auto repair",
                "years_of_experience": 5,
                "is_verified": False,
                "is_available": True,
                "working_days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                "working_hours": {"start_time": "09:00", "end_time": "18:00"}
            }
        }
    )


class MechanicSearchParams(BaseModel):
    """Model for mechanic search parameters."""
    city: Annotated[
        str,
        Field(
            ...,
            min_length=2,
            description="City to search in",
            examples=["Lahore"]
        )
    ]
    latitude: Annotated[
        Optional[float],
        Field(
            None,
            ge=-90,
            le=90,
            description="Latitude for proximity search"
        )
    ]
    longitude: Annotated[
        Optional[float],
        Field(
            None,
            ge=-180,
            le=180,
            description="Longitude for proximity search"
        )
    ]
    max_distance_km: Annotated[
        Optional[float],
        Field(
            None,
            gt=0,
            le=100,
            description="Maximum search radius in kilometers",
            examples=[10]
        )
    ]
    expertise: Annotated[
        Optional[List[ExpertiseEnum]],
        Field(
            None,
            description="Filter by specific expertise",
            examples=[["engine", "electrical"]]
        )
    ]
    min_years_experience: Annotated[
        Optional[int],
        Field(
            0,
            ge=0,
            le=50,
            description="Minimum years of experience",
            examples=[5]
        )
    ]

    @model_validator(mode='after')
    def validate_location_params(self) -> 'MechanicSearchParams':
        """Ensure location parameters are provided together."""
        if any([self.latitude, self.longitude, self.max_distance_km]) and not all([self.latitude, self.longitude, self.max_distance_km]):
            raise ValueError("All location parameters (latitude, longitude, max_distance_km) must be provided together")
        return self


class MechanicIn(MechanicRegistration):
    """Input model for creating mechanics with additional business logic."""
    @model_validator(mode='after')
    def validate_new_mechanic(self) -> 'MechanicIn':
        """Additional validations for new mechanic registrations."""
        if self.is_verified:
            raise ValueError("New mechanics cannot be created as verified")
        return self


class MechanicUpdate(BaseModel):
    """Model for updating mechanic information."""
    first_name: Annotated[
        Optional[str],
        Field(
            None,
            min_length=2,
            max_length=100,
            description="Updated first name"
        )
    ]
    last_name: Annotated[
        Optional[str],
        Field(
            None,
            min_length=2,
            max_length=100,
            description="Updated last name"
        )
    ]
    phone_number: Annotated[
        Optional[str],
        Field(
            None,
            min_length=7,
            max_length=15,
            pattern=r"^[\d\s\+\-\(\)]+$",
            description="Updated phone number"
        )
    ]
    email: Annotated[
        Optional[EmailStr],
        Field(
            None,
            description="Updated email address"
        )
    ]
    expertise: Annotated[
        Optional[List[ExpertiseEnum]],
        Field(
            None,
            min_length=1,
            description="Updated areas of expertise"
        )
    ]
    province: Annotated[
        Optional[str],
        Field(
            None,
            min_length=2,
            max_length=50,
            description="Updated province"
        )
    ]
    city: Annotated[
        Optional[str],
        Field(
            None,
            min_length=2,
            max_length=50,
            description="Updated city"
        )
    ]
    address: Annotated[
        Optional[str],
        Field(
            None,
            min_length=5,
            max_length=200,
            description="Updated address"
        )
    ]
    latitude: Annotated[
        Optional[float],
        Field(
            None,
            ge=-90,
            le=90,
            description="Updated latitude"
        )
    ]
    longitude: Annotated[
        Optional[float],
        Field(
            None,
            ge=-180,
            le=180,
            description="Updated longitude"
        )
    ]
    cnic_front: Annotated[
        Optional[str],
        Field(
            None,
            description="Updated CNIC front image URL"
        )
    ]
    cnic_back: Annotated[
        Optional[str],
        Field(
            None,
            description="Updated CNIC back image URL"
        )
    ]
    profile_picture: Annotated[
        Optional[str],
        Field(
            None,
            description="Updated profile picture URL"
        )
    ]
    workshop_name: Annotated[
        Optional[str],
        Field(
            None,
            min_length=2,
            max_length=100,
            description="Updated workshop name"
        )
    ]
    years_of_experience: Annotated[
        Optional[int],
        Field(
            None,
            ge=0,
            le=50,
            description="Updated years of experience"
        )
    ]
    is_verified: Annotated[
        Optional[bool],
        Field(
            None,
            description="Updated verification status"
        )
    ]
    is_available: Annotated[
        Optional[bool],
        Field(
            None,
            description="Updated availability status"
        )
    ]
    working_days: Annotated[
        Optional[List[WeekdayEnum]],
        Field(
            None,
            description="Updated working days"
        )
    ]
    working_hours: Annotated[
        Optional[WorkingHours],
        Field(
            None,
            description="Updated working hours"
        )
    ]
    @model_validator(mode='before')
    @classmethod
    def convert_empty_strings_to_none(cls, values):
        """Convert empty strings to None to preserve existing values."""
        for field_name, value in values.items():
            if isinstance(value, str) and value.strip() == "":
                values[field_name] = None
        return values
    
    model_config = ConfigDict(
        extra='forbid'
    )
    # @model_validator(mode='after')
    # def validate_update(self) -> 'MechanicUpdate':
    #     """Ensure verification requirements are met."""
    #     # Only validate if is_verified is explicitly set to True
    #     if hasattr(self, 'is_verified') and self.is_verified is True:
    #         # Check if CNIC images are provided (either in update or already exist)
    #         has_cnic_front = hasattr(self, 'cnic_front') and self.cnic_front is not None
    #         has_cnic_back = hasattr(self, 'cnic_back') and self.cnic_back is not None
            
    #         if not (has_cnic_front or has_cnic_back):
    #             # We can't check existing CNIC images here, so we'll check in the service
    #             # Just note that validation might fail later if images don't exist
    #             pass
        
    #     return self


class MechanicOut(MechanicRegistration):
    """Output model for mechanics with additional computed fields."""
    id: Annotated[
        PyObjectId,
        Field(
            ...,
            alias="_id",
            description="Unique mechanic identifier",
            examples=["507f1f77bcf86cd799439011"]
        )
    ]
    average_rating: Annotated[
        Optional[float],
        Field(
            None,
            ge=0,
            le=5,
            description="Average rating from feedbacks",
            examples=[4.5]
        )
    ]
    total_feedbacks: Annotated[
        int,
        Field(
            0,
            ge=0,
            description="Total number of feedbacks received",
            examples=[15]
        )
    ]
    created_at: Annotated[
        Optional[datetime],
        Field(
            ...,
            description="Timestamp when mechanic was registered",
            examples=["2023-01-01T00:00:00Z"]
        )
    ]
    updated_at: Annotated[
        Optional[datetime],
        Field(
            None,
            description="Timestamp when mechanic was last updated",
            examples=["2023-01-02T00:00:00Z"]
        )
    ]

    @computed_field
    @property
    def full_name(self) -> str:
        """Combine first and last name."""
        return f"{self.first_name} {self.last_name}"

    @computed_field
    @property
    def premium_services(self) -> List[ExpertiseEnum]:
        """List of premium services offered by this mechanic."""
        return [e for e in self.expertise if e in ExpertiseEnum.premium_services()]

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "first_name": "Ahmed",
                "last_name": "Ali",
                "cnic": "35202-1234567-1",
                "phone_number": "+923001234567",
                "email": "ahmed@example.com",
                "expertise": ["engine", "electrical"],
                "province": "Punjab",
                "city": "Lahore",
                "address": "Street 123, Model Town",
                "latitude": 31.5204,
                "longitude": 74.3587,
                "profile_picture": "https://example.com/profile.jpg",
                "workshop_name": "ali auto repair",
                "years_of_experience": 5,
                "is_verified": True,
                "is_available": True,
                "working_days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                "working_hours": {"start_time": "09:00", "end_time": "18:00"},
                "average_rating": 4.5,
                "total_feedbacks": 15,
                "created_at": "2023-01-01T00:00:00Z",
                "full_name": "Ahmed Ali"
            }
        }
    )

