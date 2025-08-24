from enum import Enum
from typing import Optional, List, Annotated
from datetime import datetime, timezone
from bson import ObjectId
from pydantic import (
    BaseModel, 
    Field, 
    field_validator, 
    model_validator,
    computed_field,
    ConfigDict
)
from utils.py_object import PyObjectId



class SuggestionStatus(str, Enum):
    """Enum representing possible states of user suggestions."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

    @classmethod
    def review_required_statuses(cls) -> List['SuggestionStatus']:
        """Statuses that require admin review."""
        return [cls.PENDING]


class SelfHelpModel(BaseModel):
    """Core model for self-help knowledge base entries."""
    id: Annotated[
        PyObjectId,
        Field(
            default_factory=PyObjectId,
            alias="_id",
            description="Unique identifier for the self-help entry",
            examples=["507f1f77bcf86cd799439011"]
        )
    ]
    question: Annotated[
        str,
        Field(
            ...,
            min_length=10,
            max_length=200,
            description="The question or problem being addressed",
            examples=["How do I check my engine oil level?"]
        )
    ]
    answer: Annotated[
        str,
        Field(
            ...,
            min_length=20,
            max_length=5000,
            description="Detailed solution or answer to the question",
            examples=["To check your engine oil, first ensure the engine is cool..."]
        )
    ]
    tags: Annotated[
        List[str],
        Field(
            default_factory=list,
            max_length=10,
            description="List of tags for categorization",
            examples=[["engine", "maintenance"]]
        )
    ]
    is_active: Annotated[
        bool,
        Field(
            True,
            description="Whether this entry is currently visible to users"
        )
    ]
    created_at: Annotated[
        datetime,
        Field(
            default_factory=lambda: datetime.now(timezone.utc),
            description="Timestamp when entry was created",
            examples=["2023-01-01T00:00:00Z"]
        )
    ]
    updated_at: Annotated[
        Optional[datetime],
        Field(
            None,
            description="Timestamp when entry was last updated",
            examples=["2023-01-02T00:00:00Z"]
        )
    ]

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Normalize and validate tags."""
        if len(v) > 10:
            raise ValueError("Cannot have more than 10 tags")
        return [tag.lower().strip() for tag in v if tag.strip()]

    @field_validator('question', 'answer')
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Ensure content doesn't contain inappropriate words."""
        banned_words = ["spam", "advertisement", "http://", "https://"]
        if any(word.lower() in v.lower() for word in banned_words):
            raise ValueError("Content contains prohibited words or links")
        return v.strip()

    @computed_field
    @property
    def word_count(self) -> int:
        """Calculate approximate word count of the answer."""
        return len(self.answer.split())

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "description": "Knowledge base entry for self-help automotive solutions",
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "question": "How do I check my engine oil level?",
                "answer": "Detailed instructions...",
                "tags": ["engine", "maintenance"],
                "is_active": True,
                "created_at": "2023-01-01T00:00:00Z",
                "word_count": 150
            }
        }
    )


class SelfHelpIn(BaseModel):
    """Input model for creating new self-help entries."""
    question: Annotated[
        str,
        Field(
            ...,
            min_length=10,
            max_length=200,
            description="The question or problem being addressed"
        )
    ]
    answer: Annotated[
        str,
        Field(
            ...,
            min_length=20,
            max_length=5000,
            description="Detailed solution or answer"
        )
    ]
    tags: Annotated[
        List[str],
        Field(
            default_factory=list,
            max_length=10,
            description="List of tags for categorization"
        )
    ]
    is_active: Annotated[
        bool,
        Field(
            True,
            description="Whether this entry should be immediately visible"
        )
    ]

    @model_validator(mode='after')
    def validate_new_entry(self) -> 'SelfHelpIn':
        """Additional validation for new entries."""
        if len(self.question.split()) < 3:
            raise ValueError("Question must be at least 3 words")
        if len(self.answer.split()) < 10:
            raise ValueError("Answer must be at least 10 words")
        return self

    model_config = ConfigDict(
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "question": "How often should I change my oil?",
                "answer": "Most manufacturers recommend...",
                "tags": ["oil", "maintenance"],
                "is_active": True
            }
        }
    )


