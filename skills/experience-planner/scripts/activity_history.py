#!/usr/bin/env python3
"""Manage a lightweight local history for the experience-planner skill."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_HISTORY_FILE = Path(".experience-planner/history.json")
VALID_STATUSES = {"planned", "completed", "skipped"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_history() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": utc_now(),
        "activities": [],
    }


def resolve_history_file(raw_path: str | None) -> Path:
    return Path(raw_path).expanduser().resolve() if raw_path else DEFAULT_HISTORY_FILE.resolve()


def ensure_history_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps(default_history(), indent=2) + "\n")


def load_history(path: Path) -> dict[str, Any]:
    ensure_history_file(path)
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("History file must contain a JSON object.")
    if "activities" not in data or not isinstance(data["activities"], list):
        raise ValueError("History file must contain an 'activities' list.")
    data.setdefault("version", 1)
    data.setdefault("updated_at", utc_now())
    return data


def write_history(path: Path, data: dict[str, Any]) -> None:
    data["updated_at"] = utc_now()
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n")


def sorted_activities(activities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(activity: dict[str, Any]) -> tuple[str, str]:
        return (
            str(activity.get("date") or ""),
            str(activity.get("created_at") or ""),
        )

    return sorted(activities, key=sort_key, reverse=True)


def validate_rating(raw_rating: int | None) -> int | None:
    if raw_rating is None:
        return None
    if 1 <= raw_rating <= 5:
        return raw_rating
    raise ValueError("Rating must be between 1 and 5.")


def most_common(values: list[str], limit: int = 5) -> list[dict[str, Any]]:
    counts = Counter(value for value in values if value)
    return [{"name": name, "count": count} for name, count in counts.most_common(limit)]


def add_history_file_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--history-file",
        help="Override the history file path. Defaults to .experience-planner/history.json",
    )


def cmd_ensure(args: argparse.Namespace) -> int:
    history_file = resolve_history_file(args.history_file)
    ensure_history_file(history_file)
    print(history_file)
    return 0


def cmd_recent(args: argparse.Namespace) -> int:
    history_file = resolve_history_file(args.history_file)
    data = load_history(history_file)
    activities = sorted_activities(data["activities"])[: args.limit]
    print(json.dumps(activities, indent=2))
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    history_file = resolve_history_file(args.history_file)
    data = load_history(history_file)
    activities = sorted_activities(data["activities"])[: args.limit]

    tags: list[str] = []
    for activity in activities:
        tags.extend(tag for tag in activity.get("tags", []) if isinstance(tag, str))

    summary = {
        "history_file": str(history_file),
        "total_entries": len(data["activities"]),
        "window_entries": len(activities),
        "recent_titles": [activity.get("title") for activity in activities if activity.get("title")],
        "categories": most_common(
            [str(activity.get("category") or "") for activity in activities]
        ),
        "locations": most_common(
            [str(activity.get("location") or "") for activity in activities]
        ),
        "companions": most_common(
            [str(activity.get("companions") or "") for activity in activities]
        ),
        "tags": most_common(tags),
    }
    print(json.dumps(summary, indent=2))
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    history_file = resolve_history_file(args.history_file)
    data = load_history(history_file)

    if args.status not in VALID_STATUSES:
        raise ValueError(f"Status must be one of: {', '.join(sorted(VALID_STATUSES))}")

    entry = {
        "id": uuid.uuid4().hex[:8],
        "title": args.title,
        "date": args.date,
        "status": args.status,
        "category": args.category,
        "location": args.location,
        "companions": args.companions,
        "cost": args.cost,
        "travel_minutes": args.travel_minutes,
        "rating": validate_rating(args.rating),
        "tags": args.tag or [],
        "notes": args.notes,
        "source": args.source,
        "created_at": utc_now(),
    }

    data["activities"].append(entry)
    write_history(history_file, data)
    print(json.dumps(entry, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage a lightweight local history for experience planning."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ensure_parser = subparsers.add_parser("ensure", help="Create the history file if needed.")
    add_history_file_argument(ensure_parser)
    ensure_parser.set_defaults(func=cmd_ensure)

    recent_parser = subparsers.add_parser("recent", help="Show recent activity entries.")
    add_history_file_argument(recent_parser)
    recent_parser.add_argument("--limit", type=int, default=10, help="Number of entries to print.")
    recent_parser.set_defaults(func=cmd_recent)

    summary_parser = subparsers.add_parser("summary", help="Show a compact recent-history summary.")
    add_history_file_argument(summary_parser)
    summary_parser.add_argument(
        "--limit", type=int, default=20, help="Number of recent entries to summarize."
    )
    summary_parser.set_defaults(func=cmd_summary)

    record_parser = subparsers.add_parser("record", help="Record a planned or completed activity.")
    add_history_file_argument(record_parser)
    record_parser.add_argument("--title", required=True, help="Human-readable activity title.")
    record_parser.add_argument("--date", required=True, help="Activity date in YYYY-MM-DD format.")
    record_parser.add_argument(
        "--status",
        default="completed",
        choices=sorted(VALID_STATUSES),
        help="Activity status.",
    )
    record_parser.add_argument("--category", help="Broad activity type, for example fitness or food.")
    record_parser.add_argument("--location", help="Venue or area.")
    record_parser.add_argument("--companions", help="Social context, for example solo or friends.")
    record_parser.add_argument("--cost", type=float, help="Approximate spend.")
    record_parser.add_argument("--travel-minutes", type=int, help="One-way travel time in minutes.")
    record_parser.add_argument("--rating", type=int, help="Optional rating from 1 to 5.")
    record_parser.add_argument("--tag", action="append", help="Repeatable tag value.")
    record_parser.add_argument("--notes", help="Short qualitative feedback.")
    record_parser.add_argument("--source", help="Optional venue or booking URL.")
    record_parser.set_defaults(func=cmd_record)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
