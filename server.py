"""
NSW Rail Tracker - server.py
Run: python server.py
Visit: http://localhost:5000
"""
import threading, time, requests, sqlite3, os
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from google.transit import gtfs_realtime_pb2
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__, static_folder=".")
CORS(app)

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJjSW0zU1BZZjdsMVlmZkFvd1B1ZW02RFR5VkwwTlRCSnA4RzhiOFh5aWhVIiwiaWF0IjoxNzc4OTEyMjk1fQ.831dM8sgLXPsi6EF5tLYiAyc5NhzEoyEaWZDGr8S3ko"
HEADERS = {"Authorization": f"apikey {API_KEY}"}

FEEDS = {
    "sydneytrains": {
        "vehicles": "https://api.transport.nsw.gov.au/v2/gtfs/vehiclepos/sydneytrains",
        "trips":    "https://api.transport.nsw.gov.au/v2/gtfs/realtime/sydneytrains",
    },
    "metro": {
        "vehicles": "https://api.transport.nsw.gov.au/v2/gtfs/vehiclepos/metro",
        "trips":    "https://api.transport.nsw.gov.au/v2/gtfs/realtime/metro",
    },
}

ROUTE_COLORS = {
    "T1":"#F99D1C","T2":"#0098CD","T3":"#F37021","T4":"#005AA3",
    "T5":"#C4258F","T6":"#7D4199","T7":"#6F818E","T8":"#00954C","T9":"#D11F2F",
    "CCN":"#E4022D","BML":"#E4022D","SCL":"#E4022D","SHL":"#E4022D","HNL":"#E4022D",
    "M1":"#009B77","M2":"#009B77",
}
METRO_ROUTE_MAP = [
    ("SMNW","M1","Metro North West"),
    ("SMSWC","M1","Metro City & South West"),
    ("SMWP","M1","Metro West"),
    ("SMBS","M1","Metro Bankstown"),
    ("SM","M1","Sydney Metro"),
]

