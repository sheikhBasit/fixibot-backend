import asyncio
import httpx

# Configuration
BASE_URL = "http://localhost:8000"  # Adjust port if different
ENDPOINT = "/mechanics/search/nearby"

async def test_live_search():
    print(f"📡 Connecting to {BASE_URL}...")

    # Define your search parameters
    params = {
        "latitude": 30.0,       # Replace with coordinates near your real data
        "longitude": 70.0, 
        "max_distance_km": 10,  # Start small to test auto-expansion
        "min_experience": 2,
        "limit": 50             # Testing your new limit
        # "city": "Lahore"      # Optional: Add if filtering by city
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{BASE_URL}{ENDPOINT}", params=params)
            
            if response.status_code == 200:
                mechanics = response.json()
                print(f"✅ Success! Status: {response.status_code}")
                print(f"📦 Found {len(mechanics)} mechanics.")
                
                # Print details to verify data
                for m in mechanics[:3]:
                    print(f"   - {m.get('name')} (Dist: {m.get('distance', 'N/A')} km)")
            else:
                print(f"❌ Failed. Status: {response.status_code}")
                print(f"   Error: {response.text}")

        except httpx.RequestError as exc:
            print(f"❌ Connection Error: {exc}")

if __name__ == "__main__":
    # Make sure you installed httpx: pip install httpx
    asyncio.run(test_live_search())