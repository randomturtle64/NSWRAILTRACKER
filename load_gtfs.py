"""
Load TfNSW GTFS static data into gtfs.db
Streams large files in batches to stay within free tier memory limits.
Run once after deployment, then daily to refresh timetables.
"""
import sqlite3, zipfile, csv, requests, io, os
from dotenv import load_dotenv

load_dotenv()

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJjSW0zU1BZZjdsMVlmZkFvd1B1ZW02RFR5VkwwTlRCSnA4RzhiOFh5aWhVIiwiaWF0IjoxNzc4OTEyMjk1fQ.831dM8sgLXPsi6EF5tLYiAyc5NhzEoyEaWZDGr8S3ko"
HEADERS = {"Authorization": f"apikey {API_KEY}"}

GTFS_URLS = [
    "https://api.transport.nsw.gov.au/v1/gtfs/schedule/sydneytrains",
    "https://api.transport.nsw.gov.au/v1/gtfs/schedule/metro",
]

# Load these fully into memory (small files, safe)
SMALL_FILES = [
    "stops.txt",
    "trips.txt",
    "routes.txt",
    "calendar.txt",
    "calendar_dates.txt",
]

# Stream these in batches (large files)
LARGE_FILES = [
    "stop_times.txt",
]

BATCH_SIZE = 5000  # rows per insert batch — keeps peak RAM under ~50MB

def ensure_table(db, table, cols):
    """Create table if not exists, add missing columns if it does."""
    existing = db.execute(f'PRAGMA table_info("{table}")').fetchall()
    if existing:
        existing_cols = [r[1] for r in existing]
        for col in cols:
            if col not in existing_cols:
                db.execute(f'ALTER TABLE "{table}" ADD COLUMN "{col}" TEXT')
        return [c for c in cols if c in existing_cols + [c for c in cols if c not in existing_cols]]
    else:
        col_defs = ", ".join(f'"{c}" TEXT' for c in cols)
        db.execute(f'CREATE TABLE "{table}" ({col_defs})')
        return cols

def load_small(db, z, filename):
    """Load a small file fully into memory."""
    if filename not in z.namelist():
        print(f"  skipping {filename} (not in zip)")
        return
    with z.open(filename) as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
        rows = list(reader)
        if not rows:
            print(f"  {filename} empty")
            return
        cols = list(rows[0].keys())
        table = filename.replace(".txt", "")
        insert_cols = ensure_table(db, table, cols)
        ph = ",".join("?" * len(insert_cols))
        cl = ",".join(f'"{c}"' for c in insert_cols)
        db.executemany(
            f'INSERT OR IGNORE INTO "{table}" ({cl}) VALUES ({ph})',
            [[r.get(c, "") for c in insert_cols] for r in rows]
        )
        db.commit()
        print(f"  loaded {len(rows):,} rows from {filename}")

def load_large(db, z, filename):
    """Stream a large file in batches to minimise peak RAM."""
    if filename not in z.namelist():
        print(f"  skipping {filename} (not in zip)")
        return
    table = filename.replace(".txt", "")
    total = 0
    with z.open(filename) as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
        cols = None
        insert_cols = None
        ph = None
        cl = None
        batch = []
        for row in reader:
            # First row — set up table
            if cols is None:
                cols = list(row.keys())
                insert_cols = ensure_table(db, table, cols)
                ph = ",".join("?" * len(insert_cols))
                cl = ",".join(f'"{c}"' for c in insert_cols)
            batch.append([row.get(c, "") for c in insert_cols])
            if len(batch) >= BATCH_SIZE:
                db.executemany(
                    f'INSERT OR IGNORE INTO "{table}" ({cl}) VALUES ({ph})', batch
                )
                db.commit()
                total += len(batch)
                batch = []
                print(f"  {filename}: {total:,} rows...", end="\r")
        # Remaining rows
        if batch:
            db.executemany(
                f'INSERT OR IGNORE INTO "{table}" ({cl}) VALUES ({ph})', batch
            )
            db.commit()
            total += len(batch)
    print(f"  loaded {total:,} rows from {filename}        ")

def load_zip(zip_bytes, db):
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        for filename in SMALL_FILES:
            load_small(db, z, filename)
        for filename in LARGE_FILES:
            load_large(db, z, filename)

def main():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gtfs.db")
    db = sqlite3.connect(db_path)

    # Drop existing tables for fresh load
    for f in SMALL_FILES + LARGE_FILES:
        table = f.replace(".txt", "")
        db.execute(f'DROP TABLE IF EXISTS "{table}"')
    db.commit()

    for url in GTFS_URLS:
        mode = url.split("/")[-1]
        print(f"\nDownloading {mode}...")
        try:
            r = requests.get(url, headers=HEADERS, timeout=120)
            r.raise_for_status()
            print(f"  got {len(r.content)/1024/1024:.1f} MB")
            load_zip(r.content, db)
        except Exception as e:
            print(f"  ERROR: {e}")

    print("\nCreating indexes...")
    indexes = [
        ("trips",      "trip_id"),
        ("stop_times", "trip_id"),
        ("stops",      "stop_id"),
        ("routes",     "route_id"),
        ("calendar",   "service_id"),
    ]
    for table, col in indexes:
        try:
            db.execute(
                f'CREATE INDEX IF NOT EXISTS idx_{table}_{col} ON "{table}"("{col}")'
            )
        except Exception as e:
            print(f"  skipping index on {table}.{col}: {e}")

    db.commit()
    db.close()
    print("\nDone! gtfs.db is ready.")

if __name__ == "__main__":
    main()