# ------------------------------------------------------------------
# ACCURATE FLEET CONSIST MAPS
# Sources: Wikipedia, NSW Trains Wiki/Fandom, Transport NSW docs
# Car types: DT=Driving Trailer, DM=Driving Motor, M=Motor, T=Trailer
#            XP=XPT Power Car, XF=Economy, XL=First, XBR=Buffet/First,
#            XAM=Sleeper, DP=Diesel Power, DS=Diesel Saloon
# ------------------------------------------------------------------
FLEET = {
    "A": {
        "name": "Waratah A Set", "operator": "Sydney Trains",
        "double_deck": True, "air_conditioned": True,
        "electric": True, "diesel": False,
        "introduced": 2011, "max_speed": 130,
        "notes": "78 sets built. Indivisible 8-car set. Runs solo or coupled as 16-car.",
        "colors": {"body":"#005AA3","cab":"#003070"},
        "formations": {
            8: [
                {"n":1,"type":"DT","label":"DT","cab":True,"panto":True,"motor":False,"accessible":True},
                {"n":2,"type":"M", "label":"M", "cab":False,"panto":False,"motor":True,"accessible":False},
                {"n":3,"type":"M", "label":"M", "cab":False,"panto":False,"motor":True,"accessible":False},
                {"n":4,"type":"T", "label":"T", "cab":False,"panto":False,"motor":False,"accessible":True,"toilet":True},
                {"n":5,"type":"T", "label":"T", "cab":False,"panto":False,"motor":False,"accessible":False},
                {"n":6,"type":"M", "label":"M", "cab":False,"panto":False,"motor":True,"accessible":False},
                {"n":7,"type":"M", "label":"M", "cab":False,"panto":False,"motor":True,"accessible":False},
                {"n":8,"type":"DT","label":"DT","cab":True,"panto":True,"motor":False,"accessible":True},
            ],
            16: "couple:8",
        },
    },
    "B": {
        "name": "Waratah B Set", "operator": "Sydney Trains",
        "double_deck": True, "air_conditioned": True,
        "electric": True, "diesel": False,
        "introduced": 2018, "max_speed": 130,
        "notes": "41 sets. Identical formation to A set. LCD screens, updated livery. B23+ has rail fault monitoring.",
        "colors": {"body":"#0070C0","cab":"#003a6b"},
        "formations": {
            8: [
                {"n":1,"type":"DT","label":"DT","cab":True,"panto":True,"motor":False,"accessible":True},
                {"n":2,"type":"M", "label":"M", "cab":False,"panto":False,"motor":True,"accessible":False},
                {"n":3,"type":"M", "label":"M", "cab":False,"panto":False,"motor":True,"accessible":False},
                {"n":4,"type":"T", "label":"T", "cab":False,"panto":False,"motor":False,"accessible":True,"toilet":True},
                {"n":5,"type":"T", "label":"T", "cab":False,"panto":False,"motor":False,"accessible":False},
                {"n":6,"type":"M", "label":"M", "cab":False,"panto":False,"motor":True,"accessible":False},
                {"n":7,"type":"M", "label":"M", "cab":False,"panto":False,"motor":True,"accessible":False},
                {"n":8,"type":"DT","label":"DT","cab":True,"panto":True,"motor":False,"accessible":True},
            ],
            16: "couple:8",
        },
    },
    "D": {
        "name": "Mariyung (D Set)", "operator": "Sydney Trains / NSW TrainLink",
        "double_deck": True, "air_conditioned": True,
        "electric": True, "diesel": False,
        "introduced": 2024, "max_speed": 160,
        "notes": "New Intercity Fleet. 610 carriages by Hyundai Rotem. Replaces V sets. Runs 4/6/8/10 car. Charging ports, luggage space, accessible toilets.",
        "colors": {"body":"#1A3A5C","cab":"#0d2540"},
        "formations": {
            4: [
                {"n":1,"type":"DDA","label":"DDA","cab":True,"panto":False,"motor":False,"accessible":True,"toilet":True},
                {"n":2,"type":"DND","label":"DND","cab":True,"panto":True,"motor":True,"accessible":False},
                {"n":3,"type":"DN", "label":"DN", "cab":False,"panto":True,"motor":True,"accessible":False},
                {"n":4,"type":"DD", "label":"DD", "cab":True,"panto":False,"motor":False,"accessible":True},
            ],
            6: [
                {"n":1,"type":"DDA","label":"DDA","cab":True,"panto":False,"motor":False,"accessible":True,"toilet":True},
                {"n":2,"type":"DND","label":"DND","cab":True,"panto":True,"motor":True,"accessible":False},
                {"n":3,"type":"DNL","label":"DNL","cab":False,"panto":True,"motor":True,"accessible":False,"luggage":True},
                {"n":4,"type":"DN", "label":"DN", "cab":False,"panto":True,"motor":True,"accessible":False},
                {"n":5,"type":"DND","label":"DND","cab":True,"panto":True,"motor":True,"accessible":False},
                {"n":6,"type":"DD", "label":"DD", "cab":True,"panto":False,"motor":False,"accessible":True},
            ],
            8:  "couple:4",
            10: "couple:6+4",
        },
    },
    "T": {
        "name": "Tangara (T Set)", "operator": "Sydney Trains",
        "double_deck": True, "air_conditioned": True,
        "electric": True, "diesel": False,
        "introduced": 1988, "max_speed": 115,
        "notes": "455 carriages by Goninan. D-N-N-D configuration. Runs as 4 or 8 car (coupled). Fixed seats facing both directions.",
        "colors": {"body":"#F4B942","cab":"#c49030"},
        "formations": {
            4: [
                {"n":1,"type":"DT","label":"D","cab":True,"panto":True,"motor":False,"accessible":False},
                {"n":2,"type":"M", "label":"N","cab":False,"panto":False,"motor":True,"accessible":False},
                {"n":3,"type":"M", "label":"N","cab":False,"panto":False,"motor":True,"accessible":False},
                {"n":4,"type":"DT","label":"D","cab":True,"panto":True,"motor":False,"accessible":False},
            ],
            8: "couple:4",
        },
    },
    "M": {
        "name": "Millennium (M Set)", "operator": "Sydney Trains",
        "double_deck": True, "air_conditioned": True,
        "electric": True, "diesel": False,
        "introduced": 2002, "max_speed": 130,
        "notes": "35 four-car sets by EDi Rail. Runs 4 or 8 car. D-N-N-D. First Sydney train with AC drive system.",
        "colors": {"body":"#2D6A2D","cab":"#1a4a1a"},
        "formations": {
            4: [
                {"n":1,"type":"DT","label":"D","cab":True,"panto":True,"motor":False,"accessible":True},
                {"n":2,"type":"M", "label":"N","cab":False,"panto":False,"motor":True,"accessible":False},
                {"n":3,"type":"M", "label":"N","cab":False,"panto":False,"motor":True,"accessible":False},
                {"n":4,"type":"DT","label":"D","cab":True,"panto":True,"motor":False,"accessible":True},
            ],
            8: "couple:4",
        },
    },
    "H": {
        "name": "OSCar (H Set)", "operator": "Sydney Trains / NSW TrainLink",
        "double_deck": True, "air_conditioned": True,
        "electric": True, "diesel": False,
        "introduced": 2004, "max_speed": 160,
        "notes": "Outer-suburban/intercity. DM-T-T-DM. Runs 4 or 8 car. Being cascaded to suburban with D set arrivals.",
        "colors": {"body":"#8B3A00","cab":"#5a2500"},
        "formations": {
            4: [
                {"n":1,"type":"DM","label":"DM","cab":True,"panto":True,"motor":True,"accessible":True,"toilet":True},
                {"n":2,"type":"T", "label":"T", "cab":False,"panto":False,"motor":False,"accessible":False},
                {"n":3,"type":"T", "label":"T", "cab":False,"panto":False,"motor":False,"accessible":False},
                {"n":4,"type":"DM","label":"DM","cab":True,"panto":True,"motor":True,"accessible":True,"toilet":True},
            ],
            8: "couple:4",
        },
    },
    "K": {
        "name": "K Set", "operator": "NSW TrainLink",
        "double_deck": True, "air_conditioned": True,
        "electric": True, "diesel": False,
        "introduced": 1964, "max_speed": 115,
        "notes": "Intercity double-deck sets. Being retired as D sets enter service.",
        "colors": {"body":"#C00000","cab":"#800000"},
        "formations": {
            8: [
                {"n":1,"type":"DT","label":"DT","cab":True,"panto":True,"motor":False,"accessible":False},
                {"n":2,"type":"M", "label":"M", "cab":False,"panto":False,"motor":True,"accessible":False},
                {"n":3,"type":"T", "label":"T", "cab":False,"panto":False,"motor":False,"accessible":False},
                {"n":4,"type":"M", "label":"M", "cab":False,"panto":False,"motor":True,"accessible":False},
                {"n":5,"type":"M", "label":"M", "cab":False,"panto":False,"motor":True,"accessible":False},
                {"n":6,"type":"T", "label":"T", "cab":False,"panto":False,"motor":False,"accessible":False},
                {"n":7,"type":"M", "label":"M", "cab":False,"panto":False,"motor":True,"accessible":False},
                {"n":8,"type":"DT","label":"DT","cab":True,"panto":True,"motor":False,"accessible":False},
            ],
        },
    },
    "V": {
        "name": "V Set", "operator": "NSW TrainLink",
        "double_deck": True, "air_conditioned": True,
        "electric": True, "diesel": False,
        "introduced": 1964, "max_speed": 115,
        "notes": "Intercity double-deck. Retired 2024 as D sets replace them.",
        "colors": {"body":"#C00000","cab":"#800000"},
        "formations": {
            4: [
                {"n":1,"type":"DT","label":"DT","cab":True,"panto":True,"motor":False,"accessible":False},
                {"n":2,"type":"M", "label":"M", "cab":False,"panto":False,"motor":True,"accessible":False},
                {"n":3,"type":"M", "label":"M", "cab":False,"panto":False,"motor":True,"accessible":False},
                {"n":4,"type":"DT","label":"DT","cab":True,"panto":True,"motor":False,"accessible":False},
            ],
            8: "couple:4",
        },
    },
    "S": {
        "name": "S Set", "operator": "Sydney Trains (retired 2019)",
        "double_deck": True, "air_conditioned": False,
        "electric": True, "diesel": False,
        "introduced": 1972, "max_speed": 115,
        "notes": "Stainless steel double-deck. NOT air conditioned. Retired 2019.",
        "colors": {"body":"#4472C4","cab":"#2a4a94"},
        "formations": {
            8: [
                {"n":1,"type":"DT","label":"DT","cab":True,"panto":True,"motor":False,"accessible":False},
                {"n":2,"type":"M", "label":"M", "cab":False,"panto":False,"motor":True,"accessible":False},
                {"n":3,"type":"T", "label":"T", "cab":False,"panto":False,"motor":False,"accessible":False},
                {"n":4,"type":"M", "label":"M", "cab":False,"panto":False,"motor":True,"accessible":False},
                {"n":5,"type":"M", "label":"M", "cab":False,"panto":False,"motor":True,"accessible":False},
                {"n":6,"type":"T", "label":"T", "cab":False,"panto":False,"motor":False,"accessible":False},
                {"n":7,"type":"M", "label":"M", "cab":False,"panto":False,"motor":True,"accessible":False},
                {"n":8,"type":"DT","label":"DT","cab":True,"panto":True,"motor":False,"accessible":False},
            ],
        },
    },
    "C": {
        "name": "C Set", "operator": "Sydney Trains (retired 2021)",
        "double_deck": True, "air_conditioned": True,
        "electric": True, "diesel": False,
        "introduced": 1964, "max_speed": 115,
        "notes": "Retired February 2021 with arrival of B sets.",
        "colors": {"body":"#7030A0","cab":"#4a1a70"},
        "formations": {
            8: [
                {"n":1,"type":"DT","label":"DT","cab":True,"panto":True,"motor":False,"accessible":False},
                {"n":2,"type":"M", "label":"M", "cab":False,"panto":False,"motor":True,"accessible":False},
                {"n":3,"type":"T", "label":"T", "cab":False,"panto":False,"motor":False,"accessible":False},
                {"n":4,"type":"M", "label":"M", "cab":False,"panto":False,"motor":True,"accessible":False},
                {"n":5,"type":"M", "label":"M", "cab":False,"panto":False,"motor":True,"accessible":False},
                {"n":6,"type":"T", "label":"T", "cab":False,"panto":False,"motor":False,"accessible":False},
                {"n":7,"type":"M", "label":"M", "cab":False,"panto":False,"motor":True,"accessible":False},
                {"n":8,"type":"DT","label":"DT","cab":True,"panto":True,"motor":False,"accessible":False},
            ],
        },
    },
    "X": {
        "name": "XPT", "operator": "NSW TrainLink",
        "double_deck": False, "air_conditioned": True,
        "electric": False, "diesel": True,
        "introduced": 1982, "max_speed": 160,
        "notes": "Push-pull diesel. Based on UK IC125. XP power cars at each end. Buffet car, first/economy/sleeper. Services to Melbourne, Brisbane, Dubbo, Grafton, Casino.",
        "colors": {"body":"#E4022D","cab":"#a00020"},
        "formations": {
            5: [
                {"n":1,"type":"XP","label":"XP","cab":True,"diesel":True,"motor":True,"accessible":False},
                {"n":2,"type":"XF","label":"XF","cab":False,"motor":False,"class_type":"Economy","accessible":False},
                {"n":3,"type":"XF","label":"XF","cab":False,"motor":False,"class_type":"Economy","accessible":False},
                {"n":4,"type":"XBR","label":"XBR","cab":False,"motor":False,"class_type":"Buffet/First","buffet":True,"accessible":True,"toilet":True},
                {"n":5,"type":"XP","label":"XP","cab":True,"diesel":True,"motor":True,"accessible":False},
            ],
            7: [
                {"n":1,"type":"XP","label":"XP","cab":True,"diesel":True,"motor":True,"accessible":False},
                {"n":2,"type":"XF","label":"XF","cab":False,"motor":False,"class_type":"Economy","accessible":False},
                {"n":3,"type":"XF","label":"XF","cab":False,"motor":False,"class_type":"Economy","accessible":False},
                {"n":4,"type":"XBR","label":"XBR","cab":False,"motor":False,"class_type":"Buffet/First","buffet":True,"accessible":True,"toilet":True},
                {"n":5,"type":"XL","label":"XL","cab":False,"motor":False,"class_type":"First Class","accessible":False},
                {"n":6,"type":"XF","label":"XF","cab":False,"motor":False,"class_type":"Economy","accessible":False},
                {"n":7,"type":"XP","label":"XP","cab":True,"diesel":True,"motor":True,"accessible":False},
            ],
            8: [
                {"n":1,"type":"XP","label":"XP","cab":True,"diesel":True,"motor":True,"accessible":False},
                {"n":2,"type":"XF","label":"XF","cab":False,"motor":False,"class_type":"Economy","accessible":False},
                {"n":3,"type":"XF","label":"XF","cab":False,"motor":False,"class_type":"Economy","accessible":False},
                {"n":4,"type":"XBR","label":"XBR","cab":False,"motor":False,"class_type":"Buffet/First","buffet":True,"accessible":True,"toilet":True},
                {"n":5,"type":"XAM","label":"XAM","cab":False,"motor":False,"class_type":"Sleeper","sleeper":True,"accessible":True,"toilet":True},
                {"n":6,"type":"XAM","label":"XAM","cab":False,"motor":False,"class_type":"Sleeper","sleeper":True,"accessible":True},
                {"n":7,"type":"XL","label":"XL","cab":False,"motor":False,"class_type":"First Class","accessible":False},
                {"n":8,"type":"XP","label":"XP","cab":True,"diesel":True,"motor":True,"accessible":False},
            ],
        },
    },
    "P": {
        "name": "Xplorer (P Set)", "operator": "NSW TrainLink",
        "double_deck": False, "air_conditioned": True,
        "electric": False, "diesel": True,
        "introduced": 1993, "max_speed": 160,
        "notes": "DMU railcar. 2 or 3 car. Buffet, toilets, luggage racks. Services to Canberra, Griffith, Broken Hill.",
        "colors": {"body":"#FF6600","cab":"#c04400"},
        "formations": {
            2: [
                {"n":1,"type":"DP","label":"DP","cab":True,"diesel":True,"motor":True,"accessible":True,"toilet":True},
                {"n":2,"type":"DP","label":"DP","cab":True,"diesel":True,"motor":True,"accessible":True,"toilet":True},
            ],
            3: [
                {"n":1,"type":"DP","label":"DP","cab":True,"diesel":True,"motor":True,"accessible":True,"toilet":True},
                {"n":2,"type":"DS","label":"DS","cab":False,"diesel":False,"motor":False,"accessible":False,"buffet":True},
                {"n":3,"type":"DP","label":"DP","cab":True,"diesel":True,"motor":True,"accessible":True,"toilet":True},
            ],
        },
    },
    "N": {
        "name": "Endeavour (N Set)", "operator": "NSW TrainLink",
        "double_deck": False, "air_conditioned": True,
        "electric": False, "diesel": True,
        "introduced": 1993, "max_speed": 130,
        "notes": "2-car diesel DMU. Regional services in NSW.",
        "colors": {"body":"#8B4513","cab":"#5c2d0a"},
        "formations": {
            2: [
                {"n":1,"type":"DP","label":"DP","cab":True,"diesel":True,"motor":True,"accessible":True,"toilet":True},
                {"n":2,"type":"DP","label":"DP","cab":True,"diesel":True,"motor":True,"accessible":True,"toilet":True},
            ],
        },
    },
    "J": {
        "name": "Hunter Railcar (J Set)", "operator": "NSW TrainLink",
        "double_deck": False, "air_conditioned": True,
        "electric": False, "diesel": True,
        "introduced": 1994, "max_speed": 130,
        "notes": "2-car DMU for Hunter Valley services.",
        "colors": {"body":"#006633","cab":"#004422"},
        "formations": {
            2: [
                {"n":1,"type":"DP","label":"DP","cab":True,"diesel":True,"motor":True,"accessible":True,"toilet":True},
                {"n":2,"type":"DP","label":"DP","cab":True,"diesel":True,"motor":True,"accessible":True,"toilet":True},
            ],
        },
    },
    "R": {
        "name": "New Regional Fleet (R Set)", "operator": "NSW TrainLink",
        "double_deck": False, "air_conditioned": True,
        "electric": True, "diesel": False,
        "introduced": 2026, "max_speed": 200,
        "notes": "Bi-mode Stadler FLIRT. 3 or 6 car. Replaces XPT and Xplorer on regional services.",
        "colors": {"body":"#003087","cab":"#001a4d"},
        "formations": {
            3: [
                {"n":1,"type":"DM","label":"DM","cab":True,"motor":True,"accessible":True,"toilet":True},
                {"n":2,"type":"M", "label":"M", "cab":False,"motor":True,"accessible":False},
                {"n":3,"type":"DM","label":"DM","cab":True,"motor":True,"accessible":True,"toilet":True},
            ],
            6: "couple:3",
        },
    },
    "MET": {
        "name": "Metropolis", "operator": "Sydney Metro",
        "double_deck": False, "air_conditioned": True,
        "electric": True, "diesel": False,
        "introduced": 2019, "max_speed": 100,
        "notes": "Alstom Metropolis. 6-car fixed formation. ATO driverless operation. CCTV throughout.",
        "colors": {"body":"#009B77","cab":"#006650"},
        "formations": {
            6: [
                {"n":1,"type":"DM","label":"DM","cab":True,"panto":True,"motor":True,"accessible":True},
                {"n":2,"type":"M", "label":"M", "cab":False,"panto":True,"motor":True,"accessible":False},
                {"n":3,"type":"M", "label":"M", "cab":False,"panto":True,"motor":True,"accessible":False},
                {"n":4,"type":"M", "label":"M", "cab":False,"panto":True,"motor":True,"accessible":False},
                {"n":5,"type":"M", "label":"M", "cab":False,"panto":True,"motor":True,"accessible":False},
                {"n":6,"type":"DM","label":"DM","cab":True,"panto":True,"motor":True,"accessible":True},
            ],
        },
    },
    "G": {
        "name": "Freight / Locomotive", "operator": "Various freight operators",
        "double_deck": False, "air_conditioned": False,
        "electric": False, "diesel": True,
        "introduced": None, "max_speed": None,
        "notes": "Freight locomotive or special working. No passenger consist.",
        "colors": {"body":"#444444","cab":"#222222"},
        "formations": {},
    },
    "L": {
        "name": "Light Locomotive", "operator": "Sydney Trains (maintenance)",
        "double_deck": False, "air_conditioned": False,
        "electric": False, "diesel": False,
        "introduced": None, "max_speed": None,
        "notes": "Maintenance locomotive.",
        "colors": {"body":"#555555","cab":"#333333"},
        "formations": {},
    },
}


