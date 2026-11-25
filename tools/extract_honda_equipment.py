"""Review aid: normalize named equipment rows from a saved Honda News matrix."""
import argparse
import json
from pathlib import Path
import re

from lxml import html

# Prefixes identify the factual rows even when the site appends footnote numbers.
# The expected title and complete ordered trim list are checked before extraction.
ROWS = {
    "Backup camera": "Multi-Angle Rearview Camera",
    "Blind-spot monitoring": "Blind Spot Information System",
    "Rear cross-traffic alert": "Rear Cross Traffic Monitor",
    "Adaptive cruise control": "Adaptive Cruise Control",
    "Automatic emergency braking": "Collision Mitigation Braking System",
    "Lane-keeping assistance": "Lane Keeping Assist System",
    "Apple CarPlay": "Apple CarPlay",
    "Android Auto": "Android Auto",
    "Wireless Apple CarPlay": "Wireless Apple CarPlay",
    "Wireless Android Auto": "Wireless Android Auto",
    "Heated front seats": "Heated Front Seats",
    "Ventilated front seats": "Ventilated Front Seats",
    "Heated steering wheel": "Heated Steering Wheel",
    "Power driver seat": "Driver's Seat with",
    "Parking sensors": "Parking Sensors",
    "Spare tire": "Compact Spare Tire",
    "Push-button start": "Push Button Start",
    "Remote start": "Remote Engine Start",
    "Sunroof": "One-Touch Power Moonroof",
    "Leather seating": "Leather-Trimmed Seats",
    "Dual-zone climate control": "Dual-Zone Automatic Climate",
    "Wireless phone charging": "Wireless Phone Charger",
    "Premium audio": "Bose Premium Sound System",
}
ROW_ALIASES = {
    "Rear cross-traffic alert": "Cross Traffic Monitor",
    "Heated front seats": "Driver & Passenger Heated Seat",
    "Remote start": "Key Fob Activated Remote Engine Start",
    "Dual-zone climate control": "Dual Zone Climate Control",
}
MARKERS = {"•": "standard", "-": "unavailable"}


def extract(path, year, model, trims):
    document = html.fromstring(path.read_bytes(), parser=html.HTMLParser(encoding="utf-8"))
    expected_title = f"{year} Honda {model} Specifications & Features"
    title = document.xpath("normalize-space(//title)")
    if title not in {expected_title, expected_title.replace(" & ", " and ")}:
        raise ValueError("Document title does not match requested model year and model")
    header = f"{year} HONDA {model.upper()} SPECIFICATIONS & FEATURES"
    cells = [[cell.xpath("normalize-space(.)") for cell in row.xpath("./td|./th")]
             for row in document.xpath("//tr")]
    headers = [row[1:] for row in cells if row and row[0] == header]
    if headers != [trims]:
        raise ValueError(f"Unexpected trim columns: {headers}")
    rows = []
    for field, prefix in ROWS.items():
        prefixes = (prefix, ROW_ALIASES[field]) if field in ROW_ALIASES else (prefix,)
        matches = [row for row in cells if row and row[0].startswith(prefixes)]
        if field == "Power driver seat":
            matches = [row for row in matches if "power adjustment" in row[0].lower()]
        if not matches:
            continue
        if len(matches) != 1 or len(matches[0]) != len(trims) + 1:
            raise ValueError(f"Unexpected row layout: {field}")
        values = []
        for cell in matches[0][1:]:
            value = MARKERS.get(cell)
            if field == "Spare tire" and re.fullmatch(r"T\d+\s*/\s*\d+[DR]\d+\s+\d+M", cell):
                value = "standard"
            if value is None:
                raise ValueError(f"Unreviewed marker for {field}: {cell!r}")
            values.append(value)
        rows.append({"field": field, "cells": values,
                     "locator": f"Specifications & Features / {field}",
                     "evidence": "The manufacturer's comparison marks availability separately in each named trim column."})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    parser.add_argument("year", type=int)
    parser.add_argument("model")
    parser.add_argument("trims", nargs="+")
    args = parser.parse_args()
    print(json.dumps(extract(args.html, args.year, args.model, args.trims), indent=2))


if __name__ == "__main__":
    main()
