import asyncio
import logging
import os
from pymongo.errors import OperationFailure
from bson import ObjectId

# Import the database connection logic from your application
# We assume the file you provided is named 'database.py'
try:
    from database import db, connect_to_mongo, close_mongo_connection
except ImportError:
    print("Error: Could not import db, connect_to_mongo, and close_mongo_connection from database.py")
    print("Please ensure 'database.py' is in the same directory and contains your DB logic.")
    exit(1)


# Setup basic logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def find_orphaned_vehicles():
    """
    Finds vehicles where the user_id does not correspond
    to any user in the users collection.
    Assumes MongoDB connection is already established.
    """
    try:
        # 1. We no longer need to connect here, we use the imported db object
        # --- THIS IS THE FIX ---
        # Changed 'not db.db' to 'db.db is None'
        if db.db is None or db.vehicles_collection is None or db.users_collection is None:
        # --- END OF FIX ---
            logger.error("Database collections are not initialized. Was connect_to_mongo() called?")
            return

        vehicles_col = db.vehicles_collection
        users_col_name = db.users_collection.name # Get the name for the $lookup

        logger.info(f"Checking for orphaned vehicles in database '{db.db.name}'...")

        # 2. Define the aggregation pipeline
        pipeline = [
            {
                # Try to join with the users collection
                "$lookup": {
                    "from": users_col_name,
                    "localField": "user_id",
                    "foreignField": "_id",
                    "as": "owner_doc"  # New field to store the joined user (as an array)
                }
            },
            {
                # Filter to find documents where the join *failed*
                # (i.e., the owner_doc array is empty)
                "$match": {
                    "owner_doc": { "$eq": [] }
                }
            },
            {
                # Clean up the output to be more readable
                "$project": {
                    "_id": 1,  # This is the Vehicle's ID
                    "brand": 1,
                    "model": 1,
                    "year": 1,
                    "registration_number": 1,
                    "orphaned_user_id": "$user_id" # The user_id that is missing
                }
            }
        ]

        logger.info("Running aggregation...")
        
        # 3. Execute the aggregation
        orphaned_vehicles = []
        cursor = vehicles_col.aggregate(pipeline)
        async for vehicle in cursor:
            orphaned_vehicles.append(vehicle)

        # 4. Report the results
        if not orphaned_vehicles:
            logger.info("Success: No orphaned vehicles found.")
            return

        logger.warning(f"Found {len(orphaned_vehicles)} orphaned vehicles:")
        print("-" * 30)
        for i, vehicle in enumerate(orphaned_vehicles, 1):
            print(f"\nVehicle {i}:")
            print(f"  Vehicle ID:   {vehicle.get('_id')}")
            print(f"  Details:      {vehicle.get('brand', '')} {vehicle.get('model', '')} ({vehicle.get('year', 'N/A')})")
            print(f"  Registration: {vehicle.get('registration_number', 'N/A')}")
            print(f"  Orphaned User ID: {vehicle.get('orphaned_user_id')}")
        print("-" * 30)
        
        logger.warning("These vehicles are linked to user_ids that do not exist.")

    except OperationFailure as e:
        logger.error(f"MongoDB Operation Failure: {e.details}")
        logger.error("This could be a permissions issue.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during aggregation: {e}", exc_info=True) # Added exc_info for better debugging


async def main():
    """
    Main function to connect, run the check, and disconnect.
    """
    try:
        logger.info("Connecting to database...")
        await connect_to_mongo()
        await find_orphaned_vehicles()
    except Exception as e:
        logger.error(f"Failed to run script: {e}")
    finally:
        logger.info("Closing database connection...")
        await close_mongo_connection()


if __name__ == "__main__":
    # This script now runs by connecting and disconnecting
    # using your application's logic.
    asyncio.run(main())

