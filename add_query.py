import requests
import random
import json

# API Endpoint
API_URL = "http://localhost:8000/mechanics/register"

# Common Lahore Locations (Lat, Long) mapping to realistic Addresses
LOCATIONS = [
    {"area": "Gulberg III", "lat": 31.5102, "long": 74.3441, "addr": "Near Liberty Market, Gulberg III"},
    {"area": "DHA Phase 5", "lat": 31.4697, "long": 74.4190, "addr": "Bedian Road, DHA Phase 5"},
    {"area": "Johar Town", "lat": 31.4697, "long": 74.2928, "addr": "G-1 Market, Johar Town"},
    {"area": "Model Town", "lat": 31.4855, "long": 74.3263, "addr": "Link Road, Model Town"},
    {"area": "Wapda Town", "lat": 31.4337, "long": 74.2750, "addr": "Main Boulevard, Wapda Town"},
    {"area": "Township", "lat": 31.4390, "long": 74.3125, "addr": "College Road, Township"},
    {"area": "Garden Town", "lat": 31.5037, "long": 74.3317, "addr": "Barkat Market, Garden Town"},
    {"area": "Allama Iqbal Town", "lat": 31.5196, "long": 74.2832, "addr": "Moon Market, Iqbal Town"},
    {"area": "Shadman", "lat": 31.5432, "long": 74.3322, "addr": "Jail Road, Shadman"},
    {"area": "Mughalpura", "lat": 31.5668, "long": 74.3875, "addr": "Shalimar Link Road, Mughalpura"},
    {"area": "Bahria Town", "lat": 31.3668, "long": 74.1872, "addr": "Talwar Chowk, Bahria Town"},
    {"area": "Valencia", "lat": 31.4089, "long": 74.2563, "addr": "Main Roundabout, Valencia Town"},
    {"area": "Lahore Cantt", "lat": 31.5497, "long": 74.3833, "addr": "Sadar Bazar, Lahore Cantt"},
    {"area": "Samanabad", "lat": 31.5382, "long": 74.3041, "addr": "Main Road, Samanabad"},
    {"area": "Garhi Shahu", "lat": 31.5635, "long": 74.3483, "addr": "Allama Iqbal Road, Garhi Shahu"},
    {"area": "Muslim Town", "lat": 31.5211, "long": 74.3276, "addr": "Wahdat Road, Muslim Town"},
    {"area": "Faisal Town", "lat": 31.4776, "long": 74.3033, "addr": "Kotha Pind, Faisal Town"},
    {"area": "Sabzazar", "lat": 31.5144, "long": 74.2536, "addr": "Multan Road, Sabzazar"},
    {"area": "Gulshan-e-Ravi", "lat": 31.5387, "long": 74.2837, "addr": "Main Boulevard, Gulshan-e-Ravi"},
    {"area": "Harbanspura", "lat": 31.5925, "long": 74.4197, "addr": "Canal Road, Harbanspura"},
]

MECHANICS_DATA = [
    # BIKE MECHANICS (10)
    ("Muhammad", "Bilal", "Bilal Autos", "bike", ["engine", "oil_change", "tyre", "brakes"]),
    ("Usman", "Ghani", "Ghani Bike Point", "bike", ["engine", "tuning", "electrical"]),
    ("Rizwan", "Ahmed", "Rizwan Honda Center", "bike", ["oil_change", "chain_sprocket", "brakes"]),
    ("Faisal", "Jutt", "Faisal Ustad", "bike", ["engine", "puncture", "tyre"]),
    ("Imran", "Khan", "IK Bike Repair", "bike", ["electrical", "battery", "lights"]),
    ("Rashid", "Minhas", "Rashid Autos", "bike", ["engine", "suspension", "oil_change"]),
    ("Tariq", "Mehmood", "Tariq Tuning Center", "bike", ["tuning", "carburetor", "filters"]),
    ("Sajid", "Ali", "Sajid Bike Care", "bike", ["brakes", "oil_change", "washing"]),
    ("Noman", "Ejaz", "Nomi Motorsports", "bike", ["modification", "engine", "exhaust"]),
    ("Kamran", "Akmal", "Kami Bike Works", "bike", ["general_service", "oil_change"]),

    # CAR MECHANICS (10)
    ("Waseem", "Badami", "Waseem Car Care", "car", ["ac", "electrical", "diagnostics"]),
    ("Asif", "Zardari", "Asif Motors", "car", ["engine", "transmission", "suspension"]),
    ("Nasir", "Jamshed", "Nasir Denting Painting", "car", ["bodywork", "painting", "denting"]),
    ("Javed", "Miandad", "Javed Autos", "car", ["oil_change", "filters", "tuning"]),
    ("Ahsan", "Iqbal", "Ahsan Electrician", "car", ["electrical", "battery", "wiring"]),
    ("Babar", "Azam", "Babar Auto Workshop", "car", ["engine", "suspension", "steering"]),
    ("Shaheen", "Afridi", "Eagle Eye Diagnostics", "car", ["diagnostics", "sensors", "ecu"]),
    ("Sarfaraz", "Ahmed", "Kaptaan Auto Repair", "car", ["general_service", "brakes", "suspension"]),
    ("Shoaib", "Malik", "Malik Brothers Autos", "car", ["engine", "transmission", "radiator"]),
    ("Hassan", "Ali", "Hassan Generator & Car", "car", ["electrical", "self_starter", "alternator"])
]

