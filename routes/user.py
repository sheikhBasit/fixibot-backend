
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Form
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta, datetime, timezone
from typing import   List, Optional, Union
from models.user import AdminUserOut, GoogleSignInRequest, UpdateUser, UserCreate, UserInDB, UserOut, Token, UserRole, VerifyOTPRequest
from services.users import UserService
from database import db
from services.mail import send_password_reset_email, send_verification_email
from services.cloudinary import upload_image
from config import settings
from utils.auth import  create_access_token
from utils.py_object import PyObjectId
from utils.user import get_current_user
from google.oauth2 import id_token
from google.auth.transport import requests
router = APIRouter(prefix="/auth", tags=['Users'])

@router.post("/register", response_model=UserOut)
async def register(user: UserCreate):
    """Register a new user with email verification."""
    # Create user through service
    db_user = await UserService.create_user(user)
    
    # Generate and send verification email
    otp = await UserService.generate_and_save_token(str(db_user.id), "verify")
    await send_verification_email(db_user.email, otp)
    db_user_dict = db_user.model_dump(by_alias=True)
    db_user_dict["_id"] = str(db_user_dict["_id"])  # Convert ObjectId → str
    return UserOut.model_validate(db_user_dict)

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """Authenticate user and return JWT token."""
    user = await UserService.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified",
        )
    
    access_token_expires = timedelta(days=(settings.ACCESS_TOKEN_EXPIRE_DAYS)*5)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": access_token_expires.total_seconds()
    }

@router.get("/users/me", response_model=UserOut)
async def read_users_me(current_user: UserInDB = Depends(get_current_user)):
    """Get current user's profile."""
    user_dict = current_user.model_dump(by_alias=True)
    # Ensure both id and _id are strings for Pydantic validation
    if "id" in user_dict and not isinstance(user_dict["id"], str):
        user_dict["id"] = str(user_dict["id"])
    if "_id" in user_dict and not isinstance(user_dict["_id"], str):
        user_dict["_id"] = str(user_dict["_id"])
    return UserOut.model_validate(user_dict)


@router.post("/verify-email")
async def verify_email(req: VerifyOTPRequest):
    """Verify user's email with OTP."""
    success = await UserService.verify_email_token(req.email, req.otp)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )
    return {"message": "Email verified successfully"}

@router.post("/password-reset")
async def request_password_reset(email: str):
    """Request password reset with OTP."""
    user = await UserService.get_user_by_email(email)
    if not user:
        return {"message": "If account exists, reset email sent"}
    
    otp = await UserService.generate_and_save_token(str(user.id), "password")
    await send_password_reset_email(email, otp)
    return {"message": "Password reset OTP sent"}

@router.post("/password-reset/confirm")
async def confirm_password_reset(
    email: str,
    otp: str,
    new_password: str
):
    """Confirm password reset with OTP."""
    success = await UserService.reset_password(email, otp, new_password)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )
    return {"message": "Password reset successful"}

@router.post("/resend-verification")
async def resend_verification(email: str):
    """Resend verification email."""
    user = await UserService.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_verified:
        raise HTTPException(status_code=400, detail="Already verified")
    
    otp = await UserService.generate_and_save_token(str(user.id), "verify")
    await send_verification_email(email, otp)
    return {"message": "Verification OTP resent"}

@router.delete("/users/me")
async def delete_account(current_user: UserInDB = Depends(get_current_user)):
    """Delete current user's account."""
    success = await UserService.delete_user(str(current_user.id))
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account"
        )
    return {"message": "Account deleted"}

