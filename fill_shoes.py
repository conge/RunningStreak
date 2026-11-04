"""Fill the Shoes column of a runningRecords CSV.

Precedence, lowest to highest: --default, --rain, then --set ranges in the
order they are given. Only blank Shoes cells are touched unless a --set range
explicitly covers a date.

Examples:
    python3 fill_shoes.py --default Barefoot --rain SL2 \\
        --set 20260611:20260731 SL2 \\
        --set 20260807:20260808 "Boston 12" --dry-run
"""
import argparse
import csv
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent


def parse_range(text: str):
    start, _, end = text.partition(":")
    return start, (end or start)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path,
                    default=REPO / f"runningRecords{datetime.now().year}.csv")
    ap.add_argument("--default", default="", help="shoe for every remaining blank cell")
    ap.add_argument("--rain", default="", help="shoe for blank cells on rainy days")
    ap.add_argument("--set", nargs=2, action="append", default=[],
                    metavar=("START:END", "SHOE"), help="explicit date range, wins")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(args.csv, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())

    choice = {}
    blanks = [r for r in rows if not r["Shoes"].strip()]
    for r in blanks:
        if args.default:
            choice[r["date"]] = args.default
    for r in blanks:
        if args.rain and r["weather"].strip().lower().startswith("rain"):
            choice[r["date"]] = args.rain
    for span, shoe in args.set:
        start, end = parse_range(span)
        for r in rows:
            if start <= r["date"] <= end:
                choice[r["date"]] = shoe

    for r in rows:
        if r["date"] in choice:
            r["Shoes"] = choice[r["date"]]

    filled = [r for r in rows if r["date"] in choice]
    print(f"{len(blanks)} blank cell(s); {len(filled)} filled now")

    remaining = [r for r in rows if not r["Shoes"].strip()]
    if remaining:
        print(f"still blank: {len(remaining)}")

    summary = {}
    for r in filled:
        summary.setdefault(r["date"][:6], {}).setdefault(r["Shoes"], 0)
        summary[r["date"][:6]][r["Shoes"]] += 1
    for month in sorted(summary):
        cells = ", ".join(f"{k} x{v}" for k, v in sorted(summary[month].items()))
        print(f"  {month[:4]}-{month[4:]}  {cells}")

    if args.dry_run:
        print("dry run, nothing written")
        return

    with open(args.csv, "rb") as f:
        has_bom = f.read(3) == b"\xef\xbb\xbf"
    with open(args.csv, "w", newline="", encoding="utf-8-sig" if has_bom else "utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {args.csv.name}")


if __name__ == "__main__":
    main()
