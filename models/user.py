from datetime import datetime, timezone
from typing import List, Optional, Annotated
from pydantic import (
    BaseModel, 
    Field, 
    EmailStr, 
    field_validator, 
    model_validator,
    computed_field,
    ConfigDict
)
from enum import Enum
from bson import ObjectId

from utils.py_object import PyObjectId



class UserRole(str, Enum):
    """Enum representing user roles with permission levels."""
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

    @classmethod
    def admin_roles(cls) -> List['UserRole']:
        """Roles with administrative privileges."""
        return [cls.ADMIN, cls.SUPER_ADMIN]


class UserBase(BaseModel):
    """Base model containing shared user fields and validations."""
    first_name: Annotated[
        str,
        Field(
            ...,
            min_length=1,
            max_length=50,
            description="User's first name",
            examples=["John"]
        )
    ]
    last_name: Annotated[
        str,
        Field(
            ...,
            min_length=1,
            max_length=50,
            description="User's last name",
            examples=["Doe"]
        )
    ]
    email: Annotated[
        EmailStr,
        Field(
            ...,
            description="User's email address",
            examples=["john.doe@example.com"]
        )
    ]
    phone_number: Annotated[
        Optional[str],
        Field(
            None,
            pattern=r"^\+?[1-9]\d{1,14}$",
            description="Phone number in E.164 format",
            examples=["+1234567890"]
        )
    ]
    profile_picture: Annotated[
        Optional[str],
        Field(
            None,
            description="URL to user's profile picture",
            examples=["https://example.com/profile.jpg"]
        )
    ]
    role: Annotated[
        UserRole,
        Field(
            default=UserRole.USER,
            description="User's role in the system"
        )
    ]
    is_active: Annotated[
        bool,
        Field(
            default=True,
            description="Whether the user account is active"
        )
    ]
    is_verified: Annotated[
        bool,
        Field(
            default=False,
            description="Whether the user's email has been verified"
        )
    ]

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Normalize email to lowercase."""
        return v.lower() if v else v

    @model_validator(mode='after')
    def validate_admin_verification(self) -> 'UserBase':
        """Ensure admin accounts are verified."""
        if self.role in UserRole.admin_roles() and not self.is_verified:
            raise ValueError("Admin accounts must be verified")
        return self


class UserCreate(UserBase):
    """Model for creating new users with password validation."""
    password: Annotated[
        str,
        Field(
            ...,
            min_length=8,
            max_length=100,
            description="User's password (will be hashed before storage)",
            examples=["Str0ngP@ssword"]
        )
    ]

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Ensure password meets complexity requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c in "!@#$%^&*()" for c in v):
            raise ValueError("Password must contain at least one special character")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "phone_number": "+1234567890",
                "password": "Str0ngP@ssword",
                "role": "user"
            }
        }
    )


class UserInDB(UserBase):
    """Database model for users with sensitive fields."""
    id: Annotated[
        PyObjectId,
        Field(
            default_factory=PyObjectId,
            alias="_id",
            description="Unique user identifier"
        )
    ]
    hashed_password: Annotated[
        str,
        Field(
            ...,
            description="Hashed password for security"
        )
    ]
    last_login: Annotated[
        Optional[datetime],
        Field(
            None,
            description="Timestamp of last successful login"
        )
    ]
    fcm_token: Annotated[
        Optional[str],
        Field(
            None,
            description="Firebase Cloud Messaging token for push notifications"
        )
    ]
    is_token_verified: Annotated[
        bool,
        Field(
            default=False,
            description="Whether the current session token is verified"
        )
    ]
    token_expiry: Annotated[
        Optional[datetime],
        Field(
            None,
            description="Expiration time for current session token"
        )
    ]
    verify_token: Annotated[
        Optional[str],
        Field(
            None,
            description="Email verification token"
        )
    ]
    verify_token_expiry: Annotated[
        Optional[datetime],
        Field(
            None,
            description="Expiration time for email verification token"
        )
    ]
    password_reset_token: Annotated[
        Optional[str],
        Field(
            None,
            description="Password reset token"
        )
    ]
    password_token_expiry: Annotated[
        Optional[datetime],
        Field(
            None,
            description="Expiration time for password reset token"
        )
    ]
    created_at: Annotated[
        datetime,
        Field(
            default_factory=lambda: datetime.now(timezone.utc),
            description="Timestamp when user was created"
        )
    ]
    updated_at: Annotated[
        datetime,
        Field(
            default_factory=lambda: datetime.now(timezone.utc),
            description="Timestamp when user was last updated"
        )
    ]

    @computed_field
    @property
    def full_name(self) -> str:
        """Combine first and last name."""
        return f"{self.first_name} {self.last_name}"

    @computed_field
    @property
    def is_admin(self) -> bool:
        """Check if user has admin privileges."""
        return self.role in UserRole.admin_roles()

    model_config = ConfigDict(
        json_encoders={ObjectId: str},
        json_schema_extra={
            "description": "Complete user model as stored in database",
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "hashed_password": "$2b$12$...",
                "role": "user",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-02T00:00:00Z",
                "full_name": "John Doe"
            }
        }
    )


class UserOut(BaseModel):
    """Output model for user data (safe for public exposure)."""
    id: Annotated[
        str,
        Field(
            ...,
            alias="_id",
            description="Unique user identifier",
            examples=["507f1f77bcf86cd799439011"]
        )
    ]
    first_name: Annotated[
        str,
        Field(
            ...,
            description="User's first name"
        )
    ]
    last_name: Annotated[
        str,
        Field(
            ...,
            description="User's last name"
        )
    ]
    email: Annotated[
        str,
        Field(
            ...,
            description="User's email address"
        )
    ]
    profile_picture: Annotated[
        Optional[str],
        Field(
            None,
            description="URL to user's profile picture"
        )
    ]
    phone_number: Annotated[
        Optional[str],
        Field(
            None,
            description="User's phone number"
        )
    ]

    @computed_field
    @property
    def initials(self) -> str:
        """Generate initials from first and last name."""
        return f"{self.first_name[0]}{self.last_name[0]}".upper()

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "description": "Public user profile information",
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "profile_picture": "https://example.com/profile.jpg",
                "phone_number": "+1234567890",
                "initials": "JD"
            }
        }
    )

class UpdateUser(BaseModel):
    """Model for updating user information."""
    first_name: Annotated[
        Optional[str],
        Field(
            None,
            min_length=1,
            max_length=50,
            description="Updated first name"
        )
    ]
    last_name: Annotated[
        Optional[str],
        Field(
            None,
            min_length=1,
            max_length=50,
            description="Updated last name"
        )
    ]
    email: Annotated[
        Optional[EmailStr],
        Field(
            None,
            description="Updated email address"
        )
    ]
    phone_number: Annotated[
        Optional[str],
        Field(
            None,
            pattern=r"^\+?[1-9]\d{1,14}$",
            description="Updated phone number"
        )
    ]
    profile_picture: Annotated[
        Optional[str],
        Field(
            None,
            description="Updated profile picture URL"
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

    @model_validator(mode='after')
    def validate_update(self) -> 'UpdateUser':
        """Ensure at least one field is being updated."""
        if all(v is None for v in [self.first_name, self.last_name, self.email, self.phone_number, self.profile_picture]):
            raise ValueError("At least one field must be provided for update")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Model for updating user profile information",
            "example": {
                "first_name": "John",
                "last_name": "Smith",
                "phone_number": "+1234567890"
            }
        }
    )


class Token(BaseModel):
    """Model for authentication tokens."""
    access_token: Annotated[
        str,
        Field(
            ...,
            description="JWT access token for authentication",
            examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."]
        )
    ]
    token_type: Annotated[
        str,
        Field(
            default="bearer",
            description="Type of token",
            examples=["bearer"]
        )
    ]
    expires_in: Annotated[
        int,
        Field(
            ...,
            description="Time in seconds until token expiration",
            examples=[3600]
        )
    ]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 3600
            }
        }
    )


class TokenData(BaseModel):
    """Model for decoded token data."""
    id: Annotated[
        Optional[str],
        Field(
            None,
            description="User ID from token",
            examples=["507f1f77bcf86cd799439011"]
        )
    ]
    email: Annotated[
        Optional[EmailStr],
        Field(
            None,
            description="User email from token",
            examples=["john.doe@example.com"]
        )
    ]


class VerifyOTPRequest(BaseModel):
    """Model for OTP verification requests."""
    email: Annotated[
        EmailStr,
        Field(
            ...,
            description="Email address to verify",
            examples=["john.doe@example.com"]
        )
    ]
    otp: Annotated[
        str,
        Field(
            ...,
            min_length=6,
            max_length=6,
            description="6-digit OTP code",
            examples=["123456"]
        )
    ]

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Normalize email to lowercase."""
        return v.lower() if v else v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "john.doe@example.com",
                "otp": "123456"
            }
        }
    )


class GoogleSignInRequest(BaseModel):
    token: str