@router.get("/admin/users", response_model=List[AdminUserOut], summary="Admin: Get all users")
async def get_all_users_admin(
    limit: int = Query(100, gt=0, le=1000),
    skip: int = Query(0, ge=0),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get all users (admin only)"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return await UserService.get_all_users(limit=limit, skip=skip)

@router.get("/admin/users/search", response_model=List[UserOut], summary="Admin: Search users")
async def search_users_admin(
    query: Optional[str] = Query(None, description="Search by name, email or phone"),
    min_vehicles: Optional[int] = Query(None, ge=0, description="Minimum vehicles owned"),
    max_vehicles: Optional[int] = Query(None, ge=0, description="Maximum vehicles owned"),
    role: Optional[UserRole] = Query(None, description="Filter by user role"),
    is_verified: Optional[bool] = Query(None, description="Filter by verification status"),
    limit: int = Query(100, gt=0, le=1000),
    skip: int = Query(0, ge=0),
    current_user: UserInDB = Depends(get_current_user)
):
    """Search users with various filters (admin only)"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return await UserService.search_users(
        query=query,
        min_vehicles=min_vehicles,
        max_vehicles=max_vehicles,
        role=role.value if role else None,
        is_verified=is_verified,
        limit=limit,
        skip=skip
    )

@router.get("/admin/users/by-vehicles", response_model=List[UserOut], summary="Admin: Get users by vehicle count")
async def get_users_by_vehicle_count_admin(
    min_count: int = Query(0, ge=0, description="Minimum vehicles owned"),
    max_count: Optional[int] = Query(None, ge=0, description="Maximum vehicles owned"),
    limit: int = Query(100, gt=0, le=1000),
    skip: int = Query(0, ge=0),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get users filtered by number of vehicles they own (admin only)"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return await UserService.get_users_by_vehicle_count(
        min_count=min_count,
        max_count=max_count,
        limit=limit,
        skip=skip
    )

@router.get("/users/email/{email}", response_model=UserOut, summary="Get user by email")
async def get_user_by_email(
    email: str,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Get user information by email address.
    
    Args:
        email: Email address of the user to fetch
        current_user: Currently authenticated user
        
    Returns:
        User information
        
    Raises:
        HTTPException: 404 if user not found
        HTTPException: 403 if not authorized (users can only access their own data unless admin)
    """
    # Normalize email
    email = email.lower()
    
    # Users can only access their own data unless they're admin
    if current_user.email != email and current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You can only view your own profile."
        )
    
    user = await UserService.admin_get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user

