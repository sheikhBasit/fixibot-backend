from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator, computed_field
from typing import Optional, List
from bson import ObjectId
from utils.py_object import PyObjectId

from datetime import datetime, timezone, timedelta
from models.feedback import FeedbackModel


class ServiceStatus(str, Enum):
    """Enum representing possible states of a mechanic service."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    @classmethod
    def valid_transitions(cls, current_status: 'ServiceStatus') -> List['ServiceStatus']:
        """Define valid status transitions."""
        transitions = {
            cls.PENDING: [cls.IN_PROGRESS, cls.CANCELLED],
            cls.IN_PROGRESS: [cls.COMPLETED, cls.CANCELLED],
        }
        return transitions.get(current_status, [])


class ServiceType(str, Enum):
    """Enum representing types of mechanic services."""
    REPAIR = "repair"
    MAINTENANCE = "maintenance"
    DIAGNOSTIC = "diagnostic"
    INSPECTION = "inspection"
    EMERGENCY = "emergency"
    OTHER = "other"

    @classmethod
    def cost_required_types(cls) -> List['ServiceType']:
        """Service types that typically require cost estimation."""
        return [cls.REPAIR, cls.MAINTENANCE, cls.EMERGENCY]


class MechanicServiceBase(BaseModel):
    """Base model for mechanic services with shared fields and validations."""
    
    user_id: PyObjectId = Field(
        ...,
        description="ID of the user requesting the service",
        examples=["507f1f77bcf86cd799439011"]
    )
    mechanic_id: PyObjectId = Field(
        ...,
        description="ID of the mechanic assigned to the service",
        examples=["507f1f77bcf86cd799439012"]
    )
    vehicle_id: PyObjectId = Field(
        ...,
        description="ID of the vehicle being serviced",
        examples=["507f1f77bcf86cd799439013"]
    )
    issue_description: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Detailed description of the service issue",
        examples=["Engine making strange knocking sounds when accelerating"]
    )
    service_type: ServiceType = Field(
        default=ServiceType.REPAIR,
        description="Type of service being requested",
        examples=["repair"]
    )
    service_cost: Optional[float] = Field(
        default=None,
        ge=0,
        description="Estimated or actual cost of the service",
        examples=[199.99]
    )
    region: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Geographic region where service is performed",
        examples=["Northwest"]
    )
    estimated_time: Optional[str] = Field(
        default=None,
        description="Estimated time to complete the service (e.g., '2 hours', '1-2 days')",
        examples=["3 hours"]
    )
    status: ServiceStatus = Field(
        default=ServiceStatus.PENDING,
        description="Current status of the service",
        examples=["pending"]
    )
    images: List[str] = Field(
        default_factory=list,
        description="List of image URLs documenting the service issue",
        examples=[["https://example.com/image1.jpg"]]
    )

    @field_validator('estimated_time')
    @classmethod
    def validate_estimated_time(cls, v: Optional[str]) -> Optional[str]:
        """Validate the estimated time format."""
        if v is not None:
            if not any(unit in v.lower() for unit in ['hour', 'day', 'minute', 'week']):
                raise ValueError("Estimated time must include time unit (e.g., 'hours', 'days')")
        return v

    @field_validator('images')
    @classmethod
    def validate_images(cls, v: List[str]) -> List[str]:
        """Validate the images list."""
        if len(v) > 10:
            raise ValueError("Cannot have more than 10 images")
        return v

    @model_validator(mode='after')
    def validate_service_cost_requirement(self) -> 'MechanicServiceBase':
        """Validate that certain service types have cost estimates."""
        if (self.service_type in ServiceType.cost_required_types() and 
            self.service_cost is None and 
            self.status != ServiceStatus.CANCELLED):
            raise ValueError(f"Service type '{self.service_type}' requires cost estimation")
        return self

    class Config:
        json_encoders = {ObjectId: str}
        validate_by_name = True
        json_schema_extra = {
            "description": "Base model for mechanic services with shared fields",
            "example": {
                "user_id": "507f1f77bcf86cd799439011",
                "mechanic_id": "507f1f77bcf86cd799439012",
                "vehicle_id": "507f1f77bcf86cd799439013",
                "issue_description": "Engine making strange knocking sounds",
                "service_type": "repair",
                "service_cost": 199.99,
                "estimated_time": "3 hours",
                "status": "pending"
            }
        }


class MechanicServiceIn(MechanicServiceBase):
    """Input model for creating new mechanic services with additional validations."""
    
    @model_validator(mode='after')
    def validate_new_service(self) -> 'MechanicServiceIn':
        """Additional validations for new service requests."""
        if self.status not in [ServiceStatus.PENDING, ServiceStatus.IN_PROGRESS]:
            raise ValueError("New services can only be created with PENDING or IN_PROGRESS status")
        return self


class MechanicServiceOut(MechanicServiceBase):
    """Output model for mechanic services with additional metadata and computed fields."""
    
    id: PyObjectId = Field(
        ...,
        alias="_id",
        description="Unique identifier for the service",
        examples=["507f1f77bcf86cd799439014"]
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the service was created",
        examples=["2023-01-01T00:00:00Z"]
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when the service was last updated",
        examples=["2023-01-02T00:00:00Z"]
    )
    feedback: Optional[FeedbackModel] = Field(
        default=None,
        description="Feedback associated with this service (if available)"
    )

    @computed_field
    @property
    def is_active(self) -> bool:
        """Whether the service is currently active (not completed or cancelled)."""
        return self.status not in {ServiceStatus.COMPLETED, ServiceStatus.CANCELLED}

    @computed_field
    @property
    def processing_time(self) -> Optional[timedelta]:
        """Calculate the time taken to process the service if completed."""
        if self.status == ServiceStatus.COMPLETED and self.updated_at:
            return self.updated_at - self.created_at
        return None

    class Config:
        from_attributes = True
        json_encoders = {ObjectId: str}
        validate_by_name = True
        json_schema_extra = {
            "description": "Output model for mechanic services with computed fields",
            "example": {
                "_id": "507f1f77bcf86cd799439014",
                "user_id": "507f1f77bcf86cd799439011",
                "mechanic_id": "507f1f77bcf86cd799439012",
                "vehicle_id": "507f1f77bcf86cd799439013",
                "issue_description": "Engine making strange knocking sounds",
                "service_type": "repair",
                "service_cost": 199.99,
                "estimated_time": "3 hours",
                "status": "pending",
                "created_at": "2023-01-01T00:00:00Z",
                "is_active": True
            }
        }


class MechanicServiceUpdate(BaseModel):
    """Model for updating mechanic service records with validation."""
    
    issue_description: Optional[str] = Field(
        default=None,
        min_length=10,
        max_length=2000,
        description="Updated description of the service issue",
        examples=["Updated description of engine issue"]
    )
    service_type: Optional[ServiceType] = Field(
        default=None,
        description="Updated type of service",
        examples=["maintenance"]
    )
    service_cost: Optional[float] = Field(
        default=None,
        ge=0,
        description="Updated cost of the service",
        examples=[249.99]
    )
    region: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Updated service region",
        examples=["Southwest"]
    )
    estimated_time: Optional[str] = Field(
        default=None,
        description="Updated estimated completion time",
        examples=["4 hours"]
    )
    status: Optional[ServiceStatus] = Field(
        default=None,
        description="Updated status of the service",
        examples=["in_progress"]
    )
    images: Optional[List[str]] = Field(
        default=None,
        description="Updated list of image URLs",
        examples=[["https://example.com/image2.jpg"]]
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of this update",
        examples=["2023-01-03T00:00:00Z"]
    )

    @model_validator(mode='after')
    def validate_status_transition(self) -> 'MechanicServiceUpdate':
        """Validate status transitions are logical."""
        if self.status is not None and self.status == ServiceStatus.COMPLETED and self.service_cost is None:
            raise ValueError("Cannot mark service as COMPLETED without service cost")
        return self

    class Config:
        json_encoders = {ObjectId: str}
        validate_by_name = True
        json_schema_extra = {
            "description": "Model for updating mechanic service records",
            "example": {
                "status": "in_progress",
                "service_cost": 249.99,
                "estimated_time": "4 hours"
            }
        }


class MechanicServiceSearch(BaseModel):
    """Model for searching/filtering mechanic service records."""
    
    user_id: Optional[PyObjectId] = Field(
        default=None,
        description="Filter by user ID",
        examples=["507f1f77bcf86cd799439011"]
    )
    mechanic_id: Optional[PyObjectId] = Field(
        default=None,
        description="Filter by mechanic ID",
        examples=["507f1f77bcf86cd799439012"]
    )
    status: Optional[ServiceStatus] = Field(
        default=None,
        description="Filter by service status",
        examples=["pending"]
    )
    service_type: Optional[ServiceType] = Field(
        default=None,
        description="Filter by service type",
        examples=["repair"]
    )
    region: Optional[str] = Field(
        default=None,
        description="Filter by service region",
        examples=["Northwest"]
    )
    date_from: Optional[datetime] = Field(
        default=None,
        description="Filter services created after this date",
        examples=["2023-01-01T00:00:00Z"]
    )
    date_to: Optional[datetime] = Field(
        default=None,
        description="Filter services created before this date",
        examples=["2023-01-31T00:00:00Z"]
    )

    @model_validator(mode='after')
    def validate_date_range(self) -> 'MechanicServiceSearch':
        """Validate that date ranges are logical."""
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must be before date_to")
        return self

    class Config:
        json_encoders = {ObjectId: str}
        validate_by_name = True
        json_schema_extra = {
            "description": "Model for searching mechanic service records",
            "example": {
                "mechanic_id": "507f1f77bcf86cd799439012",
                "status": "completed",
                "date_from": "2023-01-01T00:00:00Z"
            }
        }