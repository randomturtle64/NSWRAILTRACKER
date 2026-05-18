"""
Speed diagnostic - checks speed reporting across all feeds.
Run from nsw-tracker folder: python diagnose_speed.py
"""
import requests
from google.transit import gtfs_realtime_pb2
from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJjSW0zU1BZZjdsMVlmZkFvd1B1ZW02RFR5VkwwTlRCSnA4RzhiOFh5aWhVIiwiaWF0IjoxNzc4OTEyMjk1fQ.831dM8sgLXPsi6EF5tLYiAyc5NhzEoyEaWZDGr8S3ko"
if not API_KEY:
    API_KEY = input("Paste API key: ").strip()

HEADERS = {"Authorization": f"apikey {API_KEY}"}

FEEDS = {
    "sydneytrains_v2": "https://api.transport.nsw.gov.au/v2/gtfs/vehiclepos/sydneytrains",
    "metro_v2":        "https://api.transport.nsw.gov.au/v2/gtfs/vehiclepos/metro",
    "sydneytrains_v1": "https://api.transport.nsw.gov.au/v1/gtfs/vehiclepos/sydneytrains",
}

for feed_name, url in FEEDS.items():
    print(f"\n{'='*60}")
    print(f"FEED: {feed_name}")
    print(f"URL:  {url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        print(f"Status: {r.status_code}, bytes: {len(r.content)}")
        if r.status_code != 200:
            print(f"Body: {r.text[:100]}")
            continue

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(r.content)
        print(f"Entities: {len(feed.entity)}")

        total = 0
        with_speed = 0
        nonzero_speed = 0
        sample_with = []
        sample_without = []

        for entity in feed.entity:
            if not entity.HasField("vehicle"): continue
            v = entity.vehicle
            total += 1
            spd = v.position.speed
            if spd is not None:
                with_speed += 1
                if spd > 0:
                    nonzero_speed += 1
                    if len(sample_with) < 5:
                        sample_with.append({
                            "trip_id": v.trip.trip_id,
                            "speed_ms": spd,
                            "speed_kmh": round(spd * 3.6, 1),
                            "label": v.vehicle.label,
                            "plate": v.vehicle.license_plate,
                            "hex": v.SerializeToString().hex()[:80],
                        })
                else:
                    if len(sample_without) < 3:
                        sample_without.append({
                            "trip_id": v.trip.trip_id,
                            "speed_ms": spd,
                            "label": v.vehicle.label,
                            "hex": v.SerializeToString().hex()[:80],
                        })

        print(f"Total vehicles:        {total}")
        print(f"With speed field:      {with_speed}")
        print(f"Non-zero speed:        {nonzero_speed}")
        print(f"Zero/missing speed:    {total - nonzero_speed}")
        print()

        if sample_with:
            print("SAMPLES WITH SPEED:")
            for s in sample_with:
                print(f"  trip_id: {s['trip_id']!r}")
                print(f"  speed:   {s['speed_ms']} m/s = {s['speed_kmh']} km/h")
                print(f"  label:   {s['label']!r}")
                print(f"  plate:   {s['plate']!r}")
                print(f"  hex:     {s['hex']}")
                print()

        if sample_without:
            print("SAMPLES WITHOUT/ZERO SPEED:")
            for s in sample_without:
                print(f"  trip_id: {s['trip_id']!r}")
                print(f"  speed:   {s['speed_ms']}")
                print(f"  label:   {s['label']!r}")
                print(f"  hex:     {s['hex']}")
                print()

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback; traceback.print_exc()
