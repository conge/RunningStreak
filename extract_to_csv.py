import json
import csv
from datetime import datetime

INPUT_FILE = "activities.json"
OUTPUT_FILE = "results.csv"

# Column headers matching the runningRecords CSV format
HEADERS = ["streak#", "date", "startTime", "runningTime(min)", "Distance(mile)", "Shoes", "temperature(C)", "weather"]

MILES_PER_METER = 0.000621371

def parse_moving_time(moving_time_str: str) -> str:
    """Convert 'H:MM:SS' to total minutes as a float string."""
    try:
        parts = moving_time_str.split(":")
        if len(parts) == 3:
            hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
        elif len(parts) == 2:
            hours, minutes, seconds = 0, int(parts[0]), int(parts[1])
        else:
            return ""
        total_minutes = hours * 60 + minutes + seconds / 60.0
        # Format: keep as integer if whole, otherwise with decimals (matching CSV style)
        if total_minutes == int(total_minutes):
            return str(int(total_minutes))
        return f"{total_minutes:.2f}"
    except (ValueError, IndexError):
        return ""

def format_date(date_str: str) -> str:
    """Convert 'YYYY-MM-DD HH:MM:SS' to 'YYYYMMDD'."""
    try:
        dt = datetime.strptime(date_str.strip(), "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%Y%m%d")
    except ValueError:
        return date_str[:10].replace("-", "")

def format_time(date_str: str) -> str:
    """Convert 'YYYY-MM-DD HH:MM:SS' to 'HH:MM AM/PM'."""
    try:
        dt = datetime.strptime(date_str.strip(), "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%I:%M %p").lstrip("0")  # Remove leading zero from hour
    except ValueError:
        return ""

def convert_distance_to_miles(distance_meters: float) -> str:
    """Convert meters to miles, formatted to 2 decimal places."""
    miles = distance_meters * MILES_PER_METER
    return f"{miles:.2f}"

def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        activities = json.load(f)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)

        for activity in activities:
            streak = activity.get("streak", "")
            start_date_local = activity.get("start_date_local", "")
            moving_time = activity.get("moving_time", "")
            distance = activity.get("distance", 0)

            row = [
                streak,                                # streak#
                format_date(start_date_local),          # date (YYYYMMDD)
                format_time(start_date_local),          # startTime (HH:MM AM/PM)
                parse_moving_time(moving_time),         # runningTime(min)
                convert_distance_to_miles(distance),    # Distance(mile)
                "",                                     # Shoes (N/A in JSON)
                "",                                     # temperature(C) (N/A in JSON)
                "",                                     # weather (N/A in JSON)
            ]
            writer.writerow(row)

    print(f"Done! Wrote {len(activities)} records to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
