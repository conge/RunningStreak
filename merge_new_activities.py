"""Merge new activities from activities_new.json into runningRecords2026.csv.

- Only appends records newer than the latest date already in the CSV.
- streak# continues from the most recent streak number, one number per day
  (multiple runs on the same day share the same streak#, matching existing style).
- Output is ordered newest-first, inserted right after the header.
"""
import json
import csv
from datetime import datetime

INPUT_JSON = "activities_new.json"
CSV_FILE = "runningRecords2026.csv"

MILES_PER_METER = 0.000621371


def parse_moving_time(s: str) -> str:
    """Convert 'H:MM:SS[.frac]' to total minutes."""
    try:
        s = s.split(".")[0]
        parts = [int(p) for p in s.split(":")]
        while len(parts) < 3:
            parts.insert(0, 0)
        h, m, sec = parts
        total = h * 60 + m + sec / 60.0
        return str(int(total)) if total == int(total) else f"{total:.2f}"
    except (ValueError, IndexError):
        return ""


def main():
    with open(INPUT_JSON, encoding="utf-8") as f:
        activities = json.load(f)

    # Find latest date already in CSV and current max streak#
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header, existing = rows[0], rows[1:]
    latest_date = max(r[1] for r in existing if r[1].isdigit())
    max_streak = max(int(r[0]) for r in existing if r[0].isdigit())
    print(f"CSV 已有记录至 {latest_date}，最大 streak# = {max_streak}")

    # New runs strictly after latest_date
    new_runs = []
    for a in activities:
        d = a["start_date_local"][:10].replace("-", "")
        if d > latest_date:
            new_runs.append((d, a))
    new_runs.sort(key=lambda x: x[0], reverse=True)  # newest first

    # Assign streak#: one per day, counting down from max_streak + #days
    days = sorted({d for d, _ in new_runs}, reverse=True)
    streak_of_day = {d: max_streak + len(days) - i for i, d in enumerate(days)}

    out_rows = []
    for d, a in new_runs:
        dt = datetime.strptime(a["start_date_local"], "%Y-%m-%d %H:%M:%S")
        out_rows.append([
            streak_of_day[d],
            d,
            dt.strftime("%I:%M %p").lstrip("0"),
            parse_moving_time(str(a.get("moving_time", ""))),
            f"{a.get('distance', 0) * MILES_PER_METER:.2f}",
            "", "", "",
        ])

    print(f"新增 {len(out_rows)} 条记录（{len(days)} 天）:")
    for r in out_rows:
        print(",".join(map(str, r)))

    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(out_rows + existing)
    print(f"Done! 已写回 {CSV_FILE}")


if __name__ == "__main__":
    main()
