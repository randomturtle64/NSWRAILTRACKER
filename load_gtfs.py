"""
Run this once to load static GTFS data into gtfs.db
Run again each morning to refresh timetables.
"""
import sqlite3
import zipfile
import csv
import requests
import io
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJjSW0zU1BZZjdsMVlmZkFvd1B1ZW02RFR5VkwwTlRCSnA4RzhiOFh5aWhVIiwiaWF0IjoxNzc4OTEyMjk1fQ.831dM8sgLXPsi6EF5tLYiAyc5NhzEoyEaWZDGr8S3ko"
HEADERS = {"Authorization": f"apikey {API_KEY}"}

GTFS_URLS = [
    "https://api.transport.nsw.gov.au/v1/gtfs/schedule/sydneytrains",
    "https://api.transport.nsw.gov.au/v1/gtfs/schedule/metro",
]

FILES_TO_LOAD = [
    "stops.txt",
    "trips.txt",
    "routes.txt",
    "stop_times.txt",
    "calendar.txt",
    "calendar_dates.txt",
]

def load_zip_to_db(zip_bytes, db, mode_tag):
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        available = z.namelist()
        for filename in FILES_TO_LOAD:
            if filename not in available:
                print(f"  skipping {filename} (not in zip)")
                continue

            with z.open(filename) as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
                rows = list(reader)
                if not rows:
                    print(f"  {filename} empty")
                    continue

                file_cols = list(rows[0].keys())
                table = filename.replace(".txt", "")

                # Get existing table columns if table already exists
                existing = db.execute(
                    f"PRAGMA table_info(\"{table}\")"
                ).fetchall()

                if existing:
                    # Table exists — find common columns to insert into
                    existing_cols = [row[1] for row in existing]
                    # Add any new columns from this feed
                    for col in file_cols:
                        if col not in existing_cols:
                            db.execute(f'ALTER TABLE "{table}" ADD COLUMN "{col}" TEXT')
                            existing_cols.append(col)
                    insert_cols = [c for c in file_cols if c in existing_cols]
                else:
                    # Create fresh table with this feed's columns
                    col_defs = ", ".join(f'"{c}" TEXT' for c in file_cols)
                    db.execute(f'CREATE TABLE "{table}" ({col_defs})')
                    insert_cols = file_cols

                # Insert only the columns this file has
                placeholders = ",".join("?" * len(insert_cols))
                col_list = ",".join(f'"{c}"' for c in insert_cols)
                db.executemany(
                    f'INSERT OR IGNORE INTO "{table}" ({col_list}) VALUES ({placeholders})',
                    [[r.get(c, "") for c in insert_cols] for r in rows]
                )
                print(f"  loaded {len(rows):,} rows from {filename}")

def main():
    db_path = os.path.join(os.path.dirname(__file__), "gtfs.db")
    db = sqlite3.connect(db_path)

    # Drop existing tables for fresh load
    for f in FILES_TO_LOAD:
        table = f.replace(".txt", "")
        db.execute(f'DROP TABLE IF EXISTS "{table}"')
    db.commit()

    for url in GTFS_URLS:
        mode = url.split("/")[-1]
        print(f"\nDownloading {mode}...")
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            r.raise_for_status()
            print(f"  got {len(r.content)/1024/1024:.1f} MB")
            load_zip_to_db(r.content, db, mode)
        except Exception as e:
            print(f"  ERROR: {e}")

    # Create indexes for fast lookups
    print("\nCreating indexes...")
    indexes = [
        ('trips',          'trip_id'),
        ('stop_times',     'trip_id'),
        ('stops',          'stop_id'),
        ('routes',         'route_id'),
        ('calendar',       'service_id'),
    ]
    for table, col in indexes:
        try:
            db.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_{col} ON "{table}"("{col}")')
        except Exception as e:
            print(f"  skipping index on {table}.{col}: {e}")

    db.commit()
    db.close()
    print("\nDone! gtfs.db is ready.")

if __name__ == "__main__":
    main()
