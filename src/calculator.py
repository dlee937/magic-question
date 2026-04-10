"""
Sell price calculator. Computes maximum theoretical crop value
with mutation stacking, scale, friend bonus, and sell boost.

Stacking rules (from game source):
  1. Weather + Lunar mutations stack ADDITIVELY
     e.g. Frozen (×6) + Amberbound (×10) = ×16
  2. (Weather+Lunar total) × Colour = MULTIPLICATIVE
     e.g. ×16 × Rainbow (×50) = ×800
  3. Size scales linearly: sell = baseSell × (weight / baseWeight)
  4. Friend bonus is additive: +10% per extra player, max +50%
  5. Sell Boost ability: +20/30/40/50% on top
"""

import json
from dataclasses import dataclass
from pathlib import Path
from .config import DATA_DIR
from .entity_registry import INTERNAL_TO_DISPLAY

# ── Mutation categories ──
# Weather group: Wet, Chilled, Frozen, Thunderstruck (mutually exclusive within group)
# Lunar group: Dawnlit, Amberlit, Dawnbound, Amberbound (mutually exclusive within group)
# Colour group: Gold, Rainbow (mutually exclusive)

WEATHER_MUTATIONS = {"Wet", "Chilled", "Frozen", "Thunderstruck"}
LUNAR_MUTATIONS = {"Dawnlit", "Ambershine", "Dawncharged", "Ambercharged"}
COLOUR_MUTATIONS = {"Gold", "Rainbow"}

SELL_BOOST_TIERS = {
    "I": 0.20,
    "II": 0.30,
    "III": 0.40,
    "IV": 0.50,
}


@dataclass
class SellCalculation:
    crop_name: str
    base_sell: int
    max_scale: float
    scaled_sell: float
    weather_mutation: str | None
    weather_mult: float
    lunar_mutation: str | None
    lunar_mult: float
    colour_mutation: str | None
    colour_mult: float
    combined_mutation_mult: float
    sell_boost_pct: float
    friend_bonus_pct: float
    final_price: int
    breakdown: str


def _load_game_data() -> dict:
    with open(DATA_DIR / "source_truth.json") as f:
        return json.load(f)


def _get_mutation_multiplier(mutations: dict, mutation_id: str) -> float:
    return mutations.get(mutation_id, {}).get("coinMultiplier", 1)


