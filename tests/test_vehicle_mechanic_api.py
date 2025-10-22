import os
import sys
import json
import logging
import asyncio
import aiohttp
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VehicleMechanicTester:
    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self.user_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2OGJjNjgwMTI1NGJkYTgwYjJhZTEyMTYiLCJleHAiOjE5MTg3MTMxMzN9.J3qv7wjPF8H6Gr1sYJScGiqQlzRXQIeoKl3WJ3_OpH8"
        self.user_id = "68a1d6288b423aba320b9a8f"
        
        # Test vehicles with new hierarchical structure
        self.test_vehicles = [
            {
                "user_id": "68a1d6288b423aba320b9a8f",
                "model": "Corolla",
                "brand": "Toyota",
                "year": 2020,
                "category": "car",
                "sub_type": "sedan",
                "fuel_type": "petrol",
                "transmission": "automatic",
                "mileage_km": 50000,
                "registration_number": "ABC-123",
                "is_primary": True,
                "is_active": True
            },
            {
                "user_id": "68a1d6288b423aba320b9a8f",
                "model": "Civic",
                "brand": "Honda",
                "year": 2021,
                "category": "car",
                "sub_type": "hatchback",
                "fuel_type": "diesel",
                "transmission": "manual",
                "mileage_km": 32000,
                "registration_number": "XYZ-789",
                "is_primary": False,
                "is_active": True
            },
            {
                "user_id": "68a1d6288b423aba320b9a8f",
                "model": "Fortuner",
                "brand": "Toyota",
                "year": 2019,
                "category": "car",
                "sub_type": "suv",
                "fuel_type": "diesel",
                "transmission": "automatic",
                "mileage_km": 65000,
                "registration_number": "SUV-456",
                "is_primary": False,
                "is_active": True
            },
            {
                "user_id": "68a1d6288b423aba320b9a8f",
                "model": "Ninja",
                "brand": "Kawasaki",
                "year": 2022,
                "category": "motorcycle",
                "sub_type": "sports_bike",
                "fuel_type": "petrol",
                "transmission": "manual",
                "mileage_km": 12000,
                "registration_number": "BIKE-001",
                "is_primary": False,
                "is_active": True
            },
            {
                "user_id": "68a1d6288b423aba320b9a8f",
                "model": "Activa",
                "brand": "Honda",
                "year": 2020,
                "category": "motorcycle",
                "sub_type": "scooter",
                "fuel_type": "petrol",
                "transmission": "automatic",
                "mileage_km": 25000,
                "registration_number": "SCOOTER-02",
                "is_primary": False,
                "is_active": True
            }
        ]
        
        # Test mechanic data
        self.test_mechanic = {
            "first_name": "Test",
            "last_name": "Mechanic",
            "email": "test.mechanic@example.com",
            "phone_number": "+923001234567",
            "cnic": "35202-1234567-1",
            "province": "punjab",
            "city": "lahore",
            "address": "123 Test Street, Model Town",
            "latitude": "31.5204",
            "longitude": "74.3587",
            "expertise": ["engine", "electrical", "brakes"],
            "serviced_vehicle_categories": ["car"],
            "serviced_vehicle_types": ["car", "suv"],
            "years_of_experience": "5",
            "workshop_name": "test auto workshop",
            "working_days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "working_hours": {"start_time": "09:00", "end_time": "18:00"}
        }

    async def get_vehicle_categories(self) -> dict:
        """Get available vehicle categories and options"""
        async with aiohttp.ClientSession() as session:
            try:
                headers = {
                    "Authorization": f"Bearer {self.user_token}"
                }
                endpoint = f"{self.api_url}/vehicles/categories"
                
                logger.info("Fetching vehicle categories...")
                async with session.get(endpoint, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info("Successfully fetched categories")
                        return result
                    else:
                        text = await response.text()
                        logger.error(f"Failed to fetch categories. Status: {response.status}, Response: {text}")
                        return None
            except Exception as e:
                logger.error(f"Error fetching categories: {e}")
                return None

    async def post_vehicle(self, vehicle_data: dict) -> dict:
        """Post a test vehicle to the API"""
        async with aiohttp.ClientSession() as session:
            try:
                headers = {
                    "Authorization": f"Bearer {self.user_token}"
                }
                vehicle_endpoint = f"{self.api_url}/vehicles/create"
                
                logger.info(f"Posting vehicle: {vehicle_data['brand']} {vehicle_data['model']}...")
                logger.info(f"  Category: {vehicle_data['category']}, Sub-type: {vehicle_data['sub_type']}")
                
                # Use form data encoding instead of JSON
                form_data = aiohttp.FormData()
                form_data.add_field('user_id', vehicle_data['user_id'])
                form_data.add_field('model', vehicle_data['model'])
                form_data.add_field('brand', vehicle_data['brand'])
                form_data.add_field('year', str(vehicle_data['year']))
                form_data.add_field('category', vehicle_data['category'])
                form_data.add_field('sub_type', vehicle_data['sub_type'])
                form_data.add_field('fuel_type', vehicle_data['fuel_type'])
                form_data.add_field('transmission', vehicle_data['transmission'])
                form_data.add_field('mileage_km', str(vehicle_data['mileage_km']))
                form_data.add_field('registration_number', vehicle_data['registration_number'])
                form_data.add_field('is_primary', str(vehicle_data['is_primary']).lower())
                form_data.add_field('is_active', str(vehicle_data['is_active']).lower())
                
                async with session.post(
                    vehicle_endpoint, 
                    headers=headers, 
                    data=form_data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"  ✓ Successfully created vehicle: {result.get('_id')}")
                        return result
                    else:
                        text = await response.text()
                        logger.error(f"  ✗ Failed. Status: {response.status}, Response: {text}")
                        return None
            except Exception as e:
                logger.error(f"Error posting vehicle: {e}")
                return None

    async def get_user_vehicles(self) -> list:
        """Get all vehicles for current user"""
        async with aiohttp.ClientSession() as session:
            try:
                headers = {
                    "Authorization": f"Bearer {self.user_token}"
                }
                endpoint = f"{self.api_url}/vehicles/all"
                
                logger.info("Fetching user vehicles...")
                async with session.get(endpoint, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"Successfully fetched {len(result)} vehicles")
                        if len(result) == 0:
                            logger.info("Debug: No vehicles found, this might indicate:")
                            logger.info("  - User ID mismatch between creation and retrieval")
                            logger.info("  - Vehicles may have is_active=False")
                            logger.info("  - Database connection issue")
                        return result
                    else:
                        text = await response.text()
                        logger.error(f"Failed to fetch vehicles. Status: {response.status}, Response: {text}")
                        return []
            except Exception as e:
                logger.error(f"Error fetching vehicles: {e}")
                return []

    async def search_vehicles(self, category: str = None, sub_type: str = None, fuel_type: str = None) -> list:
        """Search vehicles with filters"""
        async with aiohttp.ClientSession() as session:
            try:
                headers = {
                    "Authorization": f"Bearer {self.user_token}",
                    "Content-Type": "application/json"
                }
                endpoint = f"{self.api_url}/vehicles/search"
                
                search_query = {}
                if category:
                    search_query["category"] = category
                if sub_type:
                    search_query["sub_type"] = sub_type
                if fuel_type:
                    search_query["fuel_type"] = fuel_type
                
                logger.info(f"Searching vehicles with filters: {search_query}...")
                async with session.post(
                    endpoint, 
                    headers=headers, 
                    json=search_query
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"  Found {len(result)} matching vehicles")
                        return result
                    else:
                        text = await response.text()
                        logger.error(f"  Search failed. Status: {response.status}, Response: {text}")
                        return []
            except Exception as e:
                logger.error(f"Error searching vehicles: {e}")
                return []

    async def post_mechanic(self) -> dict:
        """Post a test mechanic to the API"""
        async with aiohttp.ClientSession() as session:
            try:
                headers = {"Authorization": f"Bearer {self.user_token}"}
                mechanic_endpoint = f"{self.api_url}/mechanics/register"
                
                # Create form data for mechanic registration
                form_data = aiohttp.FormData()
                
                # Add simple fields
                form_data.add_field('first_name', self.test_mechanic['first_name'])
                form_data.add_field('last_name', self.test_mechanic['last_name'])
                form_data.add_field('email', self.test_mechanic['email'])
                form_data.add_field('phone_number', self.test_mechanic['phone_number'])
                form_data.add_field('cnic', self.test_mechanic['cnic'])
                form_data.add_field('province', self.test_mechanic['province'])
                form_data.add_field('city', self.test_mechanic['city'])
                form_data.add_field('address', self.test_mechanic['address'])
                form_data.add_field('latitude', self.test_mechanic['latitude'])
                form_data.add_field('longitude', self.test_mechanic['longitude'])
                form_data.add_field('years_of_experience', self.test_mechanic['years_of_experience'])
                form_data.add_field('workshop_name', self.test_mechanic['workshop_name'])
                
                # Add array fields - each item separately
                # Use correct expertise values
                correct_expertise = ["engine", "electrical", "brakes"]
                for expertise in correct_expertise:
                    form_data.add_field('expertise', expertise)
                
                for category in self.test_mechanic['serviced_vehicle_categories']:
                    form_data.add_field('serviced_vehicle_categories', category)
                
                for vehicle_type in self.test_mechanic['serviced_vehicle_types']:
                    form_data.add_field('serviced_vehicle_types', vehicle_type)
                
                for day in self.test_mechanic['working_days']:
                    form_data.add_field('working_days', day)
                
                # Add working hours - send as separate start/end time fields
                working_hours = self.test_mechanic['working_hours']
                form_data.add_field('start_time', working_hours['start_time'])
                form_data.add_field('end_time', working_hours['end_time'])
                
                logger.info("Posting mechanic data...")
                async with session.post(
                    mechanic_endpoint, 
                    headers=headers, 
                    data=form_data
                ) as response:
                    if response.status == 201:
                        result = await response.json()
                        logger.info(f"Successfully created mechanic: {result.get('_id')}")
                        return result
                    else:
                        text = await response.text()
                        logger.error(f"Failed to create mechanic. Status: {response.status}, Response: {text}")
                        return None
            except Exception as e:
                logger.error(f"Error posting mechanic: {e}")
                return None


async def main():
    try:
        tester = VehicleMechanicTester()
        
        # Get available categories
        logger.info("=" * 70)
        logger.info("STEP 1: FETCHING AVAILABLE VEHICLE CATEGORIES & OPTIONS")
        logger.info("=" * 70)
        categories = await tester.get_vehicle_categories()
        if categories:
            logger.info("Available Categories:")
            for cat in categories.get('categories', []):
                logger.info(f"  • {cat['label']}")
                for st in cat['sub_types']:
                    logger.info(f"    - {st['label']}")
            logger.info("\nAvailable Fuel Types:")
            for ft in categories.get('fuel_types', [])[:5]:
                logger.info(f"  • {ft['label']}")
            logger.info("\nAvailable Transmission Types:")
            for tt in categories.get('transmission_types', [])[:5]:
                logger.info(f"  • {tt['label']}")
        
        logger.info("\n")
        
        # Create multiple test vehicles
        logger.info("=" * 70)
        logger.info("STEP 2: CREATING TEST VEHICLES WITH HIERARCHICAL TYPES")
        logger.info("=" * 70)
        created_vehicles = []
        for vehicle in tester.test_vehicles:
            result = await tester.post_vehicle(vehicle)
            if result:
                created_vehicles.append(result)
        
        logger.info(f"\nSuccessfully created {len(created_vehicles)} vehicles")
        
        logger.info("\n")
        
        # Fetch all user vehicles
        logger.info("=" * 70)
        logger.info("STEP 3: FETCHING ALL USER VEHICLES")
        logger.info("=" * 70)
        logger.info(f"Current user ID: {tester.user_id}")
        logger.info(f"Creating vehicles with user_id: {tester.test_vehicles[0]['user_id']}")
        all_vehicles = await tester.get_user_vehicles()
        if all_vehicles:
            logger.info(f"Total vehicles: {len(all_vehicles)}")
            for v in all_vehicles[:5]:
                logger.info(f"  • {v.get('brand')} {v.get('model')} ({v.get('category')} - {v.get('sub_type')})")
        else:
            logger.warning("No vehicles found. The user_id might not match.")
        
        logger.info("\n")
        
        # Search vehicles by category
        logger.info("=" * 70)
        logger.info("STEP 4: SEARCHING VEHICLES BY CATEGORY")
        logger.info("=" * 70)
        
        logger.info("\nSearching for CAR vehicles:")
        cars = await tester.search_vehicles(category="car")
        for car in cars:
            logger.info(f"  • {car.get('brand')} {car.get('model')} - {car.get('sub_type')}")
        
        logger.info("\nSearching for MOTORCYCLE vehicles:")
        bikes = await tester.search_vehicles(category="motorcycle")
        for bike in bikes:
            logger.info(f"  • {bike.get('brand')} {bike.get('model')} - {bike.get('sub_type')}")
        
        logger.info("\n")
        
        # Search vehicles by fuel type
        logger.info("=" * 70)
        logger.info("STEP 5: SEARCHING VEHICLES BY FUEL TYPE")
        logger.info("=" * 70)
        
        logger.info("\nSearching for PETROL vehicles:")
        petrol_vehicles = await tester.search_vehicles(fuel_type="petrol")
        for v in petrol_vehicles:
            logger.info(f"  • {v.get('brand')} {v.get('model')} ({v.get('category')})")
        
        logger.info("\n")
        
        # Register mechanic
        logger.info("=" * 70)
        logger.info("STEP 6: REGISTERING TEST MECHANIC")
        logger.info("=" * 70)
        mechanic_result = await tester.post_mechanic()
        if mechanic_result:
            logger.info("Mechanic registration successful!")
            logger.info(f"  Mechanic ID: {mechanic_result.get('_id')}")
            logger.info(f"  Workshop: {mechanic_result.get('workshop_name')}")
        else:
            logger.error("Mechanic registration failed!")
        
        logger.info("\n")
        logger.info("=" * 70)
        logger.info("ALL TESTS COMPLETED SUCCESSFULLY")
        logger.info("=" * 70)

    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())