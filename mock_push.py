import requests
import datetime
import random
import json

# Configuration
API_URL = "http://localhost:8000/api/schedules/"
EMPLOYEES = [
    {"name": "Alice", "role": "Senior Engineer"},
    {"name": "Bob", "role": "Junior Engineer"},
    {"name": "Charlie", "role": "Support Specialist"}
]
SHIFTS = ["Morning", "Afternoon", "Night"]
START_DATE = datetime.date.today()
DAYS_TO_GENERATE = 30

def generate_and_push():
    print(f"Starting simulation. Pushing to {API_URL}...")
    
    current_date = START_DATE
    
    # Simple rotation: Alice -> Bob -> Charlie -> Alice ...
    # But let's make it so every day, all 3 shifts are covered by 3 people randomly or cyclically
    
    for day_offset in range(DAYS_TO_GENERATE):
        date_str = (current_date + datetime.timedelta(days=day_offset)).strftime("%Y-%m-%d")
        
        # Shuffle employees for this day's shifts
        daily_staff = EMPLOYEES.copy()
        # Rotate based on day to make it look like a pattern
        # Shift 0 (Morning): (day) % 3
        # Shift 1 (Afternoon): (day + 1) % 3
        # Shift 2 (Night): (day + 2) % 3
        
        schedule_map = [
            (daily_staff[day_offset % 3], "Morning"),
            (daily_staff[(day_offset + 1) % 3], "Afternoon"),
            (daily_staff[(day_offset + 2) % 3], "Night"),
        ]
        
        for staff, shift_type in schedule_map:
            # Simulate "Unknown" external data structure
            # Instead of standard fields, we use custom keys to test the backend mapping
            payload = {
                "employee": staff["name"],
                "date": date_str,
                "shift": shift_type,
                "meta": {
                    "role": staff["role"],
                    "weather": random.choice(["Sunny", "Cloudy", "Rainy"]),
                    "location": f"Zone-{random.randint(1, 5)}"
                },
                "source_system": "HR_LEGACY_V1"
            }
            
            try:
                response = requests.post(API_URL, json=payload)
                if response.status_code == 201:
                    print(f"[OK] {date_str}: {staff['name']} - {shift_type}")
                else:
                    print(f"[FAIL] {response.status_code} - {response.text}")
            except Exception as e:
                print(f"[ERROR] {e}")

    print("Simulation complete.")

if __name__ == "__main__":
    generate_and_push()
