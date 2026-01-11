import asyncio
from bson import ObjectId
from dotenv import load_dotenv

# Import the database connection logic from your existing backend code
from database import connect_to_mongo, close_mongo_connection, db

# Load env vars to ensure settings in config.py work correctly
load_dotenv()

async def cleanup():
    print("Connecting to MongoDB using backend configuration...")
    # Initialize the connection using your existing database.py logic
    await connect_to_mongo()
    
    try:
        # --- 1. Cleanup Vehicles (Missing Owners) ---
        print("\n--- Checking Vehicles ---")
        # Use db.vehicles_collection from your Database class
        vehicles = await db.vehicles_collection.find().to_list(length=10000)
        orphaned_vehicle_ids = []
        
        for vehicle in vehicles:
            user_id = vehicle.get("user_id")
            if not user_id:
                print(f"Vehicle {vehicle['_id']} has NO user_id field.")
                orphaned_vehicle_ids.append(vehicle['_id'])
                continue
            
            # Ensure user_id is an ObjectId for querying
            if isinstance(user_id, str):
                user_id = ObjectId(user_id)
                
            user = await db.users_collection.find_one({"_id": user_id})
            if not user:
                print(f"Vehicle {vehicle['_id']} points to missing User {user_id}")
                orphaned_vehicle_ids.append(vehicle['_id'])

        print(f"Found {len(orphaned_vehicle_ids)} orphaned vehicles.")
        
        # --- 2. Cleanup Mechanic Services (Missing User, Mechanic, or Vehicle) ---
        print("\n--- Checking Mechanic Services ---")
        # Use db.mechanic_service_collection from your Database class
        services = await db.mechanic_service_collection.find().to_list(length=10000)
        orphaned_service_ids = []

        for service in services:
            is_orphan = False
            service_id = service["_id"]
            
            # Check User
            user_id = service.get("user_id")
            if user_id:
                if isinstance(user_id, str): user_id = ObjectId(user_id)
                user = await db.users_collection.find_one({"_id": user_id})
                if not user:
                    print(f"Service {service_id} points to missing User {user_id}")
                    is_orphan = True
            
            # Check Mechanic
            mechanic_id = service.get("mechanic_id")
            if mechanic_id:
                if isinstance(mechanic_id, str): mechanic_id = ObjectId(mechanic_id)
                mechanic = await db.mechanics_collection.find_one({"_id": mechanic_id})
                if not mechanic:
                    print(f"Service {service_id} points to missing Mechanic {mechanic_id}")
                    is_orphan = True

            # Check Vehicle
            vehicle_id = service.get("vehicle_id")
            if vehicle_id:
                if isinstance(vehicle_id, str): vehicle_id = ObjectId(vehicle_id)
                vehicle = await db.vehicles_collection.find_one({"_id": vehicle_id})
                if not vehicle:
                    print(f"Service {service_id} points to missing Vehicle {vehicle_id}")
                    is_orphan = True
            
            if is_orphan:
                orphaned_service_ids.append(service_id)

        print(f"Found {len(orphaned_service_ids)} orphaned services.")

        # --- DELETION STEP ---
        if orphaned_vehicle_ids or orphaned_service_ids:
            confirm = input("\nDo you want to DELETE these orphaned records? (yes/no): ")
            if confirm.lower() == "yes":
                if orphaned_vehicle_ids:
                    res = await db.vehicles_collection.delete_many({"_id": {"$in": orphaned_vehicle_ids}})
                    print(f"Deleted {res.deleted_count} vehicles.")
                
                if orphaned_service_ids:
                    res = await db.mechanic_service_collection.delete_many({"_id": {"$in": orphaned_service_ids}})
                    print(f"Deleted {res.deleted_count} mechanic services.")
                print("Cleanup complete.")
            else:
                print("Operation cancelled. No data deleted.")
        else:
            print("\nNo orphaned records found! Your database is clean.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Ensure connection is closed properly
        await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(cleanup())