from fastapi.encoders import jsonable_encoder
from models.user import UserCreate, UserInDB, UserOut
from database import db
from utils.py_object import PyObjectId

from typing import List, Optional
import logging
from fastapi import HTTPException, status
from datetime import datetime, timedelta, timezone
from config import settings
from utils.auth import get_password_hash, verify_password
from pymongo.errors import DuplicateKeyError
from fastapi import HTTPException, status
from utils.auth import generate_otp
        
logger = logging.getLogger("user_service")

class UserService:
    @staticmethod
    async def get_user_by_email(email: str) -> Optional[UserInDB]:
        """Get user by email from database."""
        try:
            user = await db.users_collection.find_one({"email": email.lower()})
            return UserInDB(**user) if user else None
        except Exception as e:
            logger.error(f"Error fetching user by email {email}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error fetching user"
            )

    @staticmethod
    async def get_user_by_id(user_id: str) -> Optional[UserOut]:  # Change return type to UserOut
        """Get user by ID from database."""
        try:
            user = await db.users_collection.find_one({"_id": PyObjectId(user_id)})
            if user:
                # Convert ObjectId to string for Pydantic validation
                user["_id"] = str(user["_id"])
                return UserOut(**user)  # Return UserOut instead of UserInDB
            return None
        except Exception as e:
            logger.error(f"Error fetching user by ID {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error fetching user"
            )
    
    @staticmethod
    async def create_user(user_create: UserCreate) -> UserInDB:
        """Create a new user in database."""
        try:
            # Check if email already exists
            existing_user_email = await UserService.get_user_by_email(user_create.email)
            if existing_user_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )

            # Check if phone number already exists (if provided)
            if user_create.phone_number:
                existing_user_phone = await db.users_collection.find_one({"phone_number": user_create.phone_number})
                if existing_user_phone:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Phone number already registered"
                    )

            # Hash password
            hashed_password = get_password_hash(user_create.password)
            now = datetime.now(timezone.utc)

            # Create user object
            db_user = UserInDB(
                **user_create.model_dump(exclude={"password"}),
                hashed_password=hashed_password,
                created_at=now,
                updated_at=now
            )

            # Insert into database
            result = await db.users_collection.insert_one(db_user.model_dump(by_alias=True, exclude_none=True))
            if not result.inserted_id:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user"
                )

            # Fetch created user - convert ObjectId to string
            created_user_doc = await db.users_collection.find_one({"_id": result.inserted_id})
            if created_user_doc:
                created_user_doc["_id"] = str(created_user_doc["_id"])
                return UserInDB(**created_user_doc)
                
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch created user"
            )

        except HTTPException:
            raise
        except DuplicateKeyError as e:
            # Handle MongoDB duplicate key error
            if 'email' in str(e):
                raise HTTPException(status_code=400, detail="Email already registered")
            if 'phone_number' in str(e):
                raise HTTPException(status_code=400, detail="Phone number already registered")
            # Generic fallback for other unique fields
            raise HTTPException(status_code=400, detail="Duplicate key error")
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error creating user"
            )
        

    @staticmethod
    async def update_user(user_id: str, update_data: dict) -> UserInDB:
        """Update user information."""
        try:
            # Remove the extra parentheses
            update_data["updated_at"] = datetime.now(timezone.utc)
            
            result = await db.users_collection.update_one(
                {"_id": PyObjectId(user_id)},
                {"$set": update_data}
            )
            
            if result.modified_count == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No changes were made"
                )
                
            # Fetch updated user - convert ObjectId to string
            updated_user_doc = await db.users_collection.find_one({"_id": PyObjectId(user_id)})
            if updated_user_doc:
                updated_user_doc["_id"] = str(updated_user_doc["_id"])
                return jsonable_encoder(updated_user_doc)
                
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found after update"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error updating user"
            )
        

    @staticmethod
    async def verify_email_token(email: str, token: str) -> bool:
        """Verify email verification token."""
        try:
            user = await UserService.get_user_by_email(email)
            if not user:
                return False
                
            if (user.verify_token == token and 
                user.verify_token_expiry and 
                user.verify_token_expiry > datetime.now(timezone.utc)):
                await db.users_collection.update_one(
                    {"_id": PyObjectId(user.id)},  # Fix here
                    {"$set": {"is_verified": True},
                        "$unset": {"verify_token": "", "verify_token_expiry": ""}}
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Error verifying email token: {e}")
            return False

    @staticmethod
    async def reset_password(email: str, token: str, new_password: str) -> bool:
        """Reset user password with token."""
        try:
            user = await UserService.get_user_by_email(email)
            if not user:
                return False
                
            if (user.password_reset_token == token and 
                user.password_token_expiry and 
                user.password_token_expiry > datetime.now(timezone.utc)):
                
                hashed_password = get_password_hash(new_password)
                await db.users_collection.update_one(
                    {"_id": PyObjectId(user.id)},  # Fix here
                    {"$set": {"hashed_password": hashed_password},
                        "$unset": {"password_reset_token": "", "password_token_expiry": ""}}
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Error resetting password: {e}")
            return False
    @staticmethod
    async def generate_and_save_token(
        user_id: str, 
        token_type: str, 
        expires_minutes: int = settings.EMAIL_TOKEN_EXPIRE_MINUTES
    ) -> str:
        """Generate and save a token (verification or password reset)."""
        
        token = generate_otp(6)
        expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
        
        update_field = {
            "verify_token": token,
            "verify_token_expiry": expiry
        } if token_type == "verify" else {
            "password_reset_token": token,
            "password_token_expiry": expiry
        }
        
        await db.users_collection.update_one(
            {"_id": PyObjectId(user_id)},
            {"$set": update_field}
        )
        return token

    @staticmethod
    async def delete_user(user_id: str) -> bool:
        """Delete a user from database."""
        try:
            result = await db.users_collection.delete_one({"_id": PyObjectId(user_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            return False
    
    @staticmethod
    async def authenticate_user(email: str, password: str):
        """Authenticate user by verifying email and password."""
        user = await UserService.get_user_by_email(email)
        if not user:
            return False
        if not verify_password(password, user.hashed_password):
            return False
        return user
 

    @staticmethod
    async def get_all_users(limit: int = 100, skip: int = 0) -> List[UserOut]:
        """Get all users with pagination"""
        users = await db.users_collection.find().skip(skip).limit(limit).to_list(length=None)
        # Convert ObjectId to string for each user
        for user in users:
            user["_id"] = str(user["_id"])
        return [UserOut(**user) for user in users]

    @staticmethod
    async def search_users(
        query: Optional[str] = None,
        min_vehicles: Optional[int] = None,
        max_vehicles: Optional[int] = None,
        role: Optional[str] = None,
        is_verified: Optional[bool] = None,
        limit: int = 100,
        skip: int = 0
    ) -> List[UserOut]:
        """Search users with various filters"""
        filter_query = {}
        
        if query:
            filter_query["$or"] = [
                {"email": {"$regex": query, "$options": "i"}},
                {"first_name": {"$regex": query, "$options": "i"}},
                {"last_name": {"$regex": query, "$options": "i"}},
                {"phone_number": {"$regex": query, "$options": "i"}}
            ]
        
        if min_vehicles is not None or max_vehicles is not None:
            vehicle_filter = {}
            if min_vehicles is not None:
                vehicle_filter["$gte"] = min_vehicles
            if max_vehicles is not None:
                vehicle_filter["$lte"] = max_vehicles
            filter_query["vehicle_count"] = vehicle_filter
        
        if role:
            filter_query["role"] = role
        
        if is_verified is not None:
            filter_query["is_verified"] = is_verified
        
        users = await db.users_collection.find(filter_query).skip(skip).limit(limit).to_list(length=None)
        # Convert ObjectId to string for each user
        for user in users:
            user["_id"] = str(user["_id"])
        return [UserOut(**user) for user in users]

    @staticmethod
    async def create_user_from_google(user_data: dict) -> UserInDB:
        user_data["created_at"] = datetime.now(timezone.utc)
        user_data["updated_at"] = datetime.now(timezone.utc)
        result = await db.users_collection.insert_one(user_data)
        user_data["_id"] = result.inserted_id
        return UserInDB(**user_data)


    @staticmethod
    async def get_users_by_vehicle_count(
        min_count: int = 0,
        max_count: Optional[int] = None,
        limit: int = 100,
        skip: int = 0
    ) -> List[UserOut]:
        """Get users filtered by number of vehicles they own"""
        try:
            # Create aggregation pipeline to count vehicles per user
            pipeline = [
                # Lookup to get vehicles for each user
                {
                    "$lookup": {
                        "from": "vehicles_collection",  # Replace with your actual vehicles collection name
                        "localField": "_id",
                        "foreignField": "owner_id",
                        "as": "vehicles"
                    }
                },
                # Add field with vehicle count
                {
                    "$addFields": {
                        "vehicle_count": {"$size": "$vehicles"}
                    }
                },
                # Filter by vehicle count
                {
                    "$match": {
                        "vehicle_count": {"$gte": min_count}
                    }
                }
            ]

            # Add max_count filter if provided
            if max_count is not None:
                pipeline[2]["$match"]["vehicle_count"]["$lte"] = max_count

            # Add sorting and pagination
            pipeline.extend([
                {"$sort": {"vehicle_count": -1}},  # Sort by vehicle count descending
                {"$skip": skip},
                {"$limit": limit}
            ])

            users = await db.users_collection.aggregate(pipeline).to_list(length=None)

            # Convert ObjectId to string for each user and prepare for UserOut
            for user in users:
                user["_id"] = str(user["_id"])
                # Remove the vehicles array if you don't want to include it in the response
                if "vehicles" in user:
                    del user["vehicles"]

            return [UserOut(**user) for user in users]

        except Exception as e:
            logger.error(f"Error getting users by vehicle count: {e}")
            raise