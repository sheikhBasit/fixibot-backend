from motor.motor_asyncio import AsyncIOMotorClient
from config import settings
import logging

logger = logging.getLogger(__name__)

class Database:
    client: AsyncIOMotorClient = None
    db = None
    users_collection = None
    mechanics_collection = None
    vehicles_collection = None
    feedback_collection = None
    mechanic_service_collection = None
    ai_service_collection = None
    self_help_collection = None
    chat_sessions_collection = None  # Add this line

db = Database()

async def connect_to_mongo():
    try:
        db.client = AsyncIOMotorClient(
            str(settings.MONGODB_URL),
            tls=True,
            tlsAllowInvalidCertificates=False,
            retryWrites=True,
            w="majority",
            appName="Cluster0",
            maxPoolSize=100,
            minPoolSize=10
        )
        
        await db.client.admin.command('ping')
        db.db = db.client[settings.MONGO_DB]
        
        # Initialize all collections
        db.users_collection = db.db.users
        db.mechanics_collection = db.db.mechanics
        db.vehicles_collection = db.db.vehicles
        db.feedback_collection = db.db.feedbacks
        db.mechanic_service_collection = db.db.mechanic_service_collection        
        db.ai_service_collection = db.db.ai_service_collection
        db.self_help_collection = db.db.self_help_collection
        db.chat_sessions_collection = db.db.chat_sessions  # Add this line

        # Create indexes (keep your existing indexes)
        await db.users_collection.create_index("email", unique=True)
        await db.users_collection.create_index("phone_number", unique=True, sparse=True)
        # Run this once to create the index
        await db.mechanics_collection.create_index([("location", "2dsphere")])
        await db.vehicles_collection.create_index("user_id")
        await db.mechanics_collection.create_index("cnic", unique=True, sparse=True)
        await db.mechanic_service_collection.create_index([("user_id", 1)])
        await db.mechanic_service_collection.create_index([("mechanic_id", 1)])
        await db.mechanic_service_collection.create_index([("status", 1)])
        await db.mechanic_service_collection.create_index([("created_at", -1)])
        await db.ai_service_collection.create_index("user_id")
        await db.ai_service_collection.create_index("mechanic_id")
        await db.ai_service_collection.create_index("vehicle_id")
        await db.ai_service_collection.create_index("status")
        await db.ai_service_collection.create_index("priority")
        await db.ai_service_collection.create_index("request_time")
        await db.ai_service_collection.create_index([("issue_subject", "text")])
        
        # Add index for chat sessions
        await db.chat_sessions_collection.create_index("user_id")
        await db.chat_sessions_collection.create_index("session_id", unique=True)
        await db.chat_sessions_collection.create_index([("updated_at", -1)])

        logger.info("Successfully connected to MongoDB")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise

async def close_mongo_connection():
    try:
        if db.client:
            db.client.close()
            logger.info("Closed MongoDB connection")
    except Exception as e:
        logger.error(f"Error closing MongoDB connection: {e}")
        raise

# async def get_user_by_email(email: str) -> UserInDB:
#     try:
#         user = await db.users_collection.find_one({"email": email})
#         return UserInDB(**user) if user else None
#     except Exception as e:
#         logger.error(f"Error fetching user by email {email}: {e}")
#         raise

# async def get_user_by_id(user_id: str) -> UserInDB:
#     try:
#         user = await db.users_collection.find_one({"_id": PyObjectId(user_id)})
#         return UserInDB(**user) if user else None
#     except Exception as e:
#         logger.error(f"Error fetching user by ID {user_id}: {e}")
#         raise

# async def create_mechanic(self, mechanic: MechanicIn) -> MechanicOut:
#         mechanic_dict = jsonable_encoder(mechanic)
        
#         # Check for existing email/phone/cnic
#         existing = await self.mechanics_collection.find_one({
#             "$or": [
#                 {"email": mechanic.email},
#                 {"phone_number": mechanic.phone_number},
#                 {"cnic": mechanic.cnic}
#             ]
#         })
#         if existing:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Mechanic with this email, phone or CNIC already exists"
#             )
        
#         # Hash password
#         hashed_password = get_password_hash(mechanic.password)
#         mechanic_dict["hashed_password"] = hashed_password
#         del mechanic_dict["password"]
        
#         # Add timestamps and default status
#         mechanic_dict.update({
#             "created_at": datetime.now(timezone.utc)(),
#             "updated_at": datetime.now(timezone.utc)(),
#             "is_verified": False,
#             "is_available": True
#         })
        
#         result = await self.mechanics_collection.insert_one(mechanic_dict)
#         created = await self.mechanics_collection.find_one({"_id": result.inserted_id})
#         return MechanicOut(**created)
    
# async def get_mechanic_by_id(self, mechanic_id: str) -> MechanicOut:
        # try:
        #     mechanic = await self.mechanics_collection.find_one({"_id": PyObjectId(mechanic_id)})
        #     if not mechanic:
        #         raise HTTPException(status_code=404, detail="Mechanic not found")
        #     return MechanicOut(**mechanic)
        # except Exception as e:
        #     logger.error(f"Error fetching mechanic by ID {mechanic_id}: {e}")
        #     raise    