def get_metro_info(route_id):
    if not route_id: return None
    for prefix, label, name in METRO_ROUTE_MAP:
        if route_id.startswith(prefix):
            return {"label": label, "name": name, "color": "#009B77"}
    if "_M" in route_id or route_id.startswith("M1") or route_id.startswith("M2"):
        return {"label": "M1", "name": "Sydney Metro", "color": "#009B77"}
    return None

def get_route_color(rid):
    if not rid: return "#666"
    metro = get_metro_info(rid)
    if metro: return metro["color"]
    for k, v in ROUTE_COLORS.items():
        if rid.startswith(k): return v
    return "#666"

def get_route_short(route_id, mode):
    if mode == "metro":
        info = get_metro_info(route_id)
        return info["label"] if info else "M1"
    if not route_id: return ""
    for k in ROUTE_COLORS:
        if route_id.startswith(k): return k
    return route_id[:4]


def parse_trip_id(trip_id):
    """
    Extract fleet code + car count from trip_id structure.
    e.g. 770G.1371.142.2.B.8.89759584 -> fleet=B, cars=8
    """
    if not trip_id: return {}
    parts = trip_id.split(".")
    valid = set(FLEET.keys()) - {"MET", "G", "L"}
    for i, part in enumerate(parts):
        if len(part) == 1 and part.upper() in valid and i+1 < len(parts) and parts[i+1].isdigit():
            return {"fleet_code": part.upper(), "cars": int(parts[i+1])}
    return {}


