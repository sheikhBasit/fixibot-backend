from pydantic import BaseModel, Field, field_validator, model_validator, computed_field
from typing import Optional, List, Dict
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from utils.py_object import PyObjectId
from models.feedback import FeedbackModel
from enum import Enum


class AIServiceStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"
    ESCALATED = "escalated"

    @classmethod
    def get_transitions(cls, current_status: 'AIServiceStatus') -> List['AIServiceStatus']:
        """Define valid status transitions"""
        transitions = {
            cls.PENDING: [cls.IN_PROGRESS, cls.CANCELLED, cls.ESCALATED],
            cls.IN_PROGRESS: [cls.RESOLVED, cls.ESCALATED, cls.CANCELLED],
            cls.ESCALATED: [cls.RESOLVED, cls.CANCELLED],
        }
        return transitions.get(current_status, [])


class AIServiceResolvedStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    USER_CANCELLED = "user_cancelled"
    INCOMPLETE = "incomplete"
    UNNECESSARY = "unnecessary"


class PriorityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class AIServiceModel(BaseModel):
    """Represents an AI service request with comprehensive tracking and validation."""
    
    id: PyObjectId = Field(
        default_factory=PyObjectId, 
        alias="_id",
        description="Unique identifier for the service request",
        examples=["507f1f77bcf86cd799439011"]
    )
    user_id: PyObjectId = Field(
        ...,
        description="ID of the user who created the service request",
        examples=["507f1f77bcf86cd799439012"]
    )
    mechanic_id: PyObjectId = Field(
        ...,
        description="ID of the mechanic assigned to the service request",
        examples=["507f1f77bcf86cd799439013"]
    )
    vehicle_id: PyObjectId = Field(
        ...,
        description="ID of the vehicle associated with the service request",
        examples=["507f1f77bcf86cd799439014"]
    )
    status: AIServiceStatus = Field(
        default=AIServiceStatus.PENDING,
        description="Current status of the service request",
        examples=["pending"]
    )
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Detailed description of the issue",
        examples=["My car is making a strange noise when I brake"]
    )
    request_time: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the request was created",
        examples=["2023-01-01T00:00:00Z"]
    )
    resolved_status: Optional[AIServiceResolvedStatus] = Field(
        default=None,
        description="Final status if the request is resolved",
        examples=["success"]
    )
    resolved_time: Optional[datetime] = Field(
        default=None,
        description="Timestamp when the request was resolved",
        examples=["2023-01-02T00:00:00Z"]
    )
    issue_subject: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Brief subject/title of the issue",
        examples=["Brake System Noise"]
    )
    priority: PriorityLevel = Field(
        default=PriorityLevel.MEDIUM,
        description="Priority level of the service request",
        examples=["medium"]
    )
    attachments: List[str] = Field(
        default_factory=list,
        description="List of attachment URLs or identifiers",
        examples=[["https://example.com/image1.jpg"]]
    )
    chat_bot_history: List[Dict[str, str]] = Field(
        default_factory=list,
        description="History of chatbot interactions for this request",
        examples=[[{"role": "user", "content": "My car won't start"}]]
    )
    feedback: Optional[FeedbackModel] = Field(
        default=None,
        description="User feedback after service completion"
    )

    @computed_field
    @property
    def is_active(self) -> bool:
        """Check if the service request is still active (not resolved or cancelled)."""
        return self.status not in {AIServiceStatus.RESOLVED, AIServiceStatus.CANCELLED}

    @computed_field
    @property
    def duration(self) -> Optional[timedelta]:
        """Calculate the duration from request to resolution if resolved."""
        if self.resolved_time and self.request_time:
            return self.resolved_time - self.request_time
        return None

    @field_validator('attachments')
    @classmethod
    def validate_attachments(cls, v: List[str]) -> List[str]:
        """Validate that attachments list doesn't exceed reasonable limits."""
        if len(v) > 10:
            raise ValueError("Cannot have more than 10 attachments")
        return v

    @field_validator('chat_bot_history')
    @classmethod
    def validate_chat_history(cls, v: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Validate chat history structure."""
        for entry in v:
            if not all(key in entry for key in ('role', 'content')):
                raise ValueError("Chat history entries must have 'role' and 'content' keys")
        return v

    @model_validator(mode='after')
    def validate_resolution_fields(self) -> 'AIServiceModel':
        """Ensure resolved fields are only set when status is resolved."""
        if self.status != AIServiceStatus.RESOLVED and self.resolved_status is not None:
            raise ValueError("resolved_status can only be set when status is 'resolved'")
        
        if self.resolved_time is not None and self.status != AIServiceStatus.RESOLVED:
            raise ValueError("resolved_time can only be set when status is 'resolved'")
            
        if self.status == AIServiceStatus.RESOLVED and self.resolved_status is None:
            raise ValueError("resolved_status must be set when status is 'resolved'")
            
        return self

    class Config:
        from_attributes = True
        json_encoders = {ObjectId: str}
        validate_by_name = True
        json_schema_extra = {
            "description": "Complete AI service request model with validation and tracking",
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "user_id": "507f1f77bcf86cd799439012",
                "mechanic_id": "507f1f77bcf86cd799439013",
                "vehicle_id": "507f1f77bcf86cd799439014",
                "status": "pending",
                "description": "My car is making a strange noise when I brake",
                "request_time": "2023-01-01T00:00:00Z",
                "issue_subject": "Brake System Noise",
                "priority": "medium",
                "attachments": [],
                "chat_bot_history": []
            }
        }


class AIServiceIn(BaseModel):
    """Input model for creating a new AI service request."""
    
    user_id: PyObjectId = Field(
        ...,
        description="ID of the user creating the service request",
        examples=["507f1f77bcf86cd799439012"]
    )
    mechanic_id: PyObjectId = Field(
        ...,
        description="ID of the mechanic assigned to the service request",
        examples=["507f1f77bcf86cd799439013"]
    )
    vehicle_id: PyObjectId = Field(
        ...,
        description="ID of the vehicle associated with the service request",
        examples=["507f1f77bcf86cd799439014"]
    )
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Detailed description of the issue",
        examples=["My car is making a strange noise when I brake"]
    )
    issue_subject: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Brief subject/title of the issue",
        examples=["Brake System Noise"]
    )
    status: AIServiceStatus = Field(
        default=AIServiceStatus.PENDING,
        description="Initial status of the service request (default: pending)",
        examples=["pending"]
    )
    priority: PriorityLevel = Field(
        default=PriorityLevel.MEDIUM,
        description="Priority level of the service request (default: medium)",
        examples=["medium"]
    )
    attachments: List[str] = Field(
        default_factory=list,
        description="List of attachment URLs or identifiers",
        examples=[["https://example.com/image1.jpg"]]
    )
    chat_bot_history: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Initial chatbot interactions for this request",
        examples=[[{"role": "user", "content": "My car won't start"}]]
    )

    @field_validator('status')
    @classmethod
    def validate_initial_status(cls, v: AIServiceStatus) -> AIServiceStatus:
        """Ensure new requests can't be created with certain statuses."""
        if v in {AIServiceStatus.RESOLVED, AIServiceStatus.ESCALATED}:
            raise ValueError("New requests cannot be created with status 'resolved' or 'escalated'")
        return v

    class Config:
        json_encoders = {ObjectId: str}
        validate_by_name = True
        json_schema_extra = {
            "description": "Input model for creating a new AI service request",
            "example": {
                "user_id": "507f1f77bcf86cd799439012",
                "mechanic_id": "507f1f77bcf86cd799439013",
                "vehicle_id": "507f1f77bcf86cd799439014",
                "description": "My car is making a strange noise when I brake",
                "issue_subject": "Brake System Noise",
                "priority": "medium"
            }
        }


class AIServiceUpdate(BaseModel):
    """Model for updating an existing AI service request."""
    
    status: Optional[AIServiceStatus] = Field(
        default=None,
        description="Updated status of the service request",
        examples=["in_progress"]
    )
    priority: Optional[PriorityLevel] = Field(
        default=None,
        description="Updated priority level of the service request",
        examples=["high"]
    )
    resolved_time: Optional[datetime] = Field(
        default=None,
        description="Timestamp when the request was resolved",
        examples=["2023-01-02T00:00:00Z"]
    )
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Updated description of the issue",
        examples=["Updated description of the brake noise"]
    )
    issue_subject: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Updated subject/title of the issue",
        examples=["Updated Brake Issue"]
    )
    attachments: Optional[List[str]] = Field(
        default=None,
        description="Updated list of attachment URLs or identifiers",
        examples=[["https://example.com/image1.jpg", "https://example.com/image2.jpg"]]
    )
    chat_bot_history: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="Updated chatbot interactions for this request",
        examples=[[
            {"role": "user", "content": "My car won't start"},
            {"role": "bot", "content": "Have you checked the battery?"}
        ]]
    )

    @model_validator(mode='after')
    def validate_update_fields(self) -> 'AIServiceUpdate':
        """Ensure logical consistency in updates."""
        if self.resolved_time is not None and (self.status is None or self.status != AIServiceStatus.RESOLVED):
            raise ValueError("Cannot set resolved_time without setting status to 'resolved'")
            
        return self

    class Config:
        json_encoders = {ObjectId: str}
        validate_by_name = True
        json_schema_extra = {
            "description": "Model for updating an existing AI service request",
            "example": {
                "status": "in_progress",
                "priority": "high",
                "description": "Updated description of the brake noise"
            }
        }