class SelfHelpOut(SelfHelpIn):
    """Output model for self-help entries with additional metadata."""
    id: Annotated[
        PyObjectId,
        Field(
            ...,
            alias="_id",
            description="Unique identifier for the entry"
        )
    ]
    created_at: Annotated[
        datetime,
        Field(
            ...,
            description="Timestamp when entry was created"
        )
    ]
    updated_at: Annotated[
        Optional[datetime],
        Field(
            None,
            description="Timestamp when entry was last updated"
        )
    ]

    @computed_field
    @property
    def last_modified(self) -> datetime:
        """Get the most recent modification timestamp."""
        return self.updated_at or self.created_at

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "question": "How often should I change my oil?",
                "answer": "Most manufacturers recommend...",
                "tags": ["oil", "maintenance"],
                "is_active": True,
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-02T00:00:00Z"
            }
        }
    )


class SelfHelpUpdate(BaseModel):
    """Model for updating self-help entries."""
    question: Annotated[
        Optional[str],
        Field(
            None,
            min_length=10,
            max_length=200,
            description="Updated question text"
        )
    ]
    answer: Annotated[
        Optional[str],
        Field(
            None,
            min_length=20,
            max_length=5000,
            description="Updated answer text"
        )
    ]
    tags: Annotated[
        Optional[List[str]],
        Field(
            None,
            max_length=10,
            description="Updated list of tags"
        )
    ]
    is_active: Annotated[
        Optional[bool],
        Field(
            None,
            description="Updated visibility status"
        )
    ]
    updated_at: Annotated[
        datetime,
        Field(
            default_factory=lambda: datetime.now(timezone.utc),
            description="Timestamp of this update"
        )
    ]

    @model_validator(mode='after')
    def validate_update(self) -> 'SelfHelpUpdate':
        """Ensure at least one field is being updated."""
        if all(v is None for v in [self.question, self.answer, self.tags, self.is_active]):
            raise ValueError("At least one field must be provided for update")
        return self

    model_config = ConfigDict(
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "answer": "Updated detailed instructions...",
                "tags": ["engine", "oil", "maintenance"],
                "updated_at": "2023-01-03T00:00:00Z"
            }
        }
    )


class SelfHelpSearch(BaseModel):
    """Model for searching self-help entries."""
    keyword: Annotated[
        Optional[str],
        Field(
            None,
            min_length=3,
            description="Search term to match in questions and answers",
            examples=["oil change"]
        )
    ]
    tag: Annotated[
        Optional[str],
        Field(
            None,
            min_length=2,
            description="Filter by specific tag",
            examples=["engine"]
        )
    ]
    is_active: Annotated[
        Optional[bool],
        Field(
            True,
            description="Filter by active status"
        )
    ]

    @model_validator(mode='after')
    def validate_search(self) -> 'SelfHelpSearch':
        """Ensure at least one search parameter is provided."""
        if not any([self.keyword, self.tag]):
            raise ValueError("At least one search parameter (keyword or tag) is required")
        return self

    model_config = ConfigDict(
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "keyword": "oil change",
                "is_active": True
            }
        }
    )


class SelfHelpFeedbackModel(BaseModel):
    """Model for user feedback on self-help entries."""
    id: Annotated[
        PyObjectId,
        Field(
            default_factory=PyObjectId,
            alias="_id",
            description="Unique feedback identifier"
        )
    ]
    user_id: Annotated[
        Optional[PyObjectId],
        Field(
            None,
            description="ID of the user providing feedback (if logged in)"
        )
    ]
    self_help_id: Annotated[
        PyObjectId,
        Field(
            ...,
            description="ID of the self-help entry being rated"
        )
    ]
    is_helpful: Annotated[
        bool,
        Field(
            ...,
            description="Whether the user found this entry helpful"
        )
    ]
    comment: Annotated[
        Optional[str],
        Field(
            None,
            max_length=500,
            description="Optional feedback comment"
        )
    ]
    created_at: Annotated[
        datetime,
        Field(
            default_factory=lambda: datetime.now(timezone.utc),
            description="Timestamp when feedback was submitted"
        )
    ]

    @field_validator('comment')
    @classmethod
    def validate_comment(cls, v: Optional[str]) -> Optional[str]:
        """Clean and validate feedback comments."""
        if v is not None:
            v = v.strip()
            if len(v.split()) < 3 and len(v) > 0:
                raise ValueError("Comment must be at least 3 words if provided")
        return v

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "description": "User feedback on self-help entries",
            "example": {
                "_id": "507f1f77bcf86cd799439012",
                "user_id": "507f1f77bcf86cd799439013",
                "self_help_id": "507f1f77bcf86cd799439011",
                "is_helpful": True,
                "comment": "This was very clear and helpful!",
                "created_at": "2023-01-01T00:00:00Z"
            }
        }
    )


