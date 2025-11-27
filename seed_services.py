import asyncio
import os
import random
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MONGO_URL = os.getenv("MONGODB_URL")
DB_NAME = os.getenv("MONGO_DB", "fixibot_db")

if not MONGO_URL:
    print("❌ Error: MONGODB_URL not found in environment variables.")
    exit(1)

# --- DATA CONFIGURATION ---
SERVICE_ISSUES = {
    "car": [
        ("Engine overheating", "repair"),
        ("Brake pads need replacement", "maintenance"),
        ("Check engine light is on", "diagnostic"),
        ("AC blowing hot air", "repair"),
        ("Oil change and filter replacement", "maintenance"),
        ("Car vibrating at high speeds", "inspection"),
        ("Battery dead, need jump start", "emergency"),
        ("Suspension making squeaky noise", "repair"),
        ("Radiator leaking coolant", "repair"),
        ("Transmission slipping gears", "repair")
    ],
    "bike": [
        ("Chain sprocket loose", "maintenance"),
        ("Self start not working", "electrical"),
        ("Rear tyre puncture", "repair"),
        ("Tuning and oil change", "maintenance"),
        ("Headlight bulb fused", "electrical"),
        ("Clutch wire broken", "emergency"),
        ("Engine making ticking noise", "diagnostic"),
        ("Brake shoes worn out", "maintenance"),
        ("Handlebar alignment issue", "inspection"),
        ("Fuel tank leakage", "repair")
    ]
}

STATUSES = ["pending", "in_progress", "completed", "cancelled"]
REGIONS = ["Gulberg", "DHA", "Johar Town", "Model Town", "Township", "Samanabad", "Cantt"]

# Types that STRICTLY require a cost in your Pydantic model
COST_REQUIRED_TYPES = ["repair", "maintenance", "emergency"]

async def seed_services():
    print(f"Connecting to MongoDB at {MONGO_URL}...")
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # --- 0. AUTO-FIX: Delete Broken Records ---
    # This removes the records causing your 500 Error (where cost is None but type is Repair/Maintenance)
    print("🧹 Cleaning up invalid records that cause API crashes...")
    delete_result = await db.mechanic_service_collection.delete_many({
        "service_type": {"$in": COST_REQUIRED_TYPES},
        "service_cost": None,
        "status": {"$ne": "cancelled"}
    })
    if delete_result.deleted_count > 0:
        print(f"   ✅ Deleted {delete_result.deleted_count} invalid service records.")
    else:
        print("   ✨ Database is clean.")

    # --- 1. Fetch Dependencies ---
    print("Fetching Users, Vehicles, and Mechanics...")
    users = await db.users.find().to_list(length=1000)
    mechanics = await db.mechanics.find().to_list(length=1000)
    vehicles = await db.vehicles.find().to_list(length=1000)

    if not users or not mechanics or not vehicles:
        print("❌ Missing dependencies (Users, Mechanics, or Vehicles). Run previous seed scripts first.")
        return

    print(f"✅ Found {len(users)} Users, {len(mechanics)} Mechanics, {len(vehicles)} Vehicles.")

    services_to_create = []
    
    # --- 2. Generate Services ---
    print("Generating new service records...")
    
    for _ in range(30):
        vehicle = random.choice(vehicles)
        user_id = vehicle.get("user_id")
        
        if not user_id: continue

        mechanic = random.choice(mechanics)
        
        # Determine vehicle type and issue
        v_type = vehicle.get("type", "car").lower()
        if v_type not in SERVICE_ISSUES: v_type = "car"
        issue_desc, service_type = random.choice(SERVICE_ISSUES[v_type])

        # Generate Dates
        days_ago = random.randint(0, 30)
        created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
        
        status = random.choice(STATUSES)
        updated_at = None
        est_time = None
        
        # 🔥 CRITICAL FIX: Always generate a cost estimate
        # Your model requires this for Repairs/Maintenance even if status is Pending
        cost = random.randint(500, 15000) 

        if status in ["completed", "in_progress"]:
            updated_at = created_at + timedelta(hours=random.randint(2, 48))
            est_time = f"{random.randint(1, 5)} hours"
        
        # Randomly remove cost ONLY if type allows it (Diagnostic/Inspection) AND status isn't completed
        if service_type not in COST_REQUIRED_TYPES and status != "completed":
            if random.choice([True, False]):
                cost = None

        service_payload = {
            "user_id": user_id,
            "mechanic_id": mechanic["_id"],
            "vehicle_id": vehicle["_id"],
            "issue_description": issue_desc,
            "service_type": service_type,
            "service_cost": cost,  # Now populated correctly
            "region": random.choice(REGIONS),
            "estimated_time": est_time,
            "status": status,
            "images": [],
            "created_at": created_at,
            "updated_at": updated_at
        }

        services_to_create.append(service_payload)

    # --- 3. Bulk Insert ---
    if services_to_create:
        result = await db.mechanic_service_collection.insert_many(services_to_create)
        print(f"🚀 Successfully inserted {len(result.inserted_ids)} valid service records!")
    else:
        print("⚠️ No services generated.")

if __name__ == "__main__":
    asyncio.run(seed_services())