@router.get("/users/id/{user_id}", response_model=UserOut, summary="Get user by ID")
async def get_user_by_id(
    user_id: str,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Get user information by user ID.
    
    Args:
        user_id: ID of the user to fetch
        current_user: Currently authenticated user
        
    Returns:
        User information
        
    Raises:
        HTTPException: 404 if user not found
        HTTPException: 403 if not authorized (users can only access their own data unless admin)
    """
    # Users can only access their own data unless they're admin
    if current_user.id != user_id and current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You can only view your own profile."
        )
    
    user = await UserService.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.get("/admin/users/email/{email}", response_model=UserOut, summary="Admin: Get user by email")
async def get_user_by_email_admin(
    email: str,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Get user information by email address (admin only).
    
    Args:
        email: Email address of the user to fetch
        current_user: Currently authenticated admin user
        
    Returns:
        User information
        
    Raises:
        HTTPException: 404 if user not found
        HTTPException: 403 if not admin
    """
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Normalize email
    email = email.lower()
    
    user = await UserService.admin_get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.delete("/admin/users/{user_id}", summary="Admin: Delete user by ID")
async def delete_user_admin(user_id: str, current_user: UserInDB = Depends(get_current_user)):
    """Admin: Delete a user by their ID."""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    success = await UserService.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found or could not be deleted")
    return {"message": "User deleted successfully"}

@router.patch("/admin/users/{user_id}", response_model=UserOut, summary="Admin: Update any user")
async def update_user_admin(
    user_id: str,
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    phone_number: Optional[str] = Form(None),
    profile_picture: Optional[Union[UploadFile,str]] = File(None),
    role: Optional[UserRole] = Form(None),
    is_verified: Optional[bool] = Form(None),
    is_active: Optional[bool] = Form(None),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Update any user's profile (admin only).
    """
    # Debug: Print all incoming form data
    print(f"=== DEBUG: Incoming Request Data ===")
    print(f"user_id: {user_id}")
    print(f"first_name: {first_name} (type: {type(first_name)})")
    print(f"last_name: {last_name} (type: {type(last_name)})")
    print(f"email: {email} (type: {type(email)})")
    print(f"phone_number: {phone_number} (type: {type(phone_number)})")
    print(f"profile_picture: {profile_picture} (type: {type(profile_picture)})")
    print(f"role: {role} (type: {type(role)})")
    print(f"is_verified: {is_verified} (type: {type(is_verified)})")
    print(f"is_active: {is_active} (type: {type(is_active)})")
    print(f"current_user role: {current_user.role}")
    
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Convert empty strings to None before validation
    def clean_form_value(value):
        """Convert empty/placeholder values to None."""
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            if value == "" or value.lower() in ["null", "undefined", "none", "empty"]:
                return None
        return value
    
    # Clean form values
    cleaned_first_name = clean_form_value(first_name)
    cleaned_last_name = clean_form_value(last_name)
    cleaned_email = clean_form_value(email)
    cleaned_phone_number = clean_form_value(phone_number)
    
    print(f"=== DEBUG: After Cleaning ===")
    print(f"cleaned_first_name: {cleaned_first_name}")
    print(f"cleaned_last_name: {cleaned_last_name}")
    print(f"cleaned_email: {cleaned_email}")
    print(f"cleaned_phone_number: {cleaned_phone_number}")
    
    # Validate input using UpdateUser model
    try:
        update_data = UpdateUser(
            first_name=cleaned_first_name,
            last_name=cleaned_last_name,
            email=cleaned_email,
            phone_number=cleaned_phone_number,
            profile_picture=None  # Will handle file separately
        )
        print(f"=== DEBUG: UpdateUser Model Created Successfully ===")
        print(f"update_data: {update_data}")
    except Exception as e:
        print(f"=== DEBUG: Error creating UpdateUser model ===")
        print(f"Error: {e}")
        print(f"Error type: {type(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid input data: {str(e)}"
        )
    
    update_dict = update_data.model_dump(exclude_unset=True, exclude_none=True)
    print(f"=== DEBUG: After model_dump ===")
    print(f"update_dict: {update_dict}")
    
    # Handle email normalization
    if "email" in update_dict:
        update_dict["email"] = update_dict["email"].lower()
        print(f"=== DEBUG: After email normalization ===")
        print(f"normalized email: {update_dict['email']}")
        
        # Check if email is already in use by another user
        existing_email_user = await db.users_collection.find_one({
            "email": update_dict["email"],
            "_id": {"$ne": PyObjectId(user_id)}
        })
        if existing_email_user:
            print(f"=== DEBUG: Email conflict detected ===")
            print(f"existing_email_user: {existing_email_user}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address already in use by another account"
            )

    # Check phone number uniqueness
    if "phone_number" in update_dict:
        existing_phone_user = await db.users_collection.find_one({
            "phone_number": update_dict["phone_number"],
            "_id": {"$ne": PyObjectId(user_id)}
        })
        if existing_phone_user:
            print(f"=== DEBUG: Phone number conflict detected ===")
            print(f"existing_phone_user: {existing_phone_user}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already in use by another account"
            )

    # Handle profile picture upload
    if profile_picture:
        print(f"=== DEBUG: Processing profile picture ===")
        print(f"profile_picture type: {type(profile_picture)}")
        image_url = await upload_image(profile_picture, expected_type='user')
        update_dict["profile_picture"] = image_url
        print(f"uploaded image_url: {image_url}")

    # Add admin-only fields
    if role is not None:
        update_dict["role"] = role
    if is_verified is not None:
        update_dict["is_verified"] = is_verified
    if is_active is not None:
        update_dict["is_active"] = is_active

    # Add updated_at timestamp
    update_dict["updated_at"] = datetime.now(timezone.utc)

    print(f"=== DEBUG: Final update_dict ===")
    print(f"update_dict: {update_dict}")

    # Update user in database
    try:
        updated_user = await UserService.update_user(user_id, update_dict)
        print(f"=== DEBUG: After UserService.update_user ===")
        print(f"updated_user: {updated_user}")
    except Exception as e:
        print(f"=== DEBUG: Error in UserService.update_user ===")
        print(f"Error: {e}")
        print(f"Error type: {type(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user in database"
        )
    
    if not updated_user:
        print(f"=== DEBUG: User not found ===")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
        
    print(f"=== DEBUG: Successfully updated user ===")
    return updated_user
@router.put("/users/me", response_model=UserOut)
async def update_user_me(
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    phone_number: Optional[str] = Form(None),
    profile_picture: Optional[Union[UploadFile,str]] = File(None),
    current_user: UserInDB = Depends(get_current_user),
) -> UserOut:
    """
    Update current user's profile. At least one field or profile picture must be provided.
    All fields are optional, allowing for partial updates.
    """
    # Initialize update dictionary
    update_dict = {}
    
    # Handle profile picture first if provided
    if profile_picture:
        try:
            image_url = await upload_image(profile_picture, expected_type='user')
            update_dict["profile_picture"] = image_url
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error uploading profile picture: {str(e)}"
            )
    
    # Convert empty strings to None and process other fields
    def clean_form_value(value):
        """Convert empty/placeholder values to None."""
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            if value == "" or value.lower() in ["null", "undefined", "none", "empty"]:
                return None
        return value
    
    # Process text fields only if they have actual values
    field_updates = {
        "first_name": clean_form_value(first_name),
        "last_name": clean_form_value(last_name),
        "email": clean_form_value(email),
        "phone_number": clean_form_value(phone_number)
    }
    
    # Add non-None values to update_dict
    for field, value in field_updates.items():
        if value is not None:
            update_dict[field] = value
    
    # If no updates provided at all (no fields and no profile picture)
    if not update_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided for update"
        )
    
    # Handle email validation if provided
    if "email" in update_dict:
        update_dict["email"] = update_dict["email"].lower()
        existing_email_user = await db.users_collection.find_one({
            "email": update_dict["email"],
            "_id": {"$ne": current_user.id}
        })
        if existing_email_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address already in use by another account"
            )

    # Handle phone number validation if provided
    if "phone_number" in update_dict:
        existing_phone_user = await db.users_collection.find_one({
            "phone_number": update_dict["phone_number"],
            "_id": {"$ne": current_user.id}
        })
        if existing_phone_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already in use by another account"
            )

    # Add updated_at timestamp
    update_dict["updated_at"] = datetime.now(timezone.utc)

    try:
        # Update user in database
        updated_user = await UserService.update_user(str(current_user.id), update_dict)
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return updated_user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating user: {str(e)}"
        )
    
    update_dict = update_data.model_dump(exclude_unset=True, exclude_none=True)
    
    # Handle email normalization
    if "email" in update_dict:
        update_dict["email"] = update_dict["email"].lower()
        
        # Check if email is already in use by another user
        existing_email_user = await db.users_collection.find_one({
            "email": update_dict["email"],
            "_id": {"$ne": current_user.id}
        })
        if existing_email_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address already in use by another account"
            )

    # Check phone number uniqueness
    if "phone_number" in update_dict:
        existing_phone_user = await db.users_collection.find_one({
            "phone_number": update_dict["phone_number"],
            "_id": {"$ne": current_user.id}
        })
        if existing_phone_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already in use by another account"
            )

    # Handle profile picture upload
    if profile_picture:
        image_url = await upload_image(profile_picture, expected_type='user')
        update_dict["profile_picture"] = image_url

    # Add updated_at timestamp
    update_dict["updated_at"] = datetime.now(timezone.utc)

    # Update user in database
    updated_user = await UserService.update_user(str(current_user.id), update_dict)
    
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
        
    return updated_user




@router.post("/google")
async def google_login(payload: GoogleSignInRequest):
    """Login or Register user using Google OAuth token."""
    try:
        # Verify token with Google
        idinfo = id_token.verify_oauth2_token(payload.token, requests.Request(), settings.GOOGLE_CLIENT_ID)

        email = idinfo.get("email")
        first_name = idinfo.get("given_name", "")
        last_name = idinfo.get("family_name", "")
        picture = idinfo.get("picture", "")

        if not email:
            raise HTTPException(status_code=400, detail="Invalid Google token")

        # Check if user exists
        user: Optional[UserInDB] = await UserService.get_user_by_email(email)

        # If not exists, create new user
        if not user:
            user_data = {
                "first_name": first_name or "Google",
                "last_name": last_name or "User",
                "email": email,
                "phone_number": None,
                "profile_picture": picture,
                "role": "user",
                "is_active": True,
                "is_verified": True,  # Mark verified since Google already verified email
                "password": None  # No password for social login
            }
            user = await UserService.create_user_from_google(user_data)

        # Generate JWT token for your app
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_DAYS)
        token = create_access_token(data={"sub": str(user.id)}, expires_delta=access_token_expires)

        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": access_token_expires.total_seconds(),
            "user": {
                "_id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "profile_picture": user.profile_picture
            }
        }

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Google token")

