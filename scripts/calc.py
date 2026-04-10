#!/usr/bin/env python3
"""
Sell price calculator CLI.

Usage:
  python scripts/calc.py max MoonCelestial           # Max possible sell
  python scripts/calc.py max Mushroom                # Max for Mushroom
  python scripts/calc.py compare MoonCelestial       # Compare all mutation combos
  python scripts/calc.py custom Bamboo --weather Frozen --lunar Ambercharged --colour Rainbow
  python scripts/calc.py top 10                      # Top 10 crops by max sell
  python scripts/calc.py tools                       # Show all available tools/options
"""

import sys
import json
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.calculator import calculate_sell_price, max_sell_price, compare_mutations
from src.calculator import WEATHER_MUTATIONS, LUNAR_MUTATIONS, COLOUR_MUTATIONS, SELL_BOOST_TIERS
from src.entity_registry import INTERNAL_TO_DISPLAY
from src.config import DATA_DIR


def fmt(n) -> str:
    return f"{n:,}"


def load_data():
    with open(DATA_DIR / "source_truth.json") as f:
        return json.load(f)


def cmd_max(args, data):
    """Show max theoretical sell price for a crop."""
    result = max_sell_price(args.crop_id, data=data)
    print(f"\n{'=' * 60}")
    print(f"MAX SELL: {result.crop_name}")
    print(f"{'=' * 60}")
    print(f"  Base sell:     {fmt(result.base_sell)} coins")
    print(f"  Max scale:     {result.max_scale}x → {fmt(int(result.scaled_sell))} coins")
    print(f"  Weather:       Frozen (×{result.weather_mult})")
    print(f"  Lunar:         Amberbound (×{result.lunar_mult})")
    print(f"  Combined:      ×{result.combined_mutation_mult / result.colour_mult} additive")
    print(f"  Colour:        Rainbow (×{result.colour_mult})")
    print(f"  Total mut:     ×{result.combined_mutation_mult}")
    print(f"  Sell Boost IV: +{int(result.sell_boost_pct * 100)}%")
    print(f"  Friend bonus:  +{int(result.friend_bonus_pct * 100)}% (5 players)")
    print(f"  {'─' * 40}")
    print(f"  FINAL PRICE:   {fmt(result.final_price)} coins")
    print()


def cmd_compare(args, data):
    """Compare mutation combos for a crop."""
    results = compare_mutations(args.crop_id, data=data)
    crop_name = results[0].crop_name if results else args.crop_id

    print(f"\n{'=' * 70}")
    print(f"MUTATION COMPARISON: {crop_name} (at max scale)")
    print(f"{'=' * 70}")
    print(f"{'Rank':<5} {'Weather':<14} {'Lunar':<14} {'Colour':<10} {'Mult':<8} {'Sell Price':>15}")
    print(f"{'─' * 70}")

    for i, r in enumerate(results, 1):
        w = INTERNAL_TO_DISPLAY.get(r.weather_mutation, r.weather_mutation) if r.weather_mutation else "—"
        l = INTERNAL_TO_DISPLAY.get(r.lunar_mutation, r.lunar_mutation) if r.lunar_mutation else "—"
        c = INTERNAL_TO_DISPLAY.get(r.colour_mutation, r.colour_mutation) if r.colour_mutation else "—"
        print(f" {i:<4} {w:<14} {l:<14} {c:<10} ×{r.combined_mutation_mult:<6} {fmt(r.final_price):>15}")

    print(f"\nNote: Does not include Sell Boost or friend bonus. Add those for true max.")
    print()


def cmd_custom(args, data):
    """Custom calculation with specified parameters."""
    result = calculate_sell_price(
        crop_id=args.crop_id,
        weather_mutation=args.weather,
        lunar_mutation=args.lunar,
        colour_mutation=args.colour,
        at_max_scale=not args.no_scale,
        sell_boost_tier=args.sell_boost,
        friend_count=args.friends,
        data=data,
    )

    print(f"\n{'=' * 60}")
    print(f"CUSTOM CALC: {result.crop_name}")
    print(f"{'=' * 60}")
    print(f"  {result.breakdown.replace(' | ', chr(10) + '  ')}")
    print()


def cmd_top(args, data):
    """Show top N crops by max theoretical sell price."""
    n = args.count
    crops = data["crops"]

    results = []
    for cid in crops:
        try:
            r = max_sell_price(cid, data=data)
            results.append(r)
        except Exception:
            continue

    results.sort(key=lambda r: r.final_price, reverse=True)

    print(f"\n{'=' * 70}")
    print(f"TOP {n} CROPS BY MAX THEORETICAL SELL PRICE")
    print(f"(Frozen + Amberbound + Rainbow + Max Scale + Sell Boost IV + 5 Friends)")
    print(f"{'=' * 70}")
    print(f"{'Rank':<5} {'Crop':<20} {'Base Sell':>12} {'Scale':>6} {'Max Sell':>18}")
    print(f"{'─' * 70}")

    for i, r in enumerate(results[:n], 1):
        print(f" {i:<4} {r.crop_name:<20} {fmt(r.base_sell):>12} {r.max_scale:>5}x {fmt(r.final_price):>18}")
    print()


