import urllib.request
import json
import sys
from datetime import datetime, timedelta

# Key waypoints for Option 1
LOCATIONS = {
    "KTN": {"name": "Ketchikan", "lat": 55.3556, "lon": -131.7136},
    "WRG": {"name": "Wrangell", "lat": 56.4844, "lon": -132.3697},
    "PSG": {"name": "Petersburg", "lat": 56.8017, "lon": -132.9453},
    "JNU": {"name": "Juneau", "lat": 58.3547, "lon": -134.5762},
    "YAK": {"name": "Yakutat", "lat": 59.5033, "lon": -139.6603},
    "CDV": {"name": "Cordova", "lat": 60.4919, "lon": -145.4778},
    "ANC": {"name": "Anchorage", "lat": 61.1744, "lon": -149.9964},
}

# Weather thresholds (WMO codes 0-3 = Clear to Partly Cloudy)
CLEAR_WMO_CODES = {0, 1, 2, 3}
MAX_CLOUD_COVER = 60  # Percentage
MAX_POP = 20          # Probability of Precipitation (%)

def fetch_weather(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        "&hourly=temperature_2m,precipitation_probability,cloud_cover,weather_code"
        "&timezone=America%2FAnchorage"
    )
    req = urllib.request.Request(url, headers={'User-Agent': 'AlaskaMilkRunTracker/1.0'})
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())

def evaluate_time_window(data, target_date, start_hour, end_hour):
    """Evaluates weather during specific flight hours for a given day."""
    times = data["hourly"]["time"]
    clouds = data["hourly"]["cloud_cover"]
    pops = data["hourly"]["precipitation_probability"]
    codes = data["hourly"]["weather_code"]

    hours_checked = 0
    bad_hours = 0

    for idx, t_str in enumerate(times):
        dt = datetime.fromisoformat(t_str)
        if dt.date() == target_date and start_hour <= dt.hour <= end_hour:
            hours_checked += 1
            if (
                clouds[idx] > MAX_CLOUD_COVER
                or pops[idx] > MAX_POP
                or codes[idx] not in CLEAR_WMO_CODES
            ):
                bad_hours += 1

    if hours_checked == 0:
        return False, "No data available"
    
    is_good = bad_hours == 0
    summary = f"{bad_hours}/{hours_checked} hours had clouds/rain"
    return is_good, summary

def check_forecast_windows():
    print("Fetching Alaska weather forecasts...\n")
    weather_cache = {code: fetch_weather(loc["lat"], loc["lon"]) for code, loc in LOCATIONS.items()}
    
    today = datetime.now().date()
    good_windows_found = False

    # Check consecutive 2-day windows over the next 5 days
    for day_offset in range(1, 6):
        day1 = today + timedelta(days=day_offset)
        day2 = day1 + timedelta(days=1)

        print(f"--- Evaluating Window: Day 1 ({day1}) & Day 2 ({day2}) ---")

        # Day 1 Assessment (AS 65: SEA -> JNU between 07:00 and 13:00 AKDT)
        day1_stops = ["KTN", "WRG", "PSG", "JNU"]
        day1_passed = True
        print("  Day 1 (AS 65 - Inside Passage):")
        for stop in day1_stops:
            ok, msg = evaluate_time_window(weather_cache[stop], day1, 7, 13)
            status = "CLEAR" if ok else "CLOUDY/RAIN"
            print(f"    - {stop} ({LOCATIONS[stop]['name']}): [{status}] ({msg})")
            if not ok:
                day1_passed = False

        # Day 2 Assessment (AS 61: JNU -> ANC between 09:00 and 14:00 AKDT)
        day2_stops = ["JNU", "YAK", "CDV", "ANC"]
        day2_passed = True
        print("  Day 2 (AS 61 - Glacier Route):")
        for stop in day2_stops:
            ok, msg = evaluate_time_window(weather_cache[stop], day2, 9, 14)
            status = "CLEAR" if ok else "CLOUDY/RAIN"
            print(f"    - {stop} ({LOCATIONS[stop]['name']}): [{status}] ({msg})")
            if not ok:
                day2_passed = False

        if day1_passed and day2_passed:
            good_windows_found = True
            print(f"\n PERFECTION ALERT! Perfect 2-day flight window found starting {day1}!\n")
        else:
            print(f"  Result: Window on {day1}-{day2} does not meet optimal criteria.\n")

    if good_windows_found:
        print("CLEAR WINDOW DETECTED: Triggering notification alert via exit code 1.")
        sys.exit(1)  # Triggers GitHub Actions notification email
    else:
        print("No optimal 2-day weather windows found in the current 7-day forecast.")
        sys.exit(0)

if __name__ == "__main__":
    check_forecast_windows()
