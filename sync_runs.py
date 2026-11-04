"""Append newly synced runs to the yearly runningRecords CSV.

Data comes from the running_page repo's generated activities feed. Only runs
newer than the CSV's latest date are added; streak numbers continue the CSV's
own counter (the upstream `streak` field uses a different numbering and is
ignored). Temperature and weather are looked up from the Open-Meteo historical
archive for the hour each run started. Shoes must be filled in by hand.

Usage:
    python3 sync_runs.py                 # update current year's CSV
    python3 sync_runs.py --dry-run       # preview without writing
    python3 sync_runs.py --csv runningRecords2027.csv
"""
import argparse
import csv
import json
import shutil
import ssl
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent
DEFAULT_ACTIVITIES = REPO.parent / "running_page" / "src" / "static" / "activities.json"
LOCAL_SNAPSHOT = REPO / "activities.json"

HEADERS = ["streak#", "date", "startTime", "runningTime(min)", "Distance(mile)",
           "Shoes", "temperature(C)", "weather"]

MILES_PER_METER = 0.000621371

# Green Lake, Seattle - where most runs start
WEATHER_LAT = 47.6804
WEATHER_LON = -122.3282
WEATHER_TZ = "America/Los_Angeles"

# WMO weather codes -> the vocabulary already used in the CSV files
WMO_MAP = {
    0: "Sunny", 1: "Sunny", 2: "Cloudy", 3: "Cloudy",
    45: "Foggy", 48: "Foggy",
    51: "Rainy", 53: "Rainy", 55: "Rainy", 56: "Rainy", 57: "Rainy",
    61: "Rainy", 63: "Rainy", 65: "Rainy", 66: "Rainy", 67: "Rainy",
    71: "Snowy", 73: "Snowy", 75: "Snowy", 77: "Snowy",
    80: "Rainy", 81: "Rainy", 82: "Rainy",
    85: "Snowy", 86: "Snowy",
    95: "Rainy", 96: "Rainy", 99: "Rainy",
}


def parse_moving_time(s: str) -> str:
    """'H:MM:SS[.frac]' -> total minutes, matching the CSV's formatting."""
    try:
        parts = [int(p) for p in str(s).split(".")[0].split(":")]
        while len(parts) < 3:
            parts.insert(0, 0)
        h, m, sec = parts
        total = h * 60 + m + sec / 60.0
        return str(int(total)) if total == int(total) else f"{total:.2f}"
    except (ValueError, IndexError):
        return ""


def fmt_temp(t: float) -> str:
    t = int(round(t))
    return f"{t:02d}" if t >= 0 else f"-{abs(t):02d}"


def _ssl_context() -> ssl.SSLContext:
    """macOS framework Python ships without usable root certs; use certifi."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def fetch_weather(start_day: str, end_day: str) -> dict:
    """{(YYYY-MM-DD, hour): (temperature, condition)} from Open-Meteo archive."""
    query = urllib.parse.urlencode({
        "latitude": WEATHER_LAT, "longitude": WEATHER_LON,
        "start_date": start_day, "end_date": end_day,
        "hourly": "temperature_2m,weather_code",
        "temperature_unit": "celsius", "timezone": WEATHER_TZ,
    })
    url = f"https://archive-api.open-meteo.com/v1/archive?{query}"
    with urllib.request.urlopen(url, timeout=60, context=_ssl_context()) as r:
        data = json.load(r)
    hourly = data["hourly"]
    out = {}
    for stamp, temp, code in zip(hourly["time"], hourly["temperature_2m"],
                                 hourly["weather_code"]):
        if temp is None:
            continue
        day, hour = stamp.split("T")
        out[(day, int(hour[:2]))] = (fmt_temp(temp), WMO_MAP.get(code, "Cloudy"))
    return out


def read_csv(path: Path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    return rows[0], rows[1:]


def write_csv(path: Path, header, rows):
    # newer CSV files carry a UTF-8 BOM so Excel keeps the Chinese-era encoding;
    # keep whatever the file already used to avoid rewriting every line.
    with open(path, "rb") as f:
        has_bom = f.read(3) == b"\xef\xbb\xbf"
    with open(path, "w", newline="", encoding="utf-8-sig" if has_bom else "utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--activities", type=Path, default=DEFAULT_ACTIVITIES)
    ap.add_argument("--csv", type=Path,
                    default=REPO / f"runningRecords{datetime.now().year}.csv")
    ap.add_argument("--no-weather", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.activities.exists():
        sys.exit(f"activities file not found: {args.activities}")
    activities = json.loads(args.activities.read_text(encoding="utf-8"))

    if not args.csv.exists():
        sys.exit(f"CSV not found: {args.csv}")
    header, existing = read_csv(args.csv)
    dated = [r for r in existing if len(r) > 1 and r[1].isdigit()]
    latest_date = max(r[1] for r in dated)
    max_streak = max(int(r[0]) for r in dated)
    print(f"{args.csv.name}: {len(dated)} rows, latest {latest_date}, streak {max_streak}")

    pending = []
    for a in activities:
        day = a["start_date_local"][:10]
        if day.replace("-", "") > latest_date:
            pending.append((day, a))
    if not pending:
        print("Already up to date.")
        return
    pending.sort(key=lambda x: (x[0], x[1]["start_date_local"]))

    days = sorted({d for d, _ in pending})
    streak_of = {d: max_streak + i + 1 for i, d in enumerate(days)}

    weather = {}
    if not args.no_weather:
        weather = fetch_weather(days[0], days[-1])
        print(f"weather fetched for {days[0]} .. {days[-1]}")

    new_rows = []
    for day, a in sorted(pending, key=lambda x: x[1]["start_date_local"], reverse=True):
        dt = datetime.strptime(a["start_date_local"], "%Y-%m-%d %H:%M:%S")
        temp, cond = weather.get((day, dt.hour), ("", ""))
        new_rows.append([
            streak_of[day],
            day.replace("-", ""),
            dt.strftime("%I:%M %p").lower(),
            parse_moving_time(a.get("moving_time", "")),
            f"{a.get('distance', 0) * MILES_PER_METER:.2f}",
            "",  # Shoes: filled in by hand
            temp,
            cond,
        ])

    print(f"adding {len(new_rows)} runs over {len(days)} days "
          f"(streak {streak_of[days[0]]}-{streak_of[days[-1]]})")
    for r in new_rows[:3] + new_rows[-2:]:
        print("  " + ",".join(map(str, r)))

    if args.dry_run:
        print("dry run, nothing written")
        return

    if args.activities == DEFAULT_ACTIVITIES:
        shutil.copyfile(args.activities, LOCAL_SNAPSHOT)
        print(f"refreshed {LOCAL_SNAPSHOT.name}")

    write_csv(args.csv, header, new_rows + existing)
    print(f"wrote {args.csv.name}")


if __name__ == "__main__":
    main()
