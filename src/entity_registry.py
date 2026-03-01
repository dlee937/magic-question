"""
Entity name resolution. Maps player-facing text to internal IDs.
Zero LLM cost — pure string matching.
"""

import re
from dataclasses import dataclass


@dataclass
class EntityMatch:
    display_name: str
    internal_id: str
    entity_type: str  # pet, crop, ability, mutation, weather, egg, tool, decor


# Master registry: display_name (lowercase) → (internal_id, entity_type)
_REGISTRY: dict[str, tuple[str, str]] = {
    # ── PETS (21) ──
    "worm": ("Worm", "pet"), "snail": ("Snail", "pet"), "bee": ("Bee", "pet"),
    "chicken": ("Chicken", "pet"), "bunny": ("Bunny", "pet"),
    "dragonfly": ("Dragonfly", "pet"), "pig": ("Pig", "pet"),
    "cow": ("Cow", "pet"), "turkey": ("Turkey", "pet"),
    "squirrel": ("Squirrel", "pet"), "turtle": ("Turtle", "pet"),
    "goat": ("Goat", "pet"), "snow fox": ("SnowFox", "pet"),
    "snowfox": ("SnowFox", "pet"), "stoat": ("Stoat", "pet"),
    "caribou": ("WhiteCaribou", "pet"), "white caribou": ("WhiteCaribou", "pet"),
    "pony": ("Pony", "pet"), "horse": ("Horse", "pet"),
    "fire horse": ("FireHorse", "pet"), "firehorse": ("FireHorse", "pet"),
    "butterfly": ("Butterfly", "pet"), "peacock": ("Peacock", "pet"),
    "capybara": ("Capybara", "pet"),

    # ── CROPS (44) ──
    "carrot": ("Carrot", "crop"), "cabbage": ("Cabbage", "crop"),
    "strawberry": ("Strawberry", "crop"), "aloe": ("Aloe", "crop"),
    "beet": ("Beet", "crop"), "rose": ("Rose", "crop"),
    "delphinium": ("Delphinium", "crop"), "fava bean": ("FavaBean", "crop"),
    "favabean": ("FavaBean", "crop"), "blueberry": ("Blueberry", "crop"),
    "apple": ("Apple", "crop"), "tulip": ("OrangeTulip", "crop"),
    "orange tulip": ("OrangeTulip", "crop"), "tomato": ("Tomato", "crop"),
    "daffodil": ("Daffodil", "crop"), "corn": ("Corn", "crop"),
    "watermelon": ("Watermelon", "crop"), "pumpkin": ("Pumpkin", "crop"),
    "echeveria": ("Echeveria", "crop"), "pear": ("Pear", "crop"),
    "gentian": ("Gentian", "crop"), "coconut": ("Coconut", "crop"),
    "pine tree": ("PineTree", "crop"), "pinetree": ("PineTree", "crop"),
    "banana": ("Banana", "crop"), "lily": ("Lily", "crop"),
    "camellia": ("Camellia", "crop"), "squash": ("Squash", "crop"),
    "peach": ("Peach", "crop"), "burro's tail": ("BurrosTail", "crop"),
    "burros tail": ("BurrosTail", "crop"), "mushroom": ("Mushroom", "crop"),
    "cactus": ("Cactus", "crop"), "bamboo": ("Bamboo", "crop"),
    "poinsettia": ("Poinsettia", "crop"), "violet cort": ("VioletCort", "crop"),
    "chrysanthemum": ("Chrysanthemum", "crop"), "mum": ("Chrysanthemum", "crop"),
    "grape": ("Grape", "crop"), "pepper": ("Pepper", "crop"),
    "lemon": ("Lemon", "crop"), "passion fruit": ("PassionFruit", "crop"),
    "passionfruit": ("PassionFruit", "crop"), "dragon fruit": ("DragonFruit", "crop"),
    "dragonfruit": ("DragonFruit", "crop"), "cacao": ("Cacao", "crop"),
    "lychee": ("Lychee", "crop"), "sunflower": ("Sunflower", "crop"),
    "starweaver": ("Starweaver", "crop"), "dawnbinder": ("DawnCelestial", "crop"),
    "moonbinder": ("MoonCelestial", "crop"),

    # ── MUTATIONS (10) ──
    "wet": ("Wet", "mutation"), "chilled": ("Chilled", "mutation"),
    "frozen": ("Frozen", "mutation"), "thunderstruck": ("Thunderstruck", "mutation"),
    "dawnlit": ("Dawnlit", "mutation"), "dawnbound": ("Dawncharged", "mutation"),
    "amberlit": ("Ambershine", "mutation"), "amberbound": ("Ambercharged", "mutation"),
    "gold": ("Gold", "mutation"), "rainbow": ("Rainbow", "mutation"),

    # ── WEATHER (5) ──
    "rain": ("Rain", "weather"), "snow": ("Frost", "weather"),
    "thunderstorm": ("Thunderstorm", "weather"), "dawn": ("Dawn", "weather"),
    "amber moon": ("AmberMoon", "weather"), "ambermoon": ("AmberMoon", "weather"),

    # ── EGGS (8) ──
    "common egg": ("CommonEgg", "egg"), "uncommon egg": ("UncommonEgg", "egg"),
    "rare egg": ("RareEgg", "egg"), "legendary egg": ("LegendaryEgg", "egg"),
    "snow egg": ("SnowEgg", "egg"), "winter egg": ("WinterEgg", "egg"),
    "horse egg": ("HorseEgg", "egg"), "mythical egg": ("MythicalEgg", "egg"),

    # ── TOOLS (key ones) ──
    "watering can": ("WateringCan", "tool"), "planter pot": ("PlanterPot", "tool"),
    "crop cleanser": ("CropCleanser", "tool"), "shovel": ("Shovel", "tool"),
    "garden shovel": ("Shovel", "tool"),
    "feeding trough": ("FeedingTrough", "tool"), "trough": ("FeedingTrough", "tool"),
    "pet hutch": ("PetHutch", "tool"), "seed silo": ("SeedSilo", "tool"),
    "decor shed": ("DecorShed", "tool"),
}