def generate_cnic(index):
    # Generate unique CNICs: 35202-1234567-X
    return f"35202-{1000000 + index}-1"

def generate_phone(index):
    # Generate unique Phones: +9230012345XX
    return f"+9230012345{index:02d}"

def seed_mechanics():
    print(f"🚀 Starting bulk seed for {len(MECHANICS_DATA)} mechanics in Lahore...")
    
    for i, (fname, lname, wname, vtype, skills) in enumerate(MECHANICS_DATA):
        loc = LOCATIONS[i % len(LOCATIONS)]
        
        # Slight random jitter to lat/long so they aren't perfectly stacked if areas repeat
        lat = loc["lat"] + random.uniform(-0.001, 0.001)
        lon = loc["long"] + random.uniform(-0.001, 0.001)

        # Map user friendly skills to your Enum values if necessary
        # Assuming simple mapping or using strings directly if they match Enum values
        # Your ExpertiseEnum: engine, electrical, bodywork, transmission, brakes, suspension, 
        # air_conditioning, diagnostics, oil_change, tyre, exhaust_system, battery, radiator...
        
        # Cleaning skills to match your Enum exactly
        valid_skills = []
        for s in skills:
            if s == "ac": valid_skills.append("air_conditioning")
            elif s == "tuning": valid_skills.append("diagnostics") # Approx
            elif s == "puncture": valid_skills.append("tyre")
            elif s == "lights": valid_skills.append("electrical")
            elif s == "carburetor": valid_skills.append("engine")
            elif s == "washing": valid_skills.append("bodywork") # Approx
            elif s == "modification": valid_skills.append("bodywork")
            elif s == "exhaust": valid_skills.append("exhaust_system")
            elif s == "general_service": valid_skills.append("oil_change")
            elif s == "denting": valid_skills.append("bodywork")
            elif s == "wiring": valid_skills.append("electrical")
            elif s == "steering": valid_skills.append("suspension")
            elif s == "sensors": valid_skills.append("diagnostics")
            elif s == "ecu": valid_skills.append("diagnostics")
            elif s == "self_starter": valid_skills.append("electrical")
            elif s == "alternator": valid_skills.append("electrical")
            elif s == "chain_sprocket": valid_skills.append("suspension")
            elif s == "filters": valid_skills.append("oil_change")
            else: valid_skills.append(s)
        
        # Unique constrained fields
        cnic = generate_cnic(i)
        phone = generate_phone(i)
        email = f"{fname.lower()}.{lname.lower()}{i}@fixibot.com"

        payload = {
            "first_name": fname,
            "last_name": lname,
            "email": email,
            "phone_number": phone,
            "cnic": cnic,
            "province": "Punjab",
            "city": "Lahore",
            "address": loc["addr"],
            "latitude": lat,
            "longitude": lon,
            "serviced_vehicle_types": vtype, # 'car' or 'bike'
            "years_of_experience": random.randint(2, 15),
            "workshop_name": wname,
            "start_time": "09:00",
            "end_time": "20:00"
        }

        # Prepare multipart/form-data
        # Requests handles 'data' as form fields. 
        # Lists (expertise, working_days) need to be passed as list of values to same key.
        
        data_payload = [
            ('first_name', payload['first_name']),
            ('last_name', payload['last_name']),
            ('email', payload['email']),
            ('phone_number', payload['phone_number']),
            ('cnic', payload['cnic']),
            ('province', payload['province']),
            ('city', payload['city']),
            ('address', payload['address']),
            ('latitude', str(payload['latitude'])),
            ('longitude', str(payload['longitude'])),
            ('serviced_vehicle_types', payload['serviced_vehicle_types']),
            ('years_of_experience', str(payload['years_of_experience'])),
            ('workshop_name', payload['workshop_name']),
            ('start_time', payload['start_time']),
            ('end_time', payload['end_time']),
        ]

        # Add Expertise
        for skill in list(set(valid_skills)): # Dedup
            data_payload.append(('expertise', skill))

        # Add Working Days (Mon-Sat)
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]:
            data_payload.append(('working_days', day))

        try:
            response = requests.post(API_URL, data=data_payload)
            if response.status_code == 201:
                print(f"✅ Added: {wname} ({vtype}) in {loc['area']}")
            else:
                print(f"❌ Failed: {wname} - {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Error connecting to server: {e}")

if __name__ == "__main__":
    seed_mechanics()