class AIServiceOut(BaseModel):
    """Output model for AI service requests, including computed fields."""
    
    id: PyObjectId = Field(
        ...,
        alias="_id",
        description="Unique identifier for the service request",
        examples=["507f1f77bcf86cd799439011"]
    )
    user_id: PyObjectId = Field(
        ...,
        description="ID of the user who created the service request",
        examples=["507f1f77bcf86cd799439012"]
    )
    mechanic_id: PyObjectId = Field(
        ...,
        description="ID of the mechanic assigned to the service request",
        examples=["507f1f77bcf86cd799439013"]
    )
    vehicle_id: PyObjectId = Field(
        ...,
        description="ID of the vehicle associated with the service request",
        examples=["507f1f77bcf86cd799439014"]
    )
    status: str = Field(
        ...,
        description="Current status of the service request",
        examples=["pending"]
    )
    description: Optional[str] = Field(
        default=None,
        description="Detailed description of the issue",
        examples=["My car is making a strange noise when I brake"]
    )
    request_time: datetime = Field(
        ...,
        description="Timestamp when the request was created",
        examples=["2023-01-01T00:00:00Z"]
    )
    resolved_status: Optional[str] = Field(
        default=None,
        description="Final status if the request is resolved",
        examples=["success"]
    )
    resolved_time: Optional[datetime] = Field(
        default=None,
        description="Timestamp when the request was resolved",
        examples=["2023-01-02T00:00:00Z"]
    )
    issue_subject: Optional[str] = Field(
        default=None,
        description="Brief subject/title of the issue",
        examples=["Brake System Noise"]
    )
    priority: Optional[str] = Field(
        default=None,
        description="Priority level of the service request",
        examples=["medium"]
    )
    attachments: Optional[List[str]] = Field(
        default=None,
        description="List of attachment URLs or identifiers",
        examples=[["https://example.com/image1.jpg"]]
    )
    chat_bot_history: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="History of chatbot interactions for this request",
        examples=[[{"role": "user", "content": "My car won't start"}]]
    )
    feedback: Optional[FeedbackModel] = Field(
        default=None,
        description="User feedback after service completion"
    )

    @computed_field
    @property
    def is_active(self) -> bool:
        """Check if the service request is still active (not resolved or cancelled)."""
        return self.status not in {AIServiceStatus.RESOLVED, AIServiceStatus.CANCELLED}

    @computed_field
    @property
    def duration(self) -> Optional[timedelta]:
        """Calculate the duration from request to resolution if resolved."""
        if self.resolved_time and self.request_time:
            return self.resolved_time - self.request_time
        return None

    class Config:
        from_attributes = True
        json_encoders = {ObjectId: str}
        validate_by_name = True
        json_schema_extra = {
            "description": "Output model for AI service requests with computed fields",
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "user_id": "507f1f77bcf86cd799439012",
                "mechanic_id": "507f1f77bcf86cd799439013",
                "vehicle_id": "507f1f77bcf86cd799439014",
                "status": "pending",
                "description": "My car is making a strange noise when I brake",
                "request_time": "2023-01-01T00:00:00Z",
                "issue_subject": "Brake System Noise",
                "priority": "medium",
                "attachments": [],
                "chat_bot_history": [],
                "is_active": True
            }
        }