class SelfHelpAnalyticsModel(BaseModel):
    """Model for tracking analytics on self-help entries."""
    id: Annotated[
        PyObjectId,
        Field(
            default_factory=PyObjectId,
            alias="_id",
            description="Unique analytics record identifier"
        )
    ]
    self_help_id: Annotated[
        PyObjectId,
        Field(
            ...,
            description="ID of the self-help entry being tracked"
        )
    ]
    views: Annotated[
        int,
        Field(
            0,
            ge=0,
            description="Total number of views for this entry"
        )
    ]
    helpful_count: Annotated[
        int,
        Field(
            0,
            ge=0,
            description="Number of users who found this helpful"
        )
    ]
    not_helpful_count: Annotated[
        int,
        Field(
            0,
            ge=0,
            description="Number of users who didn't find this helpful"
        )
    ]
    last_viewed_at: Annotated[
        Optional[datetime],
        Field(
            None,
            description="Most recent view timestamp"
        )
    ]

    @computed_field
    @property
    def helpful_percentage(self) -> Optional[float]:
        """Calculate percentage of users who found this helpful."""
        total = self.helpful_count + self.not_helpful_count
        return round((self.helpful_count / total) * 100, 2) if total > 0 else None

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "description": "Usage analytics for self-help entries",
            "example": {
                "_id": "507f1f77bcf86cd799439014",
                "self_help_id": "507f1f77bcf86cd799439011",
                "views": 150,
                "helpful_count": 120,
                "not_helpful_count": 30,
                "last_viewed_at": "2023-01-05T00:00:00Z",
                "helpful_percentage": 80.0
            }
        }
    )


class SelfHelpSuggestionModel(BaseModel):
    """Model for user-submitted self-help suggestions."""
    id: Annotated[
        PyObjectId,
        Field(
            default_factory=PyObjectId,
            alias="_id",
            description="Unique suggestion identifier"
        )
    ]
    user_id: Annotated[
        Optional[PyObjectId],
        Field(
            None,
            description="ID of the user making the suggestion (if logged in)"
        )
    ]
    suggested_question: Annotated[
        str,
        Field(
            ...,
            min_length=10,
            max_length=200,
            description="Suggested question or problem statement"
        )
    ]
    suggested_answer: Annotated[
        str,
        Field(
            ...,
            min_length=20,
            max_length=5000,
            description="Suggested solution or answer"
        )
    ]
    tags: Annotated[
        List[str],
        Field(
            default_factory=list,
            max_length=10,
            description="Suggested tags for categorization"
        )
    ]
    status: Annotated[
        SuggestionStatus,
        Field(
            default=SuggestionStatus.PENDING,
            description="Current review status of the suggestion"
        )
    ]
    reviewed_by: Annotated[
        Optional[PyObjectId],
        Field(
            None,
            description="ID of the admin who reviewed this suggestion"
        )
    ]
    reviewed_at: Annotated[
        Optional[datetime],
        Field(
            None,
            description="Timestamp when suggestion was reviewed"
        )
    ]
    created_at: Annotated[
        datetime,
        Field(
            default_factory=lambda: datetime.now(timezone.utc),
            description="Timestamp when suggestion was submitted"
        )
    ]

    @model_validator(mode='after')
    def validate_review_fields(self) -> 'SelfHelpSuggestionModel':
        """Ensure review fields are properly set based on status."""
        if self.status != SuggestionStatus.PENDING:
            if not self.reviewed_by:
                raise ValueError("reviewed_by is required when status is not PENDING")
            if not self.reviewed_at:
                raise ValueError("reviewed_at is required when status is not PENDING")
        return self

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "description": "User-submitted suggestions for self-help knowledge base",
            "example": {
                "_id": "507f1f77bcf86cd799439015",
                "user_id": "507f1f77bcf86cd799439013",
                "suggested_question": "How do I jump start a car?",
                "suggested_answer": "Step-by-step instructions...",
                "tags": ["battery", "emergency"],
                "status": "pending",
                "created_at": "2023-01-01T00:00:00Z"
            }
        }
    )