def resolve_consist(fleet_code, car_count):
    """Return (fleet_info, car_list) resolving coupled variants."""
    info = FLEET.get(fleet_code)
    if not info or not info.get("formations"):
        return info, []
    forms = info["formations"]
    # Exact match
    if car_count and car_count in forms:
        v = forms[car_count]
        if isinstance(v, list):
            return info, v
        if isinstance(v, str) and v.startswith("couple:"):
            spec = v[7:]
            if "+" in spec:
                a, b = [int(x) for x in spec.split("+")]
                base_a = forms.get(a, [])
                base_b = forms.get(b, [])
                if isinstance(base_a, list) and isinstance(base_b, list):
                    combined = []
                    for c in base_a: combined.append({**c, "n": len(combined)+1})
                    for c in base_b: combined.append({**c, "n": len(combined)+1})
                    return info, combined
            else:
                base = int(spec)
                base_cars = forms.get(base, [])
                if isinstance(base_cars, list):
                    sets = (car_count // base) if car_count else 1
                    combined = []
                    for _ in range(sets):
                        for c in base_cars:
                            combined.append({**c, "n": len(combined)+1})
                    return info, combined
    # Fallback: largest available
    best = max((n for n, v in forms.items() if isinstance(v, list)), default=None)
    return info, forms.get(best, []) if best else []


# ------------------------------------------------------------------
# PROTO EXTENSION 1007 PARSER
# field 1  = Track Location ID / balise (e.g. "Sydenham.SM597BER")
# field 9  = air_conditioned (bool)
# field 10 = CarriageDescriptor (repeated)
#   CarriageDescriptor: field 1=sequence, field 3=occupancy_status, field 4=occupancy_pct
# ------------------------------------------------------------------
def _varint(data, pos):
    r, s = 0, 0
    while pos < len(data):
        b = data[pos]; pos += 1
        r |= (b & 0x7F) << s
        if not (b & 0x80): return r, pos
        s += 7
    return r, pos

def _ld(data, pos):
    n, pos = _varint(data, pos)
    return data[pos:pos+n], pos+n

def _parse_carriage(data):
    car = {"seq": None, "occ_status": None, "occ_pct": None}
    pos = 0
    while pos < len(data):
        try:
            tag, pos = _varint(data, pos)
            fn = tag >> 3; wt = tag & 7
            if wt == 0:
                v, pos = _varint(data, pos)
                if fn == 1: car["seq"] = v
                if fn == 3: car["occ_status"] = v
                if fn == 4: car["occ_pct"] = v
            elif wt == 2: _, pos = _ld(data, pos)
            elif wt == 1: pos += 8
            elif wt == 5: pos += 4
            else: break
        except: break
    return car

def parse_ext_1007(raw):
    result = {"location_id": "", "air_con": None, "carriages": []}
    pos = 0
    while pos < len(raw):
        try:
            tag, pos = _varint(raw, pos)
            fn = tag >> 3; wt = tag & 7
            if wt == 0: _, pos = _varint(raw, pos)
            elif wt == 2:
                inner, pos = _ld(raw, pos)
                if fn == 1007:
                    ipos = 0
                    while ipos < len(inner):
                        try:
                            itag, ipos = _varint(inner, ipos)
                            ifn = itag >> 3; iwt = itag & 7
                            if iwt == 0:
                                val, ipos = _varint(inner, ipos)
                                if ifn == 9: result["air_con"] = bool(val)
                            elif iwt == 2:
                                idat, ipos = _ld(inner, ipos)
                                if ifn == 1: result["location_id"] = idat.decode("utf-8","ignore")
                                elif ifn == 10: result["carriages"].append(_parse_carriage(idat))
                            elif iwt == 1: ipos += 8
                            elif iwt == 5: ipos += 4
                            else: break
                        except: break
                    return result
            elif wt == 1: pos += 8
            elif wt == 5: pos += 4
            else: break
        except: break
    return result


# ------------------------------------------------------------------
# DB HELPERS
# ------------------------------------------------------------------
live_trains = {}
lock = threading.Lock()

def fetch_raw(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.content

def db():
    return sqlite3.connect("gtfs.db", check_same_thread=False)

def stop_name(stop_id):
    try:
        c = db(); row = c.execute("SELECT stop_name FROM stops WHERE stop_id=?", (stop_id,)).fetchone(); c.close()
        return row[0] if row else stop_id
    except: return stop_id

def trip_info(trip_id):
    try:
        c = db()
        row = c.execute("""SELECT t.trip_headsign,t.direction_id,r.route_short_name,
            r.route_long_name,r.route_color,t.trip_note,t.route_id
            FROM trips t LEFT JOIN routes r ON t.route_id=r.route_id WHERE t.trip_id=?""",
            (trip_id,)).fetchone()
        c.close()
        if row: return {"headsign":row[0],"direction":row[1],"route_short":row[2],
                        "route_long":row[3],"route_color":row[4],"trip_note":row[5],"route_id":row[6]}
    except: pass
    return {}

def stop_times(trip_id):
    try:
        c = db()
        rows = c.execute("""SELECT st.stop_id,st.arrival_time,st.departure_time,st.stop_sequence,s.stop_name
            FROM stop_times st LEFT JOIN stops s ON st.stop_id=s.stop_id
            WHERE st.trip_id=? ORDER BY CAST(st.stop_sequence AS INTEGER)""", (trip_id,)).fetchall()
        c.close()
        return [{"stop_id":r[0],"arrival":r[1],"departure":r[2],"sequence":r[3],"stop_name":r[4] or r[0]} for r in rows]
    except: return []


# ------------------------------------------------------------------
# POLL LOOP
# ------------------------------------------------------------------
def poll():
    while True:
        new = {}
        for mode, urls in FEEDS.items():
            try:
                vp_raw = fetch_raw(urls["vehicles"])
                vp = gtfs_realtime_pb2.FeedMessage(); vp.ParseFromString(vp_raw)

                for ent in vp.entity:
                    if not ent.HasField("vehicle"): continue
                    v = ent.vehicle
                    trip_id = v.trip.trip_id
                    route_id = v.trip.route_id
                    if route_id in ("RTTA_DEF","RTTA_REV"): continue

                    # Run number
                    # Sydney Trains: vehicle.label = headsign (IGNORE), use trip_id prefix
                    # Metro: vehicle.label = set number (RS019) which is the run identifier
                    lbl = v.vehicle.label or ""
                    if mode == "metro":
                        run = lbl  # RS019 etc
                        metro_set_no = v.vehicle.license_plate or lbl
                    else:
                        metro_set_no = ""
                        if trip_id:
                            parts_tid = trip_id.split(".")
                            pfx = parts_tid[0]
                            if pfx == "NonTimetabled" and len(parts_tid) > 1:
                                run = parts_tid[1]  # e.g. "92--" from "NonTimetabled.92--"
                            elif pfx and len(pfx) <= 12 and " " not in pfx:
                                run = pfx  # e.g. "61-B", "770G", "146H"
                            else:
                                run = ""
                        else:
                            run = ""

                    # Fleet from trip_id
                    if mode == "metro":
                        fleet_code, car_count = "MET", 6
                    else:
                        tm = parse_trip_id(trip_id)
                        fleet_code = tm.get("fleet_code", "")
                        car_count  = tm.get("cars")

                    # Ext 1007
                    try:
                        ext = parse_ext_1007(v.SerializeToString())
                        loc_id   = ext["location_id"]
                        air_api  = ext["air_con"]
                        carr_api = ext["carriages"]
                        if not car_count and carr_api: car_count = len(carr_api)
                    except: loc_id=""; air_api=None; carr_api=[]

                    # Resolve consist
                    finfo, consist = resolve_consist(fleet_code, car_count or 0)

                    # Merge per-car occupancy
                    if carr_api and consist:
                        consist = [dict(c) for c in consist]
                        sorted_api = sorted(carr_api, key=lambda c: c.get("seq") or 0)
                        for i, ac in enumerate(sorted_api):
                            if i < len(consist):
                                consist[i]["occ_pct"]    = ac.get("occ_pct")
                                consist[i]["occ_status"] = ac.get("occ_status")

                    air_con = air_api if air_api is not None else (finfo.get("air_conditioned") if finfo else None)
                    spd = v.position.speed
                    # Sydney Trains does NOT populate speed (always 0.0) - confirmed from API data
                    # Metro DOES populate speed correctly
                    if mode == "metro" and spd and spd > 0:
                        speed_kmh = round(spd * 3.6, 1)
                    else:
                        speed_kmh = None  # None = not reported, vs 0 = actually stopped

                    ti = trip_info(trip_id)
                    rs = ti.get("route_short") or get_route_short(route_id, mode) or route_id or ""

                    is_special = (
                        v.trip.schedule_relationship == 1
                        or "NonTimetabled" in trip_id
                        or (not fleet_code and mode != "metro")
                    )

                    new[trip_id] = {
                        "trip_id": trip_id, "mode": mode,
                        "run_number": run,
                        "set_number": metro_set_no,
                        "fleet_code": fleet_code,
                        "fleet_name": finfo["name"] if finfo else "Unknown",
                        "car_count": car_count,
                        "consist": consist,
                        "air_conditioned": air_con,
                        "double_deck": finfo.get("double_deck") if finfo else None,
                        "diesel": finfo.get("diesel", False) if finfo else False,
                        "electric": finfo.get("electric", False) if finfo else False,
                        "introduced": finfo.get("introduced") if finfo else None,
                        "max_speed": finfo.get("max_speed") if finfo else None,
                        "fleet_notes": finfo.get("notes","") if finfo else "",
                        "location_id": loc_id,
                        "lat": v.position.latitude,
                        "lon": v.position.longitude,
                        "bearing": v.position.bearing,
                        "speed": speed_kmh,  # None if not reported by this operator
                        "current_stop_seq": v.current_stop_sequence,
                        "current_status": v.current_status,
                        "timestamp": v.timestamp,
                        "route_id": route_id,
                        "route_short": rs,
                        "route_color": get_route_color(rs or route_id),
                        "headsign": ti.get("headsign",""),
                        "route_long": ti.get("route_long","") or (get_metro_info(route_id) or {}).get("name",""),
                        "trip_note": ti.get("trip_note",""),
                        "is_special": is_special,
                        "start_date": v.trip.start_date,
                        "next_stop": None,
                        "delay_seconds": 0,
                        "cancelled": False,
                        "stop_updates": [],
                    }

                tu_raw = fetch_raw(urls["trips"])
                tu = gtfs_realtime_pb2.FeedMessage(); tu.ParseFromString(tu_raw)

                for ent in tu.entity:
                    if not ent.HasField("trip_update"): continue
                    upd = ent.trip_update
                    tid = upd.trip.trip_id
                    if tid not in new: continue
                    updates = []
                    for stu in upd.stop_time_update:
                        d  = stu.arrival.delay if stu.HasField("arrival") else (stu.departure.delay if stu.HasField("departure") else None)
                        at = stu.arrival.time  if stu.HasField("arrival") else None
                        dt = stu.departure.time if stu.HasField("departure") else None
                        sk = stu.schedule_relationship == 1
                        updates.append({"stop_id":stu.stop_id,"stop_sequence":stu.stop_sequence,
                                        "delay":d,"arrival_time":at,"departure_time":dt,
                                        "skipped":sk,"stop_name":stop_name(stu.stop_id)})
                    new[tid]["stop_updates"] = updates
                    ns = [u for u in updates if not u["skipped"]]
                    if ns: new[tid]["next_stop"] = ns[0]["stop_name"]; new[tid]["delay_seconds"] = ns[0]["delay"] or 0
                    elif updates: new[tid]["next_stop"] = updates[0]["stop_name"]
                    if updates and all(u["skipped"] for u in updates): new[tid]["cancelled"] = True

            except Exception as e:
                print(f"[{mode}] error: {e}")
                import traceback; traceback.print_exc()

        with lock: live_trains.clear(); live_trains.update(new)
        print(f"[poll] {len(live_trains)} trains | {time.strftime('%H:%M:%S')}")
        time.sleep(15)


# ------------------------------------------------------------------
# API ROUTES
# ------------------------------------------------------------------
@app.route("/api/trains")
def api_trains():
    with lock: return jsonify(list(live_trains.values()))

@app.route("/api/train/trip/<path:trip_id>")
def api_trip(trip_id):
    with lock: t = live_trains.get(trip_id)
    if not t: return jsonify({"error":"not found"}), 404
    t = dict(t); t["scheduled_stops"] = stop_times(trip_id)
    return jsonify(t)

@app.route("/api/timetable")
def api_timetable():
    try:
        import datetime
        today = datetime.date.today()
        ds = today.strftime("%Y%m%d"); dc = today.strftime("%A").lower()
        lf = request.args.get("line","")
        c = db()
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if "calendar_dates" in tables:
            cal = "JOIN calendar_dates cd ON t.service_id=cd.service_id WHERE cd.date=? AND cd.exception_type=1"
            params = [ds]
        elif "calendar" in tables:
            cal = f"JOIN calendar cc ON t.service_id=cc.service_id WHERE cc.{dc}='1' AND cc.start_date<=? AND cc.end_date>=?"
            params = [ds, ds]
        else: return jsonify([])
        rows = c.execute(f"""SELECT DISTINCT t.trip_id,t.trip_headsign,t.direction_id,
            r.route_short_name,r.route_long_name,MIN(st.departure_time) as first_dep,t.trip_note
            FROM trips t LEFT JOIN routes r ON t.route_id=r.route_id
            LEFT JOIN stop_times st ON t.trip_id=st.trip_id {cal}
            GROUP BY t.trip_id ORDER BY first_dep LIMIT 2000""", params).fetchall()
        c.close()
        with lock: snap = dict(live_trains)
        out = []
        for r in rows:
            tid = r[0]; rs = r[3] or ""
            if lf and not rs.startswith(lf): continue
            lv = snap.get(tid, {})
            out.append({"trip_id":tid,"headsign":r[1],"direction":r[2],"route_short":rs,
                        "route_long":r[4],"first_dep":r[5],"trip_note":r[6],
                        "route_color":get_route_color(rs),"is_live":tid in snap,
                        "run_number":lv.get("run_number",""),"fleet_code":lv.get("fleet_code",""),
                        "fleet_name":lv.get("fleet_name",""),"car_count":lv.get("car_count"),
                        "delay":lv.get("delay_seconds",0),"is_special":lv.get("is_special",False),
                        "air_conditioned":lv.get("air_conditioned"),"speed":lv.get("speed",0)})
        return jsonify(out)
    except Exception as e:
        import traceback; traceback.print_exc(); return jsonify({"error":str(e)}), 500

@app.route("/api/fleet")
def api_fleet():
    return jsonify({k: {**v, "formations": {str(n): (cars if isinstance(cars, list) else cars)
        for n, cars in v.get("formations",{}).items()}} for k, v in FLEET.items()})

@app.route("/")
def index(): return send_from_directory(".", "index.html")

if __name__ == "__main__":
    # Auto-build DB in background if missing (for hosted deployments like Render)
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gtfs.db")
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        print("gtfs.db not found — building in background (timetable tab unavailable until done)...")
        def build_db():
            try:
                import load_gtfs
                load_gtfs.main()
                print("gtfs.db ready — timetable tab now available")
            except Exception as e:
                print(f"gtfs.db build failed: {e}")
        threading.Thread(target=build_db, daemon=True).start()

    threading.Thread(target=poll, daemon=True).start()
    print("NSW Rail Tracker running at http://localhost:5000")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)