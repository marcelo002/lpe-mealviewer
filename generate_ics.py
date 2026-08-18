#!/usr/bin/env python3
"""
Generate an Apple Calendar (.ics) subscription feed for Laureate Park
Elementary's lunch menu, sourced live from MealViewer's public JSON API.

Runs with the Python standard library only (no pip install needed), so it
works unmodified inside a GitHub Actions runner.

MealViewer API discovered via reverse-engineering (confirmed working,
no API key required):

    https://api.mealviewer.com/api/v4/school/{schoolKey}/{start}/{end}/

    - schoolKey: the slug from the school's MealViewer URL
      (https://schools.mealviewer.com/school/<schoolKey>)
    - start/end: dates formatted MM-DD-YYYY (inclusive range)

Credit: endpoint structure confirmed against the MMM-MealViewer
MagicMirror module (https://github.com/KevinGlinski/MMM-MealViewer).
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration - edit these if your needs change
# ---------------------------------------------------------------------------

SCHOOL_KEY = "LaureateParkElementary"

# Which meal block to publish. MealViewer usually exposes "Breakfast" and
# "Lunch" as block names for this school.
MEAL_BLOCK_NAME = "Lunch"

# How far back / forward to ask MealViewer for. MealViewer typically only
# publishes menus a few weeks to ~1 month ahead, so asking for a wide
# window is harmless - days with no published menu are simply skipped.
DAYS_BEHIND = 3
DAYS_AHEAD = 75

# Item types to include in the event description, in display order.
# "Entrees" also drives the event title.
ITEM_TYPE_ORDER = ["Entrees", "Breads/Grains", "Vegetables", "Fruits", "Milk"]

OUTPUT_PATH = Path(__file__).parent / "docs" / "lpe_lunch_menu.ics"

CALENDAR_NAME = "LPE Lunch Menu"
CALENDAR_TIMEZONE = "America/New_York"

API_URL_TEMPLATE = (
    "https://api.mealviewer.com/api/v4/school/{school_key}/{start}/{end}/"
)


# ---------------------------------------------------------------------------
# MealViewer fetch
# ---------------------------------------------------------------------------

def fetch_menu(school_key: str, start: datetime, end: datetime) -> dict:
    url = API_URL_TEMPLATE.format(
        school_key=school_key,
        start=start.strftime("%m-%d-%Y"),
        end=end.strftime("%m-%d-%Y"),
    )
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def extract_days(payload: dict) -> list[dict]:
    """Return a list of {date, items_by_type} for each day that has a
    published menu for MEAL_BLOCK_NAME."""
    days = []
    for day in payload.get("menuSchedules", []):
        date_str = day["dateInformation"]["dateFull"][:10]  # YYYY-MM-DD
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()

        for block in day.get("menuBlocks", []):
            if block.get("blockName") != MEAL_BLOCK_NAME:
                continue
            if block.get("blackedOut"):
                continue

            items_by_type: dict[str, list[str]] = {}
            for line in block.get("cafeteriaLineList", {}).get("data", []):
                for item in line.get("foodItemList", {}).get("data", []):
                    item_type = item.get("item_Type") or "Other"
                    name = (item.get("item_Name") or "").strip()
                    if not name:
                        continue
                    items_by_type.setdefault(item_type, [])
                    if name not in items_by_type[item_type]:
                        items_by_type[item_type].append(name)

            if items_by_type:
                days.append({"date": date_obj, "items_by_type": items_by_type})

    days.sort(key=lambda d: d["date"])
    return days


# ---------------------------------------------------------------------------
# ICS generation
# ---------------------------------------------------------------------------

def escape_ics_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def fold_line(line: str) -> str:
    """RFC 5545 line folding at 75 octets, continuation lines start with a space."""
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line
    parts = []
    while len(encoded) > 75:
        # find a safe split point that doesn't break a multi-byte char
        cut = 75
        while (encoded[cut] & 0xC0) == 0x80:
            cut -= 1
        parts.append(encoded[:cut].decode("utf-8"))
        encoded = encoded[cut:]
    parts.append(encoded.decode("utf-8"))
    return "\r\n ".join(parts)


def build_event_title(items_by_type: dict[str, list[str]]) -> str:
    entrees = items_by_type.get("Entrees", [])
    if not entrees:
        return "Lunch Menu"
    if len(entrees) <= 2:
        return " / ".join(entrees)
    return f"{entrees[0]} / {entrees[1]} +{len(entrees) - 2} more"


def build_event_description(items_by_type: dict[str, list[str]]) -> str:
    lines = []
    seen_types = set()

    ordered_types = ITEM_TYPE_ORDER + sorted(
        t for t in items_by_type if t not in ITEM_TYPE_ORDER
    )
    for item_type in ordered_types:
        if item_type in seen_types:
            continue
        seen_types.add(item_type)
        names = items_by_type.get(item_type)
        if not names:
            continue
        lines.append(f"{item_type}: {', '.join(names)}")

    return "\n".join(lines)


def build_ics(days: list[dict]) -> str:
    now_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//LPE Mealviewer//lunch-calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape_ics_text(CALENDAR_NAME)}",
        f"X-WR-TIMEZONE:{CALENDAR_TIMEZONE}",
        # Hint to clients how often to refresh; not all clients honor this.
        "X-PUBLISHED-TTL:PT12H",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
    ]

    for day in days:
        date_obj = day["date"]
        dtstart = date_obj.strftime("%Y%m%d")
        dtend = (date_obj + timedelta(days=1)).strftime("%Y%m%d")
        uid = f"lpe-lunch-{dtstart}@lpe-mealviewer.local"

        summary = build_event_title(day["items_by_type"])
        description = build_event_description(day["items_by_type"])

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{now_utc}",
                f"DTSTART;VALUE=DATE:{dtstart}",
                f"DTEND;VALUE=DATE:{dtend}",
                f"SUMMARY:{escape_ics_text(summary)}",
                f"DESCRIPTION:{escape_ics_text(description)}",
                "TRANSP:TRANSPARENT",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")

    folded = [fold_line(line) for line in lines]
    return "\r\n".join(folded) + "\r\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    today = datetime.now().date()
    start = datetime.combine(today - timedelta(days=DAYS_BEHIND), datetime.min.time())
    end = datetime.combine(today + timedelta(days=DAYS_AHEAD), datetime.min.time())

    try:
        payload = fetch_menu(SCHOOL_KEY, start, end)
    except urllib.error.URLError as exc:
        raise SystemExit(f"Failed to fetch MealViewer data: {exc}")

    days = extract_days(payload)
    if not days:
        raise SystemExit(
            "No menu days found in the response - MealViewer's data shape "
            "may have changed, or nothing is published for this window."
        )

    ics_text = build_ics(days)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(ics_text, encoding="utf-8")

    print(f"Wrote {len(days)} lunch menu day(s) to {OUTPUT_PATH}")
    print(f"Date range covered: {days[0]['date']} to {days[-1]['date']}")


if __name__ == "__main__":
    main()