class AIServiceSearch(BaseModel):
    """Model for searching/filtering AI service requests."""
    
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
    vehicle_id: Optional[PyObjectId] = Field(
        default=None,
        description="Filter by vehicle ID",
        examples=["507f1f77bcf86cd799439014"]
    )
    status: Optional[str] = Field(
        default=None,
        description="Filter by status",
        examples=["pending"]
    )
    priority: Optional[str] = Field(
        default=None,
        description="Filter by priority level",
        examples=["medium"]
    )
    date_from: Optional[datetime] = Field(
        default=None,
        description="Filter requests created after this date",
        examples=["2023-01-01T00:00:00Z"]
    )
    date_to: Optional[datetime] = Field(
        default=None,
        description="Filter requests created before this date",
        examples=["2023-01-31T00:00:00Z"]
    )
    issue_subject: Optional[str] = Field(
        default=None,
        description="Filter by issue subject (partial match)",
        examples=["Brake"]
    )

    @model_validator(mode='after')
    def validate_date_range(self) -> 'AIServiceSearch':
        """Ensure date range is valid if both dates are provided."""
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must be before date_to")
        return self

    class Config:
        json_encoders = {ObjectId: str}
        validate_by_name = True
        json_schema_extra = {
            "description": "Search/filter model for AI service requests",
            "example": {
                "user_id": "507f1f77bcf86cd799439012",
                "status": "pending",
                "date_from": "2023-01-01T00:00:00Z",
                "date_to": "2023-01-31T00:00:00Z"
            }
        }