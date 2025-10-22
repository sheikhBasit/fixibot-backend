from typing import List, Optional, Annotated
from pydantic import (
    BaseModel, 
    Field, 
    field_validator, 
    model_validator,
    computed_field,
    ConfigDict
)
from bson import ObjectId
from datetime import datetime, timezone
from utils.py_object import PyObjectId
from enum import Enum


class VehicleCategory(str, Enum):
    """Main vehicle categories."""
    MOTORCYCLE = "motorcycle"
    CAR = "car"


class MotorcycleSubType(str, Enum):
    """Sub-types for motorcycles."""
    SPORTS_BIKE = "sports_bike"
    SUPERBIKE = "superbike"
    SCOOTER = "scooter"
    ELECTRIC_MOTORCYCLE = "electric_motorcycle"
    ADVENTURE_BIKE = "adventure_bike"
    CRUISER = "cruiser"
    STANDARD_MOTORCYCLE = "standard_motorcycle"


class CarSubType(str, Enum):
    """Sub-types for cars."""
    SUV = "suv"
    SEDAN = "sedan"
    ELECTRIC_CAR = "electric_car"
    HYBRID = "hybrid"
    VAN = "van"
    HATCHBACK = "hatchback"
    SUPERCAR = "supercar"


class FuelType(str, Enum):
    """Enum representing different fuel types."""
    PETROL = "petrol"
    DIESEL = "diesel"
    ELECTRIC = "electric"
    HYBRID = "hybrid"
    CNG = "cng"
    LPG = "lpg"
    HYDROGEN = "hydrogen"
    OTHER = "other"

    @classmethod
    def fossil_fuels(cls) -> List['FuelType']:
        """Traditional fuel types."""
        return [cls.PETROL, cls.DIESEL]


class TransmissionType(str, Enum):
    """Enum representing different transmission types."""
    MANUAL = "manual"
    AUTOMATIC = "automatic"
    SEMI_AUTOMATIC = "semi_automatic"
    CVT = "cvt"
    DUAL_CLUTCH = "dual_clutch"
    DIRECT_DRIVE = "direct_drive"  # For electric vehicles
    OTHER = "other"

    @classmethod
    def automatic_types(cls) -> List['TransmissionType']:
        """Automatic transmission variants."""
        return [cls.AUTOMATIC, cls.CVT, cls.DUAL_CLUTCH]


class BaseVehicleModel(BaseModel):
    """Base model containing shared validation logic."""
    
    @classmethod
    def _validate_year(cls, v: Optional[int]) -> Optional[int]:
        """Shared year validation for all models."""
        if v is not None:
            current_year = datetime.now().year
            if v < 1886:
                raise ValueError("Year seems too old for a vehicle")
            if v > current_year + 1:
                raise ValueError("Manufacturing year cannot be in the future")
            if v < 1000 or v > 9999:
                raise ValueError("Year must be exactly 4 digits")
        return v


