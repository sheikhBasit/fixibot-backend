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


class VehicleType(str, Enum):
    """Enum representing different types of vehicles."""
    CAR = "car"
    BIKE = "bike"
    TRUCK = "truck"
    VAN = "van"
    SUV = "suv"
    BUS = "bus"
    OTHER = "other"

    @classmethod
    def motorized_types(cls) -> List['VehicleType']:
        """Vehicle types that typically have engines."""
        return [cls.CAR, cls.TRUCK, cls.VAN, cls.SUV, cls.BUS]


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
            if v < 1886:  # First car was patented in 1886
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
    type: Annotated[
        VehicleType,
        Field(
            ...,
            description="Type of vehicle",
            examples=["car"]
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
        if self.type == VehicleType.BIKE and self.transmission == TransmissionType.AUTOMATIC:
            raise ValueError("Bikes typically don't have automatic transmissions")
        
        if self.type in VehicleType.motorized_types() and self.fuel_type is None:
            raise ValueError("Motorized vehicles must specify fuel type")
            
            
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
                "type": "car",
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
        Field(
            ...,
            description="ID of the user who owns this vehicle"
        )
    ]
    model: Annotated[
        str,
        Field(
            ...,
            min_length=2,
            max_length=50,
            description="Vehicle model name"
        )
    ]
    brand: Annotated[
        Optional[str],
        Field(
            None,
            min_length=2,
            max_length=50,
            description="Vehicle brand/manufacturer"
        )
    ]
    year: Annotated[
        Optional[int],
        Field(
            None,
            ge=1886,
            le=datetime.now().year + 1,
            description="Manufacturing year"
        )
    ]
    type: Annotated[
        VehicleType,
        Field(
            ...,
            description="Type of vehicle"
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
            description="Maintenance and accident history"
        )
    ]
    images: Annotated[
        List[str],
        Field(
            default_factory=list,
            max_length=10,
            description="List of image URLs for the vehicle"
        )
    ]
    registration_number: Annotated[
        Optional[str],
        Field(
            None,
            min_length=5,
            max_length=20,
            description="Official registration/license plate number"
        )
    ]
    mileage_km: Annotated[
        int,
        Field(
            default=0,
            ge=0,
            description="Current mileage in kilometers"
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
    @field_validator('year')
    @classmethod
    def validate_year(cls, v: Optional[int]) -> Optional[int]:
        return cls._validate_year(v) 
    @model_validator(mode='after')
    def validate_new_vehicle(self) -> 'VehicleIn':
        """Additional validations for new vehicle creation."""
        if self.type in VehicleType.motorized_types() and self.fuel_type is None:
            raise ValueError("Motorized vehicles must specify fuel type")
            
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
                "type": "car",
                "fuel_type": "petrol",
                "mileage_km": 50000
            }
        }
    )


class VehicleUpdate(BaseVehicleModel):
    """Model for updating vehicle information."""
    model: Annotated[
        Optional[str],
        Field(
            None,
            min_length=2,
            max_length=50,
            description="Updated model name"
        )
    ]
    brand: Annotated[
        Optional[str],
        Field(
            None,
            min_length=2,
            max_length=50,
            description="Updated brand name"
        )
    ]
    year: Annotated[
        Optional[int],
        Field(
            None,
            ge=1886,
            le=datetime.now().year + 1,
            description="Updated manufacturing year"
        )
    ]
    type: Annotated[
        Optional[VehicleType],
        Field(
            None,
            description="Updated vehicle type"
        )
    ]
    fuel_type: Annotated[
        Optional[FuelType],
        Field(
            None,
            description="Updated fuel type"
        )
    ]
    transmission: Annotated[
        Optional[TransmissionType],
        Field(
            None,
            description="Updated transmission type"
        )
    ]
    history: Annotated[
        Optional[str],
        Field(
            None,
            max_length=2000,
            description="Updated maintenance history"
        )
    ]
    images: Annotated[
        Optional[List[str]],
        Field(
            None,
            max_length=10,
            description="Updated list of image URLs"
        )
    ]
    registration_number: Annotated[
        Optional[str],
        Field(
            None,
            min_length=5,
            max_length=20,
            description="Updated registration number"
        )
    ]
    mileage_km: Annotated[
        Optional[int],
        Field(
            None,
            ge=0,
            description="Updated mileage in kilometers"
        )
    ]
    is_primary: Annotated[
        Optional[bool],
        Field(
            None,
            description="Updated primary vehicle status"
        )
    ]
    is_active: Annotated[
        Optional[bool],
        Field(
            None,
            description="Updated active status"
        )
    ]
    @field_validator('year')
    @classmethod
    def validate_year(cls, v: Optional[int]) -> Optional[int]:
        return cls._validate_year(v) 
    @model_validator(mode='after')
    def validate_update(self) -> 'VehicleUpdate':
        """Ensure updates maintain data consistency."""
        if self.mileage_km is not None and self.mileage_km > 500000:
            raise ValueError("Mileage seems unusually high, please verify")
            
        if self.type is not None and self.type == VehicleType.BIKE and self.transmission == TransmissionType.AUTOMATIC:
            raise ValueError("Bikes typically don't have automatic transmissions")
            
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