def calculate_sell_price(
    crop_id: str,
    weather_mutation: str | None = None,
    lunar_mutation: str | None = None,
    colour_mutation: str | None = None,
    at_max_scale: bool = True,
    sell_boost_tier: str | None = None,
    friend_count: int = 0,
    data: dict | None = None,
) -> SellCalculation:
    """Calculate the sell price of a crop with mutations, scale, and bonuses.

    Args:
        crop_id: Internal crop ID (e.g. "MoonCelestial", "Mushroom")
        weather_mutation: One of Wet/Chilled/Frozen/Thunderstruck (internal ID)
        lunar_mutation: One of Dawnlit/Ambershine/Dawncharged/Ambercharged (internal ID)
        colour_mutation: Gold or Rainbow (internal ID)
        at_max_scale: Whether the crop is at max weight
        sell_boost_tier: "I", "II", "III", or "IV"
        friend_count: Number of additional players (0-5, each adds 10%)
        data: Pre-loaded game data (optional, loads from file if None)
    """
    if data is None:
        data = _load_game_data()

    crop = data["crops"].get(crop_id)
    if not crop:
        raise ValueError(f"Unknown crop: {crop_id}")

    mutations = data["mutations"]
    display = crop.get("displayName", INTERNAL_TO_DISPLAY.get(crop_id, crop_id))

    base_sell = crop["sellPrice"]
    max_scale = crop["maxScale"]

    # Step 1: Scale
    scale_factor = max_scale if at_max_scale else 1.0
    scaled_sell = base_sell * scale_factor

    # Step 2: Weather mutation multiplier
    w_mult = _get_mutation_multiplier(mutations, weather_mutation) if weather_mutation else 1
    # Step 3: Lunar mutation multiplier
    l_mult = _get_mutation_multiplier(mutations, lunar_mutation) if lunar_mutation else 1
    # Step 4: Colour mutation multiplier
    c_mult = _get_mutation_multiplier(mutations, colour_mutation) if colour_mutation else 1

    # Stacking: (weather + lunar - 1) × colour
    # Weather + Lunar are additive: combined = w_mult + l_mult - 1
    # Then colour is multiplicative on top
    if weather_mutation and lunar_mutation:
        base_mutation_mult = (w_mult + l_mult - 1)
    else:
        base_mutation_mult = max(w_mult, l_mult)

    combined_mutation_mult = base_mutation_mult * c_mult

    # Step 5: Sell boost
    sell_boost_pct = SELL_BOOST_TIERS.get(sell_boost_tier, 0) if sell_boost_tier else 0

    # Step 6: Friend bonus (10% per player, max 5 players = 50%)
    friend_count = min(max(friend_count, 0), 5)
    friend_bonus_pct = friend_count * 0.10

    # Final: baseSell × scale × mutations × (1 + sellBoost) × (1 + friendBonus)
    final = scaled_sell * combined_mutation_mult * (1 + sell_boost_pct) * (1 + friend_bonus_pct)
    final_price = int(final)

    # Build breakdown string
    parts = [f"Base: {base_sell:,} coins"]
    if at_max_scale and max_scale > 1:
        parts.append(f"× {max_scale}x scale = {int(scaled_sell):,}")

    mut_parts = []
    if weather_mutation:
        w_display = INTERNAL_TO_DISPLAY.get(weather_mutation, weather_mutation)
        mut_parts.append(f"{w_display} (×{w_mult})")
    if lunar_mutation:
        l_display = INTERNAL_TO_DISPLAY.get(lunar_mutation, lunar_mutation)
        mut_parts.append(f"{l_display} (×{l_mult})")
    if weather_mutation and lunar_mutation:
        mut_parts.append(f"= ×{base_mutation_mult} additive")
    if colour_mutation:
        c_display = INTERNAL_TO_DISPLAY.get(colour_mutation, colour_mutation)
        mut_parts.append(f"× {c_display} (×{c_mult})")
    if mut_parts:
        parts.append(f"Mutations: {' + '.join(mut_parts)} = ×{combined_mutation_mult}")

    if sell_boost_pct > 0:
        parts.append(f"Sell Boost {sell_boost_tier}: +{int(sell_boost_pct * 100)}%")
    if friend_bonus_pct > 0:
        parts.append(f"Friend bonus: +{int(friend_bonus_pct * 100)}% ({friend_count} players)")

    parts.append(f"TOTAL: {final_price:,} coins")

    return SellCalculation(
        crop_name=display,
        base_sell=base_sell,
        max_scale=max_scale,
        scaled_sell=scaled_sell,
        weather_mutation=weather_mutation,
        weather_mult=w_mult,
        lunar_mutation=lunar_mutation,
        lunar_mult=l_mult,
        colour_mutation=colour_mutation,
        colour_mult=c_mult,
        combined_mutation_mult=combined_mutation_mult,
        sell_boost_pct=sell_boost_pct,
        friend_bonus_pct=friend_bonus_pct,
        final_price=final_price,
        breakdown=" | ".join(parts),
    )


def max_sell_price(crop_id: str, data: dict | None = None) -> SellCalculation:
    """Calculate the absolute maximum sell price for a crop.
    Uses: Frozen + Amberbound + Rainbow + max scale + Sell Boost IV + 5 friends.
    """
    return calculate_sell_price(
        crop_id=crop_id,
        weather_mutation="Frozen",
        lunar_mutation="Ambercharged",
        colour_mutation="Rainbow",
        at_max_scale=True,
        sell_boost_tier="IV",
        friend_count=5,
        data=data,
    )


def compare_mutations(crop_id: str, data: dict | None = None) -> list[SellCalculation]:
    """Compare all useful mutation combos for a crop at max scale."""
    if data is None:
        data = _load_game_data()

    combos = [
        (None, None, None, "No mutations"),
        ("Frozen", None, None, "Frozen only"),
        (None, "Ambercharged", None, "Amberbound only"),
        ("Frozen", "Ambercharged", None, "Frozen + Amberbound"),
        (None, None, "Gold", "Gold only"),
        (None, None, "Rainbow", "Rainbow only"),
        ("Frozen", "Ambercharged", "Gold", "Frozen + Amberbound + Gold"),
        ("Frozen", "Ambercharged", "Rainbow", "Frozen + Amberbound + Rainbow"),
        ("Thunderstruck", "Ambercharged", "Rainbow", "Thunderstruck + Amberbound + Rainbow"),
        ("Frozen", "Dawncharged", "Rainbow", "Frozen + Dawnbound + Rainbow"),
    ]

    results = []
    for weather, lunar, colour, _label in combos:
        results.append(calculate_sell_price(
            crop_id=crop_id,
            weather_mutation=weather,
            lunar_mutation=lunar,
            colour_mutation=colour,
            at_max_scale=True,
            data=data,
        ))
    results.sort(key=lambda r: r.final_price, reverse=True)
    return results
