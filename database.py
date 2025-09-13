from motor.motor_asyncio import AsyncIOMotorClient
from config import settings
import logging
import certifi
from pymongo.errors import OperationFailure

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
    chat_sessions_collection = None
    audit_logs_collection = None
    settings_collection= None

db = Database()

async def connect_to_mongo():
    try:
        db.client = AsyncIOMotorClient(
            str(settings.MONGODB_URL),
            tls=True,
            tlsCAFile=certifi.where(),
            tlsAllowInvalidCertificates=False,
            retryWrites=True,
            w="majority",
            appName="Cluster0",
            maxPoolSize=100,
            minPoolSize=10,
            connectTimeoutMS=30000,
            serverSelectionTimeoutMS=30000
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
        db.chat_sessions_collection = db.db.chat_sessions
        db.audit_logs_collection = db.db.audit_logs
        db.settings_collection = db.db.settings

        # Create indexes with error handling for existing indexes
        try:
            await db.users_collection.create_index("email", unique=True)
            await db.users_collection.create_index("phone_number", unique=True, sparse=True)
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
            
            # Add index for chat sessions, re-adding sparse=True
            await db.chat_sessions_collection.create_index("user_id")
            await db.chat_sessions_collection.create_index([("updated_at", -1)])
            logger.info("MongoDB indexes created successfully.")
        except OperationFailure as e:
            logger.warning(f"Failed to create some MongoDB indexes: {e}. This may be because they already exist.")
        
        logger.info("Successfully connected to MongoDB")
        
        return db.client
        
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