class VehicleModel(BaseVehicleModel):
    """Core model representing a vehicle with comprehensive details."""
    id: Annotated[
        PyObjectId,
        Field(
            default_factory=PyObjectId,
            alias="_id",
            description="Unique identifier for the vehicle",
            examples=["507f1f77bcf86cd799439011"]
        )
    ]
    user_id: Annotated[
        PyObjectId,
        Field(
            ...,
            description="ID of the user who owns this vehicle",
            examples=["507f1f77bcf86cd799439012"]
        )
    ]
    model: Annotated[
        str,
        Field(
            ...,
            min_length=2,
            max_length=50,
            description="Vehicle model name",
            examples=["Corolla"]
        )
    ]
    brand: Annotated[
        Optional[str],
        Field(
            None,
            min_length=2,
            max_length=50,
            description="Vehicle brand/manufacturer",
            examples=["Toyota"]
        )
    ]
    year: Annotated[
        Optional[int],
        Field(
            None,
            ge=1886,
            le=datetime.now().year + 1,
            description="Manufacturing year",
            examples=[2020]
        )
    ]
    category: Annotated[
        VehicleCategory,
        Field(
            ...,
            description="Main vehicle category (motorcycle or car)",
            examples=["car"]
        )
    ]
    sub_type: Annotated[
        Optional[str],
        Field(
            None,
            description="Vehicle sub-type based on category",
            examples=["sedan"]
        )
    ]
    fuel_type: Annotated[
        Optional[FuelType],
        Field(
            None,
            description="Type of fuel the vehicle uses"
        )
    ]
    transmission: Annotated[
        Optional[TransmissionType],
        Field(
            None,
            description="Type of transmission"
        )
    ]
    history: Annotated[
        Optional[str],
        Field(
            None,
            max_length=2000,
            description="Maintenance and accident history",
            examples=["Regular maintenance at authorized service centers"]
        )
    ]
    images: Annotated[
        List[str],
        Field(
            default_factory=list,
            max_length=10,
            description="List of image URLs for the vehicle",
            examples=[["https://example.com/vehicle1.jpg"]]
        )
    ]
    registration_number: Annotated[
        Optional[str],
        Field(
            None,
            min_length=5,
            max_length=20,
            description="Official registration/license plate number",
            examples=["ABC-1234"]
        )
    ]
    mileage_km: Annotated[
        int,
        Field(
            default=0,
            ge=0,
            description="Current mileage in kilometers",
            examples=[50000]
        )
    ]
    is_primary: Annotated[
        bool,
        Field(
            default=False,
            description="Whether this is the user's primary vehicle"
        )
    ]
    is_active: Annotated[
        bool,
        Field(
            default=True,
            description="Whether this vehicle is currently active"
        )
    ]
    created_at: Annotated[
        datetime,
        Field(
            default_factory=lambda: datetime.now(timezone.utc),
            description="Timestamp when vehicle was added",
            examples=["2023-01-01T00:00:00Z"]
        )
    ]

    @field_validator('images')
    @classmethod
    def validate_images(cls, v: List[str]) -> List[str]:
        """Validate vehicle images."""
        if len(v) > 10:
            raise ValueError("Cannot have more than 10 images")
        return v

    @field_validator('registration_number')
    @classmethod
    def normalize_registration(cls, v: Optional[str]) -> Optional[str]:
        """Normalize registration number format."""
        if v is not None:
            return v.strip().upper()
        return v

    @field_validator('year')
    @classmethod
    def validate_year(cls, v: Optional[int]) -> Optional[int]:
        return cls._validate_year(v)

    @model_validator(mode='after')
    def validate_vehicle_properties(self) -> 'VehicleModel':
        """Validate logical relationships between vehicle properties."""
        # Validate sub_type matches category
        if self.category == VehicleCategory.MOTORCYCLE:
            if self.sub_type and self.sub_type not in [e.value for e in MotorcycleSubType]:
                raise ValueError(f"Invalid motorcycle sub-type: {self.sub_type}")
        elif self.category == VehicleCategory.CAR:
            if self.sub_type and self.sub_type not in [e.value for e in CarSubType]:
                raise ValueError(f"Invalid car sub-type: {self.sub_type}")
        
        # Transmission validation
        if self.category == VehicleCategory.MOTORCYCLE and self.transmission == TransmissionType.AUTOMATIC:
            raise ValueError("Motorcycles typically don't have automatic transmissions")
        
        # Fuel type requirements
        motorized_categories = [VehicleCategory.MOTORCYCLE, VehicleCategory.CAR]
        if self.category in motorized_categories and self.fuel_type is None:
            raise ValueError("Motorized vehicles must specify fuel type")
        
        # Direct drive only for electric vehicles
        if self.transmission == TransmissionType.DIRECT_DRIVE and self.fuel_type != FuelType.ELECTRIC:
            raise ValueError("Direct drive transmission is only for electric vehicles")
            
        return self

    @computed_field
    @property
    def age_years(self) -> Optional[int]:
        """Calculate vehicle age in years."""
        if self.year:
            return datetime.now().year - self.year
        return None

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "description": "Complete vehicle information model",
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "user_id": "507f1f77bcf86cd799439012",
                "model": "Corolla",
                "brand": "Toyota",
                "year": 2020,
                "category": "car",
                "sub_type": "sedan",
                "fuel_type": "petrol",
                "transmission": "automatic",
                "mileage_km": 50000,
                "age_years": 3
            }
        }
    )


