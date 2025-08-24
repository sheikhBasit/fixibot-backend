from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator, computed_field
from typing import Optional, List
from datetime import datetime, timezone
from bson import ObjectId
from utils.py_object import PyObjectId
from enum import Enum


class FeedbackStatus(str, Enum):
    """Enum representing possible states of feedback."""
    REVIEWED = "reviewed"
    FLAGGED = "flagged"
    RESOLVED = "resolved"
    DELETED = "deleted"
    HIDDEN = "hidden"

    @classmethod
    def editable_statuses(cls) -> List['FeedbackStatus']:
        """Returns statuses that allow content edits."""
        return [cls.REVIEWED, cls.FLAGGED]


class FeedbackModel(BaseModel):
    """Main feedback model with comprehensive validation and metadata."""
    
    id: PyObjectId = Field(
        default_factory=PyObjectId,
        alias="_id",
        description="Unique identifier for the feedback",
        examples=["507f1f77bcf86cd799439011"]
    )
    user_id: PyObjectId = Field(
        ...,
        description="ID of the user who created the feedback",
        examples=["507f1f77bcf86cd799439012"]
    )
    mechanic_id: PyObjectId = Field(
        ...,
        description="ID of the mechanic the feedback is about",
        examples=["507f1f77bcf86cd799439013"]
    )
    service_id: Optional[PyObjectId] = Field(
        default=None,
        description="ID of the related service (if applicable)",
        examples=["507f1f77bcf86cd799439014"]
    )
    ai_service_id: Optional[PyObjectId] = Field(
        default=None,
        description="ID of the related AI service (if applicable)",
        examples=["507f1f77bcf86cd799439015"]
    )
    status: FeedbackStatus = Field(
        default=FeedbackStatus.REVIEWED,
        description="Current status of the feedback",
        examples=["reviewed"]
    )
    title: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Title/summary of the feedback",
        examples=["Great service!"]
    )
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Detailed feedback content",
        examples=["The mechanic was very professional and fixed my car quickly."]
    )
    rating: Optional[float] = Field(
        default=None,
        ge=1,
        le=5,
        description="Numeric rating (1-5 stars)",
        examples=[4.5]
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when feedback was created",
        examples=["2023-01-01T00:00:00Z"]
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when feedback was last updated",
        examples=["2023-01-02T00:00:00Z"]
    )

    # Pydantic v2 configuration
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={ObjectId: str},
        validate_by_name=True,
        json_schema_extra={
            "description": "Complete feedback model with validation and tracking",
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "user_id": "507f1f77bcf86cd799439012",
                "mechanic_id": "507f1f77bcf86cd799439013",
                "service_id": "507f1f77bcf86cd799439014",
                "status": "reviewed",
                "title": "Great service!",
                "description": "The mechanic was very professional and fixed my car quickly.",
                "rating": 4.5,
                "created_at": "2023-01-01T00:00:00Z"
            }
        }
    )

    @computed_field
    @property
    def is_editable(self) -> bool:
        """Whether the feedback content can be edited based on status."""
        return self.status in FeedbackStatus.editable_statuses()

    @computed_field
    @property
    def age_days(self) -> float:
        """Age of the feedback in days."""
        # Ensure both datetimes are timezone-aware for comparison
        now = datetime.now(timezone.utc)
        created_at = self.created_at
        
        # If created_at is naive (no timezone), assume UTC
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        
        return (now - created_at).total_seconds() / 86400

    @field_validator('created_at', 'updated_at', mode='before')
    @classmethod
    def ensure_timezone_aware(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure datetime fields are timezone-aware."""
        if v is not None and v.tzinfo is None:
            # If datetime is naive, assume it's UTC
            return v.replace(tzinfo=timezone.utc)
        return v

    @field_validator('title')
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        """Ensure title meets content guidelines."""
        if v is not None:
            if len(v.strip()) < 5:
                raise ValueError("Title must be at least 5 characters long")
            if len(v) > 100:
                raise ValueError("Title cannot exceed 100 characters")
        return v

    @field_validator('description')
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        """Validate description content."""
        if v is not None:
            if len(v.strip()) < 10:
                raise ValueError("Description must be at least 10 characters long")
            if len(v) > 2000:
                raise ValueError("Description cannot exceed 2000 characters")
        return v

    @model_validator(mode='after')
    def validate_service_reference(self) -> 'FeedbackModel':
        """Ensure at least one service reference exists."""
        if self.service_id is None and self.ai_service_id is None:
            raise ValueError("Feedback must reference either service_id or ai_service_id")
        return self


class FeedbackIn(BaseModel):
    """Input model for creating new feedback."""
    
    user_id: PyObjectId = Field(
        ...,
        description="ID of the user creating the feedback",
        examples=["507f1f77bcf86cd799439012"]
    )
    mechanic_id: PyObjectId = Field(
        ...,
        description="ID of the mechanic the feedback is about",
        examples=["507f1f77bcf86cd799439013"]
    )
    service_id: Optional[PyObjectId] = Field(
        default=None,
        description="ID of the related service (if applicable)",
        examples=["507f1f77bcf86cd799439014"]
    )
    ai_service_id: Optional[PyObjectId] = Field(
        default=None,
        description="ID of the related AI service (if applicable)",
        examples=["507f1f77bcf86cd799439015"]
    )
    status: FeedbackStatus = Field(
        default=FeedbackStatus.REVIEWED,
        description="Initial status of the feedback",
        examples=["reviewed"]
    )
    title: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Title/summary of the feedback",
        examples=["Great service!"]
    )
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Detailed feedback content",
        examples=["The mechanic was very professional and fixed my car quickly."]
    )
    rating: Optional[float] = Field(
        default=None,
        ge=1,
        le=5,
        description="Numeric rating (1-5 stars)",
        examples=[4.5]
    )

    @model_validator(mode='after')
    def validate_initial_data(self) -> 'FeedbackIn':
        """Validate initial feedback submission."""
        if self.rating is None and self.description is None:
            raise ValueError("Feedback must include either rating or description")
            
        if self.status not in [FeedbackStatus.REVIEWED, FeedbackStatus.FLAGGED]:
            raise ValueError("New feedback can only be created with REVIEWED or FLAGGED status")
            
        return self

    class Config:
        json_encoders = {ObjectId: str}
        validate_by_name = True
        json_schema_extra = {
            "description": "Input model for creating new feedback",
            "example": {
                "user_id": "507f1f77bcf86cd799439012",
                "mechanic_id": "507f1f77bcf86cd799439013",
                "service_id": "507f1f77bcf86cd799439014",
                "title": "Great service!",
                "description": "The mechanic was very professional and fixed my car quickly.",
                "rating": 4.5
            }
        }


class FeedbackUpdate(BaseModel):
    """Model for updating existing feedback."""
    
    status: Optional[FeedbackStatus] = Field(
        default=None,
        description="Updated status of the feedback",
        examples=["flagged"]
    )
    title: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Updated title/summary of the feedback",
        examples=["Updated title"]
    )
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Updated feedback content",
        examples=["Updated detailed feedback"]
    )
    rating: Optional[float] = Field(
        default=None,
        ge=1,
        le=5,
        description="Updated numeric rating (1-5 stars)",
        examples=[3.5]
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when feedback was updated",
        examples=["2023-01-02T00:00:00Z"]
    )

    @model_validator(mode='after')
    def validate_update(self) -> 'FeedbackUpdate':
        """Validate feedback update constraints."""
        if self.status in [FeedbackStatus.DELETED, FeedbackStatus.HIDDEN] and (
            self.title is not None or self.description is not None or self.rating is not None
        ):
            raise ValueError("Cannot modify content when changing status to DELETED or HIDDEN")
            
        return self

    class Config:
        json_encoders = {ObjectId: str}
        validate_by_name = True
        json_schema_extra = {
            "description": "Model for updating existing feedback",
            "example": {
                "status": "flagged",
                "description": "Updated detailed feedback",
                "rating": 3.5
            }
        }


class FeedbackOut(BaseModel):
    """Output model for feedback with computed fields."""
    
    id: PyObjectId = Field(
        ...,
        alias="_id",
        description="Unique identifier for the feedback",
        examples=["507f1f77bcf86cd799439011"]
    )
    user_id: PyObjectId = Field(
        ...,
        description="ID of the user who created the feedback",
        examples=["507f1f77bcf86cd799439012"]
    )
    mechanic_id: PyObjectId = Field(
        ...,
        description="ID of the mechanic the feedback is about",
        examples=["507f1f77bcf86cd799439013"]
    )
    service_id: Optional[PyObjectId] = Field(
        default=None,
        description="ID of the related service (if applicable)",
        examples=["507f1f77bcf86cd799439014"]
    )
    ai_service_id: Optional[PyObjectId] = Field(
        default=None,
        description="ID of the related AI service (if applicable)",
        examples=["507f1f77bcf86cd799439015"]
    )
    status: FeedbackStatus = Field(
        ...,
        description="Current status of the feedback",
        examples=["reviewed"]
    )
    title: Optional[str] = Field(
        default=None,
        description="Title/summary of the feedback",
        examples=["Great service!"]
    )
    description: Optional[str] = Field(
        default=None,
        description="Detailed feedback content",
        examples=["The mechanic was very professional and fixed my car quickly."]
    )
    rating: Optional[float] = Field(
        default=None,
        description="Numeric rating (1-5 stars)",
        examples=[4.5]
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when feedback was created",
        examples=["2023-01-01T00:00:00Z"]
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when feedback was last updated",
        examples=["2023-01-02T00:00:00Z"]
    )

    @computed_field
    @property
    def is_editable(self) -> bool:
        """Whether the feedback content can be edited based on status."""
        return self.status in FeedbackStatus.editable_statuses()

    @computed_field
    @property
    def age_days(self) -> float:
        """Age of the feedback in days."""
        # Ensure both datetimes are timezone-aware for comparison
        now = datetime.now(timezone.utc)
        created_at = self.created_at
        
        # If created_at is naive (no timezone), assume UTC
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        
        return (now - created_at).total_seconds() / 86400


    class Config:
        from_attributes = True
        json_encoders = {ObjectId: str}
        validate_by_name = True
        json_schema_extra = {
            "description": "Output model for feedback with computed fields",
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "user_id": "507f1f77bcf86cd799439012",
                "mechanic_id": "507f1f77bcf86cd799439013",
                "service_id": "507f1f77bcf86cd799439014",
                "status": "reviewed",
                "title": "Great service!",
                "description": "The mechanic was very professional and fixed my car quickly.",
                "rating": 4.5,
                "created_at": "2023-01-01T00:00:00Z",
                "is_editable": True,
                "age_days": 2.5
            }
        }


class FeedbackSearch(BaseModel):
    """Model for searching/filtering feedback records."""
    
    user_id: Optional[PyObjectId] = Field(
        default=None,
        description="Filter by user ID",
        examples=["507f1f77bcf86cd799439012"]
    )
    mechanic_id: Optional[PyObjectId] = Field(
        default=None,
        description="Filter by mechanic ID",
        examples=["507f1f77bcf86cd799439013"]
    )
    service_id: Optional[PyObjectId] = Field(
        default=None,
        description="Filter by service ID",
        examples=["507f1f77bcf86cd799439014"]
    )
    ai_service_id: Optional[PyObjectId] = Field(
        default=None,
        description="Filter by AI service ID",
        examples=["507f1f77bcf86cd799439015"]
    )
    status: Optional[FeedbackStatus] = Field(
        default=None,
        description="Filter by status",
        examples=["reviewed"]
    )
    min_rating: Optional[float] = Field(
        default=None,
        ge=1,
        le=5,
        description="Minimum rating to include (1-5)",
        examples=[3.0]
    )
    max_rating: Optional[float] = Field(
        default=None,
        ge=1,
        le=5,
        description="Maximum rating to include (1-5)",
        examples=[5.0]
    )
    date_from: Optional[datetime] = Field(
        default=None,
        description="Earliest creation date to include",
        examples=["2023-01-01T00:00:00Z"]
    )
    date_to: Optional[datetime] = Field(
        default=None,
        description="Latest creation date to include",
        examples=["2023-01-31T00:00:00Z"]
    )

    @model_validator(mode='after')
    def validate_search_params(self) -> 'FeedbackSearch':
        """Validate search parameters."""
        if self.min_rating is not None and self.max_rating is not None and self.min_rating > self.max_rating:
            raise ValueError("min_rating cannot be greater than max_rating")
            
        if self.date_from is not None and self.date_to is not None and self.date_from > self.date_to:
            raise ValueError("date_from cannot be after date_to")
            
        return self

    class Config:
        json_encoders = {ObjectId: str}
        validate_by_name = True
        json_schema_extra = {
            "description": "Model for searching/filtering feedback records",
            "example": {
                "mechanic_id": "507f1f77bcf86cd799439013",
                "min_rating": 4.0,
                "date_from": "2023-01-01T00:00:00Z",
                "date_to": "2023-01-31T00:00:00Z"
            }
        }