# Internal→display mapping for chunks
INTERNAL_TO_DISPLAY = {
    "Ambershine": "Amberlit", "Ambercharged": "Amberbound", "Dawncharged": "Dawnbound",
    "OrangeTulip": "Tulip", "FavaBean": "Fava Bean", "BurrosTail": "Burro's Tail",
    "PineTree": "Pine Tree", "VioletCort": "Violet Cort", "DragonFruit": "Dragon Fruit",
    "PassionFruit": "Passion Fruit", "DawnCelestial": "Dawnbinder",
    "MoonCelestial": "Moonbinder", "SnowFox": "Snow Fox", "FireHorse": "Fire Horse",
    "WhiteCaribou": "Caribou", "Frost": "Snow",
}

# Pre-compile: sort by length descending so "fire horse" matches before "horse"
_SORTED_KEYS = sorted(_REGISTRY.keys(), key=len, reverse=True)
_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(k) for k in _SORTED_KEYS) + r')\b',
    re.IGNORECASE
)


def find_entities(text: str) -> list[EntityMatch]:
    """Extract all game entities mentioned in user text."""
    seen_ids: set[str] = set()
    results: list[EntityMatch] = []
    for match in _PATTERN.finditer(text.lower()):
        key = match.group(0).lower()
        internal_id, entity_type = _REGISTRY[key]
        if internal_id in seen_ids:
            continue
        seen_ids.add(internal_id)
        display = INTERNAL_TO_DISPLAY.get(internal_id, internal_id)
        results.append(EntityMatch(
            display_name=display,
            internal_id=internal_id,
            entity_type=entity_type,
        ))
    return results


def resolve_name(text: str) -> EntityMatch | None:
    """Resolve a single entity name. Returns best match or None."""
    matches = find_entities(text)
    return matches[0] if matches else None


def display_name(internal_id: str) -> str:
    """Get display name for an internal ID."""
    return INTERNAL_TO_DISPLAY.get(internal_id, internal_id)