class VehicleIn(BaseVehicleModel):
    """Input model for creating new vehicle entries."""
    user_id: Annotated[
        PyObjectId,
        Field(..., description="ID of the user who owns this vehicle")
    ]
    model: Annotated[
        str,
        Field(..., min_length=2, max_length=50, description="Vehicle model name")
    ]
    brand: Annotated[
        Optional[str],
        Field(None, min_length=2, max_length=50, description="Vehicle brand/manufacturer")
    ]
    year: Annotated[
        Optional[int],
        Field(None, ge=1886, le=datetime.now().year + 1, description="Manufacturing year")
    ]
    category: Annotated[
        VehicleCategory,
        Field(..., description="Main vehicle category (motorcycle or car)")
    ]
    sub_type: Annotated[
        Optional[str],
        Field(None, description="Vehicle sub-type based on category")
    ]
    fuel_type: Annotated[
        Optional[FuelType],
        Field(None, description="Type of fuel the vehicle uses")
    ]
    transmission: Annotated[
        Optional[TransmissionType],
        Field(None, description="Type of transmission")
    ]
    history: Annotated[
        Optional[str],
        Field(None, max_length=2000, description="Maintenance and accident history")
    ]
    images: Annotated[
        List[str],
        Field(default_factory=list, max_length=10, description="List of image URLs for the vehicle")
    ]
    registration_number: Annotated[
        Optional[str],
        Field(None, min_length=5, max_length=20, description="Official registration/license plate number")
    ]
    mileage_km: Annotated[
        int,
        Field(default=0, ge=0, description="Current mileage in kilometers")
    ]
    is_primary: Annotated[
        bool,
        Field(default=False, description="Whether this is the user's primary vehicle")
    ]
    is_active: Annotated[
        bool,
        Field(default=True, description="Whether this vehicle is currently active")
    ]

    @field_validator('year')
    @classmethod
    def validate_year(cls, v: Optional[int]) -> Optional[int]:
        return cls._validate_year(v)

    @model_validator(mode='after')
    def validate_new_vehicle(self) -> 'VehicleIn':
        """Additional validations for new vehicle creation."""
        if self.category == VehicleCategory.MOTORCYCLE:
            if self.sub_type and self.sub_type not in [e.value for e in MotorcycleSubType]:
                raise ValueError(f"Invalid motorcycle sub-type: {self.sub_type}")
        elif self.category == VehicleCategory.CAR:
            if self.sub_type and self.sub_type not in [e.value for e in CarSubType]:
                raise ValueError(f"Invalid car sub-type: {self.sub_type}")
        
        if self.fuel_type is None:
            raise ValueError("Fuel type is required")
        
        if self.transmission is None:
            raise ValueError("Transmission type is required")
            
        if self.mileage_km > 500000:
            raise ValueError("Mileage seems unusually high, please verify")
            
        return self

    model_config = ConfigDict(
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "user_id": "507f1f77bcf86cd799439012",
                "model": "Corolla",
                "brand": "Toyota",
                "year": 2020,
                "category": "car",
                "sub_type": "sedan",
                "fuel_type": "petrol",
                "transmission": "automatic",
                "mileage_km": 50000
            }
        }
    )


class VehicleUpdate(BaseVehicleModel):
    """Model for updating vehicle information."""
    model: Annotated[Optional[str], Field(None, min_length=2, max_length=50)]
    brand: Annotated[Optional[str], Field(None, min_length=2, max_length=50)]
    year: Annotated[Optional[int], Field(None, ge=1886, le=datetime.now().year + 1)]
    category: Annotated[Optional[VehicleCategory], Field(None)]
    sub_type: Annotated[Optional[str], Field(None)]
    fuel_type: Annotated[Optional[FuelType], Field(None)]
    transmission: Annotated[Optional[TransmissionType], Field(None)]
    history: Annotated[Optional[str], Field(None, max_length=2000)]
    images: Annotated[Optional[List[str]], Field(None, max_length=10)]
    registration_number: Annotated[Optional[str], Field(None, min_length=5, max_length=20)]
    mileage_km: Annotated[Optional[int], Field(None, ge=0)]
    is_primary: Annotated[Optional[bool], Field(None)]
    is_active: Annotated[Optional[bool], Field(None)]

    @field_validator('year')
    @classmethod
    def validate_year(cls, v: Optional[int]) -> Optional[int]:
        return cls._validate_year(v)

    @model_validator(mode='after')
    def validate_update(self) -> 'VehicleUpdate':
        """Ensure updates maintain data consistency."""
        if self.mileage_km is not None and self.mileage_km > 500000:
            raise ValueError("Mileage seems unusually high, please verify")
        
        if self.category == VehicleCategory.MOTORCYCLE and self.transmission == TransmissionType.AUTOMATIC:
            raise ValueError("Motorcycles typically don't have automatic transmissions")
        
        if self.transmission == TransmissionType.DIRECT_DRIVE and self.fuel_type != FuelType.ELECTRIC:
            raise ValueError("Direct drive transmission is only for electric vehicles")
            
        return self

    model_config = ConfigDict(
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "mileage_km": 55000,
                "is_primary": True,
                "images": ["https://example.com/new_photo.jpg"]
            }
        }
    )


