#!/usr/bin/env python3
"""Merge a browser verification CSV into shared JSON; newest checked_at wins."""
import csv
import datetime as dt
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "verified-channels.json"
# New location avoids the existing data/verification-inbox path collision.
INBOX = ROOT / "data" / "verification_uploads"
MAX_BYTES = 2_000_000
MAX_ROWS = 5000


def parse_time(value):
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timestamp must include timezone")
        return parsed.astimezone(dt.timezone.utc)
    except (ValueError, TypeError):
        return None


def main():
    file_name = os.environ.get("CSV_FILE", "").strip()
    if (
        not file_name
        or pathlib.Path(file_name).name != file_name
        or not file_name.lower().endswith(".csv")
    ):
        raise ValueError("CSV_FILE must be a filename ending in .csv")

    file_path = INBOX / file_name
    if not file_path.is_file():
        raise ValueError(
            f"CSV file not found in data/verification_uploads: {file_name}"
        )
    if file_path.stat().st_size > MAX_BYTES:
        raise ValueError("CSV exceeds 2 MB")

    if DB.exists():
        doc = json.loads(DB.read_text(encoding="utf-8"))
    else:
        doc = {"schemaVersion": 1, "results": {}}

    if not isinstance(doc, dict) or not isinstance(doc.get("results"), dict):
        raise ValueError("Invalid existing JSON schema")

    results = doc["results"]
    updated = 0
    ignored = 0

    with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"channel_key", "status", "checked_at", "detail"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(
                "Invalid CSV header; required: channel_key,status,checked_at,detail"
            )

        for row_number, row in enumerate(reader, 1):
            if row_number > MAX_ROWS:
                raise ValueError("Too many rows")

            key = (row.get("channel_key") or "").strip()
            status = (row.get("status") or "").strip().lower()
            checked = parse_time(row.get("checked_at"))

            if (
                not key.startswith(("https://", "http://"))
                or len(key) > 2048
                or status not in ("ok", "fail", "blocked")
                or checked is None
            ):
                ignored += 1
                continue

            if checked > dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=10):
                ignored += 1
                continue

            old = results.get(key)
            old_checked = (
                parse_time(old.get("checkedAt")) if isinstance(old, dict) else None
            )
            if old_checked and checked <= old_checked:
                ignored += 1
                continue

            results[key] = {
                "status": status,
                "checkedAt": checked.isoformat(timespec="milliseconds").replace(
                    "+00:00", "Z"
                ),
                "detail": str(row.get("detail") or "")[:250],
            }
            updated += 1

    doc["schemaVersion"] = 1
    doc["source"] = "Admin browser verification CSV; not live uptime"
    doc["publishedAt"] = (
        dt.datetime.now(dt.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )

    DB.parent.mkdir(parents=True, exist_ok=True)
    DB.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Merge complete: updated={updated}, skipped={ignored}, "
        f"total={len(results)}"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Merge failed:", str(error), file=sys.stderr)
        sys.exit(1)
