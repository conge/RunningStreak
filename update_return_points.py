"""Convert one camera-roll photo per run day into ReturnPoints/YYYYMMDD.webp.

For each run day in the CSV that has no ReturnPoints image yet, the photo taken
closest to the middle of a run is used (the turnaround point), restricted to a
window around the day's run(s). Images are rotated per EXIF, scaled to a max
side of 1080 px and saved as WebP - the format already used in ReturnPoints/.

Usage:
    python3 update_return_points.py --dry-run    # report only
    python3 update_return_points.py              # convert what it can
"""
import argparse
import csv
import re
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageOps

REPO = Path(__file__).resolve().parent
DEFAULT_PHOTOS = Path("/Users/qli/Library/CloudStorage/OneDrive-Personal/Pictures/Camera Roll")
DEST = REPO / "ReturnPoints"

MAX_SIDE = 1080
QUALITY = 80
PRE_MINUTES = 20   # allow shots taken just before starting the watch
POST_MINUTES = 90  # and a while after finishing

PHOTO_RE = re.compile(r"^IMG(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})\.jpg$", re.I)


def scan_photos(folder: Path) -> dict:
    """{"YYYY-MM-DD": [(timestamp, path), ...]}"""
    photos = {}
    for p in folder.iterdir():
        m = PHOTO_RE.match(p.name)
        if not m:
            continue
        y, mo, d, h, mi, s = map(int, m.groups())
        photos.setdefault(f"{y:04d}-{mo:02d}-{d:02d}", []).append(
            (datetime(y, mo, d, h, mi, s), p))
    return photos


def run_windows(rows) -> dict:
    """{"YYYY-MM-DD": [(start, end), ...]} from the CSV rows."""
    runs = {}
    for r in rows:
        day = r["date"]
        key = f"{day[:4]}-{day[4:6]}-{day[6:]}"
        start = datetime.strptime(f"{key} {r['startTime']}", "%Y-%m-%d %I:%M %p")
        minutes = float(r["runningTime(min)"] or 0)
        runs.setdefault(key, []).append((start, start + timedelta(minutes=minutes)))
    return runs


def pick_photo(candidates, windows):
    """Photo closest to the middle of any run that day, or None."""
    mids = [s + (e - s) / 2 for s, e in windows]
    lo = min(s for s, _ in windows) - timedelta(minutes=PRE_MINUTES)
    hi = max(e for _, e in windows) + timedelta(minutes=POST_MINUTES)
    inside = [(t, p) for t, p in candidates if lo <= t <= hi]
    if not inside:
        return None
    return min(inside, key=lambda c: min(abs((c[0] - m).total_seconds()) for m in mids))


def to_webp(src: Path, dest: Path):
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
        im.save(dest, "WEBP", quality=QUALITY, method=6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path,
                    default=REPO / f"runningRecords{datetime.now().year}.csv")
    ap.add_argument("--photos", type=Path, default=DEFAULT_PHOTOS)
    ap.add_argument("--since", default="",
                    help="only fill days on/after this YYYYMMDD date")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(args.csv, newline="", encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f) if r.get("date", "").isdigit()]

    photos = scan_photos(args.photos)
    runs = run_windows(rows)

    converted, ambiguous, missing = [], [], []
    for day in sorted(runs, reverse=True):
        if args.since and day.replace("-", "") < args.since:
            continue
        dest = DEST / f"{day.replace('-', '')}.webp"
        if dest.exists():
            continue
        picked = pick_photo(photos.get(day, []), runs[day])
        if picked is None:
            missing.append((day, len(photos.get(day, []))))
            continue
        stamp, src = picked
        converted.append((day, src.name, stamp.strftime("%H:%M")))
        if not args.dry_run:
            to_webp(src, dest)

    print(f"{'would convert' if args.dry_run else 'converted'} {len(converted)} images")
    for day, name, hhmm in converted[:5]:
        print(f"  {day} <- {name} ({hhmm})")
    if len(converted) > 5:
        print(f"  ... and {len(converted) - 5} more")

    if missing:
        print(f"\nno usable photo for {len(missing)} day(s):")
        for day, n in missing:
            print(f"  {day} ({n} photo(s) on disk, none near the run)")


if __name__ == "__main__":
    main()