from models.user import UserOut


class VehicleWithOwnerOut(VehicleIn):
    """Output model for vehicle information with owner details (admin only)."""
    id: Annotated[PyObjectId, Field(..., alias="_id")]
    created_at: Annotated[datetime, Field(...)]
    images: Annotated[List[str], Field(...)]
    owner: UserOut

    @computed_field
    @property
    def display_name(self) -> str:
        """Generate a display-friendly vehicle name."""
        parts = []
        if self.brand:
            parts.append(self.brand)
        if self.model:
            parts.append(self.model)
        if self.year:
            parts.append(str(self.year))
        return " ".join(parts) if parts else "Unnamed Vehicle"

    model_config = ConfigDict(from_attributes=True, json_encoders={ObjectId: str})


class VehicleOut(VehicleIn):
    """Output model for vehicle information."""
    id: Annotated[PyObjectId, Field(..., alias="_id")]
    created_at: Annotated[datetime, Field(...)]
    images: Annotated[List[str], Field(...)]

    @computed_field
    @property
    def display_name(self) -> str:
        """Generate a display-friendly vehicle name."""
        parts = []
        if self.brand:
            parts.append(self.brand)
        if self.model:
            parts.append(self.model)
        if self.year:
            parts.append(str(self.year))
        return " ".join(parts) if parts else "Unnamed Vehicle"

    model_config = ConfigDict(from_attributes=True, json_encoders={ObjectId: str})


class VehicleSearch(BaseModel):
    """Model for searching/filtering vehicles."""
    brand: Annotated[Optional[str], Field(None, min_length=2, description="Filter by vehicle brand")]
    model: Annotated[Optional[str], Field(None, min_length=2, description="Filter by vehicle model")]
    category: Annotated[Optional[str], Field(None, description="Filter by vehicle category (motorcycle or car)")]
    sub_type: Annotated[Optional[str], Field(None, description="Filter by vehicle sub-type")]
    fuel_type: Annotated[Optional[str], Field(None, description="Filter by fuel type")]
    transmission: Annotated[Optional[str], Field(None, description="Filter by transmission type")]
    year_from: Annotated[Optional[int], Field(None, ge=1886, description="Filter by minimum manufacturing year")]
    year_to: Annotated[Optional[int], Field(None, le=datetime.now().year + 1, description="Filter by maximum manufacturing year")]
    is_primary: Annotated[Optional[bool], Field(None, description="Filter by primary vehicle status")]
    is_active: Annotated[Optional[bool], Field(None, description="Filter by active status (None = no filter, True = active only, False = inactive only)")]
    mileage_min: Annotated[Optional[int], Field(None, ge=0, description="Filter by minimum mileage")]
    mileage_max: Annotated[Optional[int], Field(None, ge=0, description="Filter by maximum mileage")]

    @model_validator(mode='after')
    def validate_search_params(self) -> 'VehicleSearch':
        """Validate search parameter combinations."""
        if self.year_from is not None and self.year_to is not None and self.year_from > self.year_to:
            raise ValueError("year_from cannot be greater than year_to")
        if self.mileage_min is not None and self.mileage_max is not None and self.mileage_min > self.mileage_max:
            raise ValueError("mileage_min cannot be greater than mileage_max")
        return self

    model_config = ConfigDict(json_encoders={ObjectId: str})