class VehicleOut(VehicleIn):
    """Output model for vehicle information."""
    id: Annotated[
        PyObjectId,
        Field(
            ...,
            alias="_id",
            description="Unique vehicle identifier"
        )
    ]
    created_at: Annotated[
        datetime,
        Field(
            ...,
            description="Timestamp when vehicle was added"
        )
    ]

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

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "user_id": "507f1f77bcf86cd799439012",
                "model": "Corolla",
                "brand": "Toyota",
                "year": 2020,
                "created_at": "2023-01-01T00:00:00Z",
                "display_name": "Toyota Corolla 2020"
            }
        }
    )


class VehicleSearch(BaseModel):
    """Model for searching/filtering vehicles."""
    user_id: Annotated[
        Optional[PyObjectId],
        Field(
            None,
            description="Filter by owner user ID"
        )
    ]
    brand: Annotated[
        Optional[str],
        Field(
            None,
            min_length=2,
            description="Filter by vehicle brand"
        )
    ]
    model: Annotated[
        Optional[str],
        Field(
            None,
            min_length=2,
            description="Filter by vehicle model"
        )
    ]
    type: Annotated[
        Optional[VehicleType],
        Field(
            None,
            description="Filter by vehicle type"
        )
    ]
    fuel_type: Annotated[
        Optional[FuelType],
        Field(
            None,
            description="Filter by fuel type"
        )
    ]
    transmission: Annotated[
        Optional[TransmissionType],
        Field(
            None,
            description="Filter by transmission type"
        )
    ]
    year_from: Annotated[
        Optional[int],
        Field(
            None,
            ge=1886,
            description="Filter by minimum manufacturing year"
        )
    ]
    year_to: Annotated[
        Optional[int],
        Field(
            None,
            le=datetime.now().year + 1,
            description="Filter by maximum manufacturing year"
        )
    ]
    is_primary: Annotated[
        Optional[bool],
        Field(
            None,
            description="Filter by primary vehicle status"
        )
    ]
    is_active: Annotated[
        Optional[bool],
        Field(
            True,
            description="Filter by active status"
        )
    ]
    mileage_min: Annotated[
        Optional[int],
        Field(
            None,
            ge=0,
            description="Filter by minimum mileage"
        )
    ]
    mileage_max: Annotated[
        Optional[int],
        Field(
            None,
            ge=0,
            description="Filter by maximum mileage"
        )
    ]

    @model_validator(mode='after')
    def validate_search_params(self) -> 'VehicleSearch':
        """Validate search parameter combinations."""
        if self.year_from is not None and self.year_to is not None and self.year_from > self.year_to:
            raise ValueError("year_from cannot be greater than year_to")
            
        if self.mileage_min is not None and self.mileage_max is not None and self.mileage_min > self.mileage_max:
            raise ValueError("mileage_min cannot be greater than mileage_max")
            
        return self

    model_config = ConfigDict(
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "brand": "Toyota",
                "type": "car",
                "year_from": 2015,
                "year_to": 2020,
                "mileage_max": 100000
            }
        }
    )