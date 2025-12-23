import os
import time
import requests
from bs4 import BeautifulSoup
from geopy.distance import geodesic
from geopy.geocoders import Nominatim

# ================= CONFIG =================

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
CHECK_INTERVAL = 600  # 10 minutes
USER_POSTCODE = "DN9"
MAX_DISTANCE_MILES = 25

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PokemonRestockBot/1.0)"
}

# ================= SAFETY CHECK =================

if not DISCORD_WEBHOOK:
    raise RuntimeError("DISCORD_WEBHOOK environment variable is missing")

# ================= LOCATION SETUP =================

geolocator = Nominatim(user_agent="pokemon_restocks")
user_location = geolocator.geocode(USER_POSTCODE)

if not user_location:
    raise RuntimeError("Failed to geocode postcode")

USER_COORD = (user_location.latitude, user_location.longitude)

# ================= STORES =================

TIERS = {
    1: {
        "Smyths Doncaster": (
            "https://www.smythstoys.com/uk/en-gb/search/?text=pokemon",
            (53.552, -1.128),
        ),
        "The Entertainer Doncaster": (
            "https://www.thetoyshop.com/search/?text=pokemon",
            (53.521, -1.120),
        ),
        "Argos Doncaster": (
            "https://www.argos.co.uk/search/pokemon-trading-cards/",
            (53.525, -1.130),
        ),
        "WHSmith Doncaster": (
            "https://www.whsmith.co.uk/search?query=pokemon",
            (53.518, -1.121),
        ),
    },
    2: {
        "Tesco Doncaster": (
            "https://www.tesco.com/groceries/en-GB/search?query=pokemon",
            (53.523, -1.125),
        ),
        "Morrisons Doncaster": (
            "https://groceries.morrisons.com/search?entry=pokemon",
            (53.520, -1.127),
        ),
        "ASDA Doncaster": (
            "https://groceries.asda.com/search/pokemon",
            (53.519, -1.122),
        ),
        "Sainsbury's Doncaster": (
            "https://www.sainsburys.co.uk/gol-ui/SearchResults/pokemon",
            (53.518, -1.121),
        ),
    },
    3: {
        "Amazon UK": (
            "https://www.amazon.co.uk/s?k=pokemon+tcg",
            USER_COORD,
        ),
        "eBay UK": (
            "https://www.ebay.co.uk/sch/i.html?_nkw=pokemon+tcg",
            USER_COORD,
        ),
        "CEX UK": (
            "https://uk.webuy.com/search/?query=pokemon",
            USER_COORD,
        ),
        "Forbidden Planet": (
            "https://forbiddenplanet.com/catalogsearch/result/?q=pokemon",
            USER_COORD,
        ),
        "Waterstones": (
            "https://www.waterstones.com/books/search/term/pokemon",
            USER_COORD,
        ),
    },
}

# ================= KEYWORDS =================

SEALED_KEYWORDS = [
    "booster",
    "elite trainer box",
    "etb",
    "tin",
    "collection",
    "blister",
    "trading card",
]

TOP_PRIORITY_KEYWORDS = ["elite trainer box", "etb", "booster"]

IGNORE_KEYWORDS = ["single", "guide", "book", "magazine"]

seen_items = set()

# ================= HELPERS =================

def is_sealed(name: str) -> bool:
    name = name.lower()
    return any(k in name for k in SEALED_KEYWORDS) and not any(
        i in name for i in IGNORE_KEYWORDS
    )

def is_top_priority(name: str) -> bool:
    name = name.lower()
    return any(k in name for k in TOP_PRIORITY_KEYWORDS)

def within_distance(store_coord):
    return geodesic(USER_COORD, store_coord).miles <= MAX_DISTANCE_MILES

def send_discord(message: str):
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": message}, timeout=10)
    except Exception as e:
        print("Discord error:", e)

# ================= CORE LOGIC =================

def parse_store(store, url, tier, coord):
    if tier == 3 and not within_distance(coord):
        return

    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")

        items = [
            text.strip()
            for text in soup.stripped_strings
            if "pokemon" in text.lower()
            and 10 < len(text) < 120
            and is_sealed(text)
        ]

        new_items = [i for i in set(items) if i not in seen_items]
        if not new_items:
            return

        top_priority = [i for i in new_items if is_top_priority(i)]
        normal_items = [i for i in new_items if i not in top_priority]

        message = f"STORE RESTOCK DETECTED: {store} ({USER_POSTCODE})\n"

        if top_priority:
            message += "\nTOP PRIORITY ITEMS:\n"
            for i in top_priority[:10]:
                message += f"- {i}\n"
                seen_items.add(i)

        if normal_items:
            message += "\nOTHER SEALED ITEMS:\n"
            for i in normal_items[:10]:
                message += f"- {i}\n"
                seen_items.add(i)

        send_discord(message)

    except Exception as e:
        print(f"Error checking {store}: {e}")

# ================= MAIN LOOP =================

print("Pokemon Restock Bot started")

while True:
    try:
        for tier in TIERS:
            for store, (url, coord) in TIERS[tier].items():
                parse_store(store, url, tier, coord)
        time.sleep(CHECK_INTERVAL)
    except Exception as e:
        print("Main loop error:", e)
        time.sleep(60)