def cmd_tools(_args, data):
    """Print all available game tools, mutations, and calculator options."""
    mutations = data["mutations"]
    crops = data["crops"]
    tools = data["tools"]

    print(f"\n{'=' * 70}")
    print("MAGIC GARDEN — TOOL & REFERENCE LIST")
    print(f"{'=' * 70}")

    print(f"\n── MUTATIONS ──")
    print(f"{'Name':<16} {'Internal ID':<18} {'Multiplier':>10} {'Base Chance':>12} {'Category':<10}")
    print(f"{'─' * 70}")
    for mid, m in mutations.items():
        display = INTERNAL_TO_DISPLAY.get(mid, m["name"])
        cat = "Weather" if mid in WEATHER_MUTATIONS else "Lunar" if mid in LUNAR_MUTATIONS else "Colour"
        print(f"{display:<16} {mid:<18} ×{m['coinMultiplier']:<9} {m['baseChance'] * 100:>10.1f}% {cat:<10}")

    print(f"\n── STACKING RULES ──")
    print("  1. Weather + Lunar = ADDITIVE      (e.g. ×6 + ×10 = ×16)")
    print("  2. Combined × Colour = MULTIPLICATIVE (e.g. ×16 × ×50 = ×800)")
    print("  3. Size scales linearly             (sell × weight/baseWeight)")
    print("  4. Friend bonus = +10% per player   (max +50% with 5 players)")
    print("  5. Sell Boost = ability bonus        (I=+20%, II=+30%, III=+40%, IV=+50%)")

    print(f"\n── SELL BOOST TIERS ──")
    for tier, pct in SELL_BOOST_TIERS.items():
        print(f"  Sell Boost {tier}: +{int(pct * 100)}%")

    print(f"\n── WEATHER MUTATIONS (pick one) ──")
    for mid in ["Wet", "Chilled", "Frozen", "Thunderstruck"]:
        m = mutations[mid]
        print(f"  {INTERNAL_TO_DISPLAY.get(mid, mid):<16} ×{m['coinMultiplier']}")

    print(f"\n── LUNAR MUTATIONS (pick one) ──")
    for mid in ["Dawnlit", "Ambershine", "Dawncharged", "Ambercharged"]:
        m = mutations[mid]
        print(f"  {INTERNAL_TO_DISPLAY.get(mid, mid):<16} ×{m['coinMultiplier']}")

    print(f"\n── COLOUR MUTATIONS (pick one) ──")
    for mid in ["Gold", "Rainbow"]:
        m = mutations[mid]
        print(f"  {INTERNAL_TO_DISPLAY.get(mid, mid):<16} ×{m['coinMultiplier']}  ({m['baseChance'] * 100}% base chance)")

    print(f"\n── MUTATION TOOLS (potions) ──")
    for tid, t in tools.items():
        if t.get("mutation"):
            display_mut = INTERNAL_TO_DISPLAY.get(t["mutation"], t["mutation"])
            print(f"  {t['name']:<20} applies {display_mut:<14} {t['rarity']}")

    print(f"\n── TOP 5 MUTATION COMBOS ──")
    print("  1. Frozen + Amberbound + Rainbow = ×800")
    print("  2. Thunderstruck + Amberbound + Rainbow = ×750")
    print("  3. Frozen + Dawnbound + Rainbow = ×650")
    print("  4. Frozen + Amberlit + Rainbow = ×600")
    print("  5. Wet + Amberbound + Rainbow = ×600")

    print(f"\n── CROP COUNT ──")
    print(f"  {len(crops)} crops total")
    print(f"  Single-harvest: {sum(1 for c in crops.values() if c['harvestType'] == 'Single')}")
    print(f"  Multi-harvest:  {sum(1 for c in crops.values() if c['harvestType'] == 'Multiple')}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Magic Garden sell price calculator")
    sub = parser.add_subparsers(dest="command")

    # max
    p_max = sub.add_parser("max", help="Max theoretical sell price for a crop")
    p_max.add_argument("crop_id", help="Internal crop ID (e.g. MoonCelestial, Mushroom)")

    # compare
    p_cmp = sub.add_parser("compare", help="Compare mutation combos for a crop")
    p_cmp.add_argument("crop_id", help="Internal crop ID")

    # custom
    p_custom = sub.add_parser("custom", help="Custom calculation")
    p_custom.add_argument("crop_id", help="Internal crop ID")
    p_custom.add_argument("--weather", choices=["Wet", "Chilled", "Frozen", "Thunderstruck"],
                          help="Weather mutation")
    p_custom.add_argument("--lunar", choices=["Dawnlit", "Ambershine", "Dawncharged", "Ambercharged"],
                          help="Lunar mutation")
    p_custom.add_argument("--colour", choices=["Gold", "Rainbow"], help="Colour mutation")
    p_custom.add_argument("--sell-boost", choices=["I", "II", "III", "IV"], help="Sell Boost tier")
    p_custom.add_argument("--friends", type=int, default=0, help="Friend count (0-5)")
    p_custom.add_argument("--no-scale", action="store_true", help="Don't use max scale")

    # top
    p_top = sub.add_parser("top", help="Top N crops by max sell price")
    p_top.add_argument("count", type=int, nargs="?", default=10, help="Number of crops (default: 10)")

    # tools
    sub.add_parser("tools", help="Show all mutations, stacking rules, and reference data")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    data = load_data()
    {"max": cmd_max, "compare": cmd_compare, "custom": cmd_custom,
     "top": cmd_top, "tools": cmd_tools}[args.command](args, data)


if __name__ == "__main__":
    main()
