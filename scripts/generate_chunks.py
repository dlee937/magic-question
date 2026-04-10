#!/usr/bin/env python3
"""
Reads source_truth.json → generates chunk JSON files for indexing.
Run once after data extraction, re-run when game updates.

Usage: python -m scripts.generate_chunks
"""

import json
import math
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.entity_registry import INTERNAL_TO_DISPLAY
from src.calculator import calculate_sell_price

DATA_DIR = PROJECT_ROOT / "data"
SOURCE = DATA_DIR / "source_truth.json"
OUT_DIR = DATA_DIR / "chunks"

# Derived from central registry — no need to duplicate mappings
CROP_DISPLAY = {k: v for k, v in INTERNAL_TO_DISPLAY.items()
                if k[0].isupper() and k not in ("SnowFox", "FireHorse", "WhiteCaribou",
                                                  "Frost", "Ambershine", "Ambercharged",
                                                  "Dawncharged", "AmberMoon")}

PET_DISPLAY = {k: v for k, v in INTERNAL_TO_DISPLAY.items()
               if k in ("SnowFox", "FireHorse", "WhiteCaribou")}


def _get_owned_abilities(data) -> set[str]:
    """Return set of ability IDs that are actually owned by at least one pet."""
    owned = set()
    for pet in data["pets"].values():
        for aid in pet["abilities"]:
            owned.add(aid)
    return owned


def ensure_dirs():
    for sub in ["entities", "relationships", "summaries", "strategies"]:
        (OUT_DIR / sub).mkdir(parents=True, exist_ok=True)


def write_chunk(subdir: str, chunk_id: str, text: str, metadata: dict):
    path = OUT_DIR / subdir / f"{chunk_id}.json"
    path.write_text(json.dumps({"chunk_id": chunk_id, "text": text, "metadata": metadata}, indent=2))


def fmt(n) -> str:
    """Format number with commas."""
    if isinstance(n, float):
        if n == int(n):
            return f"{int(n):,}"
        return f"{n:,.2f}"
    return f"{n:,}"


# ═══════════════════════════════════════════════════════════════
# LAYER 1: Entity Chunks
# ═══════════════════════════════════════════════════════════════

def gen_pet_chunks(data):
    pets, eggs, abilities = data["pets"], data["eggs"], data["abilities"]

    # Build pet→egg reverse map
    pet_to_egg = {}
    for eid, egg in eggs.items():
        for pid, weight in egg["spawns"].items():
            pet_to_egg[pid] = (egg["name"], weight, fmt(egg["coinPrice"]), eid)

    for pid, pet in pets.items():
        egg_name, hatch_pct, egg_price, egg_id = pet_to_egg.get(pid, ("Unknown", 0, "?", "?"))
        pname = PET_DISPLAY.get(pid, pet["name"])

        # Ability lines with weights and params
        ab_lines = []
        for aid, weight in pet["abilities"].items():
            ab = abilities.get(aid, {})
            ab_name = ab.get("name", aid)
            params = ab.get("params", {})
            param_parts = []
            for k, v in params.items():
                if k == "requiredWeather":
                    continue
                param_parts.append(f"{v} {k}")
            param_str = f" — {', '.join(param_parts)}" if param_parts else ""
            ab_lines.append(f"  {ab_name} ({weight}% pool weight){param_str}")

        max_wt = pet["matureWeight"] * pet["maxScale"]
        diet_display = [CROP_DISPLAY.get(c, c) for c in pet["diet"]]

        text = (
            f"[PET] {pname}\n"
            f"Egg: {egg_name} ({hatch_pct}% hatch chance, {egg_price} coins)\n"
            f"Rarity: {pet['rarity']} | Maturity: {pet['hoursToMature']}h | Max Scale: {pet['maxScale']}x\n"
            f"Hunger Cost: {fmt(pet['hunger'])} coins to fill\n"
            f"Base Weight: {pet['matureWeight']} kg | Max Weight: {max_wt} kg\n"
            f"Maturity Sell: {fmt(pet['maturitySellPrice'])} coins\n"
            f"Diet: {', '.join(diet_display)}\n"
            f"Ability Pool (weighted — each slot rolls independently):\n"
            + '\n'.join(ab_lines)
        )

        write_chunk("entities", f"pet_{pid}", text, {
            "entity_type": "pet", "entity_name": pname, "internal_id": pid,
            "rarity_tier": pet["rarity"], "layer": "entity",
        })
    print(f"  {len(pets)} pet chunks")


def gen_crop_chunks(data):
    crops, pets = data["crops"], data["pets"]

    # Reverse diet: crop→[pet names]
    crop_to_pets: dict[str, list[str]] = {}
    for pid, pet in pets.items():
        pname = PET_DISPLAY.get(pid, pet["name"])
        for cid in pet["diet"]:
            crop_to_pets.setdefault(cid, []).append(pname)

    for cid, crop in crops.items():
        display = crop.get("displayName", CROP_DISPLAY.get(cid, cid))
        fed_to = crop_to_pets.get(cid, [])
        max_wt = crop["baseWeight"] * crop["maxScale"]

        if crop["harvestType"] == "Multiple" and crop.get("slots"):
            regrow_s = crop.get("secondsToMature") or 0
            if regrow_s >= 3600:
                regrow_str = f"{regrow_s // 3600}h"
            elif regrow_s >= 60:
                regrow_str = f"{regrow_s // 60}m"
            else:
                regrow_str = f"{regrow_s}s"
            harvest_info = f"Multi-harvest ({crop['slots']} slots, {regrow_str} regrow)"
        else:
            harvest_info = "Single-harvest"

        # Plant abilities (Dawnbinder/Moonbinder)
        mut_display = {"Dawnlit": "Dawnlit", **{k: v for k, v in INTERNAL_TO_DISPLAY.items()
                        if k in ("Ambershine", "Ambercharged", "Dawncharged")}}
        weather_display = {k: v for k, v in INTERNAL_TO_DISPLAY.items()
                           if k in ("AmberMoon", "Frost")}
        weather_display["Dawn"] = "Dawn"
        ability_note = ""
        if crop.get("abilities"):
            for pa_id in crop["abilities"]:
                pa = data.get("plant_abilities", {}).get(pa_id, {})
                if pa:
                    src_mut = mut_display.get(pa.get('sourceMutation', ''), pa.get('sourceMutation', '?'))
                    tgt_mut = mut_display.get(pa.get('targetMutation', ''), pa.get('targetMutation', '?'))
                    weather = weather_display.get(pa.get('requiredWeather', ''), pa.get('requiredWeather', '?'))
                    ability_note = (
                        f"\nPlant Ability: {pa['name']} — during {weather} weather, "
                        f"adjacent {src_mut} crops have {pa['mutationChancePerMinute']}%/min "
                        f"chance to upgrade to {tgt_mut}"
                    )

        text = (
            f"[CROP] {display}\n"
            f"Type: {harvest_info}\n"
            f"Seed Price: {fmt(crop['seedPrice'])} coins | Base Sell: {fmt(crop['sellPrice'])} coins\n"
            f"Base Weight: {crop['baseWeight']} kg | Max Weight: {max_wt} kg ({crop['maxScale']}x scale)\n"
            f"Fed to: {', '.join(fed_to) if fed_to else 'No pets (sell only)'}"
            f"{ability_note}"
        )

        write_chunk("entities", f"crop_{cid}", text, {
            "entity_type": "crop", "entity_name": display, "internal_id": cid,
            "harvest_type": crop["harvestType"], "layer": "entity",
        })
    print(f"  {len(crops)} crop chunks")


def gen_ability_chunks(data):
    abilities = data["abilities"]
    pets = data["pets"]

    # Build ability→pet reverse map
    ability_to_pets: dict[str, list[tuple[str, int]]] = {}
    for pid, pet in pets.items():
        pname = PET_DISPLAY.get(pid, pet["name"])
        for aid, weight in pet["abilities"].items():
            ability_to_pets.setdefault(aid, []).append((pname, weight))

    owned = _get_owned_abilities(data)
    count = 0

    for aid, ab in abilities.items():
        # Skip unimplemented abilities (no pet owns them)
        if aid not in owned:
            continue

        owners = ability_to_pets.get(aid, [])
        owner_str = ", ".join(f"{name} ({w}%)" for name, w in owners)

        # Format params with human-readable names
        param_readable = {
            "baseMaxCoinsFindable": "max coins findable",
            "plantGrowthReductionMinutes": "growth time reduction (minutes)",
            "cropSellPriceIncreasePercentage": "sell price increase %",
            "scaleIncreasePercentage": "scale increase %",
            "mutationChanceIncreasePercentage": "mutation chance increase %",
            "eggGrowthTimeReductionMinutes": "egg hatch time reduction (minutes)",
            "bonusXp": "bonus XP",
            "hungerDepletionRateDecreasePercentage": "hunger depletion decrease %",
            "hungerRestorePercentage": "hunger restore %",
            "mutationChanceIncreasePercentage": "mutation chance increase %",
            "cropSellPriceIncreasePercentage": "sell price increase %",
            "maxStrengthIncreasePercentage": "max strength increase %",
        }
        param_lines = []
        weather_req = None
        for k, v in ab.get("params", {}).items():
            if k == "requiredWeather":
                weather_req = v
                continue
            if k == "grantedMutations":
                mut_names = [{"Wet": "Wet", "Chilled": "Chilled", "Frozen": "Frozen",
                              "Dawnlit": "Dawnlit", "Ambershine": "Amberlit",
                              "Gold": "Gold", "Rainbow": "Rainbow"}.get(m, m) for m in v]
                param_lines.append(f"  grants: {', '.join(mut_names)}")
                continue
            readable = param_readable.get(k, k)
            param_lines.append(f"  {readable}: {v}")

        prob = ab.get("baseProbability")
        prob_str = f"{prob}% × STR" if prob is not None else "passive (always active)"

        text = (
            f"[ABILITY] {ab['name']}\n"
            f"Internal ID: {aid}\n"
            f"Trigger: {ab['trigger']} | Probability: {prob_str}\n"
        )
        if param_lines:
            text += "Effect:\n" + "\n".join(param_lines) + "\n"
        if weather_req:
            weather_names = {k: v for k, v in INTERNAL_TO_DISPLAY.items()
                                if k in ("Frost", "AmberMoon")}
            text += f"Requires weather: {weather_names.get(weather_req, weather_req)}\n"
        text += f"Owned by: {owner_str}"

        write_chunk("entities", f"ability_{aid}", text, {
            "entity_type": "ability", "entity_name": ab["name"],
            "internal_id": aid, "ability_trigger": ab["trigger"], "layer": "entity",
        })
        count += 1
    print(f"  {count} ability chunks ({len(abilities) - count} unimplemented skipped)")


def gen_mutation_chunks(data):
    for mid, mut in data["mutations"].items():
        display = mut["name"]
        text = (
            f"[MUTATION] {display}\n"
            f"Internal ID: {mid}\n"
            f"Sell Multiplier: ×{mut['coinMultiplier']}\n"
            f"Base chance on planting: {mut['baseChance'] * 100}%"
        )
        write_chunk("entities", f"mutation_{mid}", text, {
            "entity_type": "mutation", "entity_name": display,
            "internal_id": mid, "layer": "entity",
        })
    print(f"  {len(data['mutations'])} mutation chunks")


def gen_weather_chunks(data):
    for wid, w in data["weather_events"].items():
        text = (
            f"[WEATHER] {w['name']}\n"
            f"Internal ID: {wid} | Group: {w['groupId']}\n"
            f"Mutation applied: {w['mutation']} at {w['chancePerMinutePerCrop']}% per minute per mature crop\n"
        )
        if w["groupId"] == "Hydro":
            text += "Frequency: Regular (every 20-30 min, lasts 5 min)"
        else:
            text += "Frequency: Lunar (every 4 hours, lasts 10 min)"
        write_chunk("entities", f"weather_{wid}", text, {
            "entity_type": "weather", "entity_name": w["name"],
            "internal_id": wid, "layer": "entity",
        })
    print(f"  {len(data['weather_events'])} weather chunks")


def gen_egg_chunks(data):
    eggs = data["eggs"]
    pets = data["pets"]
    for eid, egg in eggs.items():
        spawn_lines = []
        for pid, pct in egg["spawns"].items():
            pname = PET_DISPLAY.get(pid, pets.get(pid, {}).get("name", pid))
            spawn_lines.append(f"  {pname}: {pct}%")

        hatch_s = egg["secondsToHatch"]
        hatch_str = f"{hatch_s // 60} min" if hatch_s < 3600 else f"{hatch_s // 3600} hours"

        req = ""
        if egg.get("requiredWeather"):
            weather_display = {k: v for k, v in INTERNAL_TO_DISPLAY.items()
                                if k in ("Frost", "AmberMoon")}
            wname = weather_display.get(egg["requiredWeather"], egg["requiredWeather"])
            req = f"\nRequires: Active {wname} weather to purchase"

        text = (
            f"[EGG] {egg['name']}\n"
            f"Internal ID: {eid}\n"
            f"Price: {fmt(egg['coinPrice'])} coins ({egg['creditPrice']} credits)\n"
            f"Rarity: {egg['rarity']} | Hatch Time: {hatch_str}\n"
            f"Spawns:\n" + "\n".join(spawn_lines)
            + req
        )
        write_chunk("entities", f"egg_{eid}", text, {
            "entity_type": "egg", "entity_name": egg["name"],
            "internal_id": eid, "layer": "entity",
        })
    print(f"  {len(eggs)} egg chunks")


def gen_tool_chunks(data):
    for tid, tool in data["tools"].items():
        price_str = fmt(tool["coinPrice"])
        if tool["coinPrice"] > 1_000_000_000:
            price_str += " (effectively unpurchasable — Carnival Stand only)"

        cp = tool.get("creditPrice")
        credit_str = str(cp) if cp is not None else "N/A"

        text = (
            f"[TOOL] {tool['name']}\n"
            f"Internal ID: {tid}\n"
            f"Price: {price_str} coins ({credit_str} credits)\n"
            f"Rarity: {tool['rarity']} | One-time use: {'Yes' if tool.get('oneTime') else 'No'}"
        )
        if tool.get("mutation"):
            text += f"\nApplies mutation: {tool['mutation']}"

        write_chunk("entities", f"tool_{tid}", text, {
            "entity_type": "tool", "entity_name": tool["name"],
            "internal_id": tid, "layer": "entity",
        })
    print(f"  {len(data['tools'])} tool chunks")


def gen_constants_chunk(data):
    c = data["constants"]
    restocks = c["shopRestocks"]
    text = (
        f"[SYSTEM] Game Constants\n"
        f"Active pet slots: {c['petSlotsActive']}\n"
        f"Main inventory: {c['maxInventorySlots']} slots\n"
        f"Pet Hutch: {c['petHutchCapacity']} | Decor Shed: {c['decorShedCapacity']} | "
        f"Seed Silo: {c['seedSiloCapacity']} | Feeding Trough: {c['feedingTroughCapacity']}\n"
        f"Strength: {c['minStrength']} (base) to {c['maxStrength']} (max), range {c['strengthRange']}\n"
        f"XP: {c['xpPerHour']} per hour of maturity\n"
        f"Friend bonus: +{c['friendBonusPerPlayer'] * 100:.0f}% sell price per additional player\n"
        f"Insta-grow: ~{c['instaGrowCostPerSecond']:.4f} credits/sec\n"
        f"Shop restocks: Seed {restocks['seed']['intervalSeconds']}s, "
        f"Egg {restocks['egg']['intervalSeconds']}s, "
        f"Tool {restocks['tool']['intervalSeconds']}s, "
        f"Decor {restocks['decor']['intervalSeconds']}s"
    )
    write_chunk("entities", "constants", text, {
        "entity_type": "constant", "entity_name": "Game Constants", "layer": "entity",
    })
    print("  1 constants chunk")


# ═══════════════════════════════════════════════════════════════
# LAYER 2: Relationship Chunks
# ═══════════════════════════════════════════════════════════════

def gen_diet_chains(data):
    pets, crops = data["pets"], data["crops"]
    count = 0
    for pid, pet in pets.items():
        pname = PET_DISPLAY.get(pid, pet["name"])
        lines = [f"[DIET CHAIN] {pname}"]
        lines.append(f"{pname} hunger cost: {fmt(pet['hunger'])} coins to fill")
        lines.append(f"{pname} eats:")

        best_sell = ("", 0)
        cheapest_seed = ("", float('inf'))

        for cid in pet["diet"]:
            crop = crops.get(cid, {})
            display = crop.get("displayName", CROP_DISPLAY.get(cid, cid))
            sell = crop.get("sellPrice", 0)
            seed = crop.get("seedPrice", 0)

            if crop.get("harvestType") == "Multiple" and crop.get("slots"):
                harvest = f"multi {crop['slots']} slots"
            else:
                harvest = "single"
            lines.append(f"  {display}: {fmt(seed)} seed, {fmt(sell)} sell, {harvest}")

            if sell > best_sell[1]:
                best_sell = (display, sell)
            if seed < cheapest_seed[1]:
                cheapest_seed = (display, seed)

        if best_sell[0]:
            lines.append(f"Best hunger restore: {best_sell[0]} ({fmt(best_sell[1])} sell value)")
        if cheapest_seed[0]:
            lines.append(f"Cheapest option: {cheapest_seed[0]} ({fmt(int(cheapest_seed[1]))} seed)")

        write_chunk("relationships", f"diet_{pid}", "\n".join(lines), {
            "entity_type": "pet", "entity_name": pname,
            "query_intents": "diet", "layer": "relationship",
        })
        count += 1
    print(f"  {count} diet chain chunks")


def gen_crop_feeders(data):
    pets, crops = data["pets"], data["crops"]
    crop_to_pets: dict[str, list[str]] = {}
    for pid, pet in pets.items():
        pname = PET_DISPLAY.get(pid, pet["name"])
        for cid in pet["diet"]:
            crop_to_pets.setdefault(cid, []).append(pname)

    count = 0
    for cid, pet_names in crop_to_pets.items():
        crop = crops.get(cid, {})
        display = crop.get("displayName", CROP_DISPLAY.get(cid, cid))
        text = (
            f"[CROP FEEDERS] {display}\n"
            f"{display} is eaten by: {', '.join(pet_names)}\n"
            f"Seed: {fmt(crop.get('seedPrice', 0))} | Sell: {fmt(crop.get('sellPrice', 0))} | "
            f"Weight: {crop.get('baseWeight', 0)} kg (max {crop.get('baseWeight', 0) * crop.get('maxScale', 1)} kg)"
        )
        write_chunk("relationships", f"feeders_{cid}", text, {
            "entity_type": "crop", "entity_name": display,
            "query_intents": "diet", "layer": "relationship",
        })
        count += 1
    print(f"  {count} crop feeder chunks")


def gen_weather_combos(data):
    combos = [
        ("frozen_path", "[WEATHER COMBO] Frozen mutation path",
         "Step 1: Rain → Wet (×2) at 7%/min per crop\n"
         "Step 2: Snow → Wet crops upgrade to Frozen (×6) at 7%/min\n"
         "Alt: Turkey (Rain Granter 10%/min) + Snow Fox/Stoat (Snow Granter 8%/min)\n"
         "Alt: Caribou (Frost Granter 6%/min) — applies Frozen directly\n"
         "Alt: Frozen Potion (Carnival Stand only)\n"
         "Cannot combine: Frozen is exclusive with Thunderstruck"),
        ("dawnbound_path", "[WEATHER COMBO] Dawnbound mutation path",
         "Step 1: Plant a Dawnbinder crop (Celestial, 10B seed cost)\n"
         "Step 2: Wait for Dawn weather (67% chance every 4 hours, lasts 10 min)\n"
         "Step 3: Mature crops get Dawnlit (×4) at 1%/min\n"
         "Step 4: Dawnlit crops adjacent to Dawnbinder upgrade to Dawnbound (×7) at 25%/min\n"
         "Alt: Horse's Dawnlit Granter (4%/min) can apply Dawnlit without weather"),
        ("amberbound_path", "[WEATHER COMBO] Amberbound mutation path",
         "Step 1: Plant a Moonbinder crop (Celestial, 50B seed cost)\n"
         "Step 2: Wait for Amber Moon weather (33% chance every 4 hours, lasts 10 min)\n"
         "Step 3: Mature crops get Amberlit (×6) at 1%/min\n"
         "Step 4: Amberlit crops adjacent to Moonbinder upgrade to Amberbound (×10) at 25%/min\n"
         "Alt: Fire Horse's Amberlit Granter (2%/min) applies Amberlit without weather"),
        ("gold_rainbow_path", "[WEATHER COMBO] Gold and Rainbow mutations",
         "Gold: 1% base chance when planting any crop. Multiplier: ×25\n"
         "Rainbow: 0.1% base chance when planting any crop. Multiplier: ×50\n"
         "Alt: Gold Granter pet ability (0.72%/min × STR)\n"
         "Alt: Rainbow Granter pet ability (0.72%/min × STR)\n"
         "Alt: Gold/Rainbow Potion (Carnival Stand only)\n"
         "Gold and Rainbow are mutually exclusive — a crop can only have one"),
    ]

    for chunk_id, title, body in combos:
        text = f"{title}\n{body}"
        write_chunk("relationships", chunk_id, text, {
            "entity_type": "mutation", "query_intents": "mutation",
            "layer": "relationship",
        })
    print(f"  {len(combos)} weather combo chunks")


def gen_multiplier_guide(data):
    text = """[MULTIPLIER GUIDE] Sell value stacking rules
RULE 1: Weather + Lunar mutations stack ADDITIVELY
  Frozen (×6) + Amberbound (×10) = ×16
  Thunderstruck (×5) + Amberbound (×10) = ×15
  Frozen (×6) + Dawnbound (×7) = ×13
  Wet (×2) + Amberbound (×10) = ×12

RULE 2: (Weather+Lunar) × Colour = MULTIPLICATIVE
  ×16 × Rainbow (×50) = ×800 (maximum possible)
  ×16 × Gold (×25) = ×400
  ×13 × Rainbow (×50) = ×650

RULE 3: Size scales sell price linearly
  Sell = baseSell × (currentWeight / baseWeight)

RULE 4: Friend bonus is additive (+10% per player, max +50%)

Top 5 combos:
1. Frozen + Amberbound + Rainbow = ×800
2. Thunderstruck + Amberbound + Rainbow = ×750
3. Frozen + Dawnbound + Rainbow = ×650
4. Frozen + Amberlit + Rainbow = ×600
5. Wet + Amberbound + Rainbow = ×600"""

    write_chunk("relationships", "multiplier_guide", text, {
        "entity_type": "mutation", "query_intents": "multipliers",
        "layer": "relationship",
    })
    print("  1 multiplier guide chunk")


def gen_snow_egg_comparison(data):
    text = """[COMPARISON] Snow Egg vs Winter Egg
Both hatch the same pets: Snow Fox (75%), Stoat (20%), Caribou (5%)

Snow Egg: 200,000,000 coins / 269 credits
  Requires active Snow weather to purchase. Available permanently but weather-gated.

Winter Egg: 80,000,000 coins / 199 credits
  No weather requirement. Seasonal availability (limited time).

Strategy: Winter Egg is 60% cheaper and easier to obtain during winter events.
Snow Egg costs more but is technically always available when Snow weather is active."""

    write_chunk("relationships", "snow_vs_winter_egg", text, {
        "entity_type": "egg", "query_intents": "comparison",
        "layer": "relationship",
    })
    print("  1 egg comparison chunk")


def gen_ability_families(data):
    """Group abilities into tier families (I→II→III + weather variants).
    This is critical for 'what are the sell boost tiers' type queries."""
    abilities = data["abilities"]
    pets = data["pets"]

    # Build ability→pet reverse map
    ability_to_pets: dict[str, list[tuple[str, int]]] = {}
    for pid, pet in pets.items():
        pname = PET_DISPLAY.get(pid, pet["name"])
        for aid, weight in pet["abilities"].items():
            ability_to_pets.setdefault(aid, []).append((pname, weight))

    # Define families manually since naming is inconsistent in source
    families = [
        {
            "name": "Sell Boost",
            "members": ["SellBoostI", "SellBoostII", "SellBoostIII", "SellBoostIV"],
            "intent": "selling",
            "desc": "Chance to increase sell price when selling crops",
        },
        {
            "name": "Coin Finder",
            "members": ["CoinFinderI", "CoinFinderII", "CoinFinderIII", "SnowyCoinFinder"],
            "intent": "selling",
            "desc": "Passive coin generation while pet is active",
        },
        {
            "name": "Seed Finder",
            "members": ["SeedFinderI", "SeedFinderII", "SeedFinderIII", "SeedFinderIV"],
            "intent": "growing",
            "desc": "Find free seeds in garden. Higher tiers find rarer seeds",
        },
        {
            "name": "Plant Growth Boost",
            "members": ["PlantGrowthBoostI", "PlantGrowthBoostII", "PlantGrowthBoostIII",
                        "SnowyPlantGrowthBoost", "DawnPlantGrowthBoost", "AmberPlantGrowthBoost"],
            "intent": "growing",
            "desc": "Reduces crop grow time. Weather variants only active during specific weather",
        },
        {
            "name": "Egg Growth Boost",
            "members": ["EggGrowthBoostI", "EggGrowthBoostII_NEW", "EggGrowthBoostII",
                        "SnowyEggGrowthBoost"],
            "intent": "hatching",
            "desc": "Reduces egg hatch time. Internal naming: II_NEW=display II, II=display III",
        },
        {
            "name": "Weather Mutation Boost",
            "members": ["ProduceMutationBoost", "ProduceMutationBoostII", "ProduceMutationBoostIII",
                        "SnowBoost", "DawnBoost", "AmberMoonBoost"],
            "intent": "mutation",
            "desc": "Increases chance of weather mutations on garden crops. STR scaling",
        },
        {
            "name": "Crop Size Boost",
            "members": ["ProduceScaleBoost", "ProduceScaleBoostII", "ProduceScaleBoostIII"],
            "intent": "growing",
            "desc": "Increases crop scale/weight over time. Bigger crops sell for more",
        },
        {
            "name": "Hunger Management",
            "members": ["HungerBoostI", "HungerBoostII", "HungerBoostIII",
                        "HungerRestoreI", "HungerRestoreII", "HungerRestoreIII",
                        "SnowyHungerBoost", "SnowyHungerRestore"],
            "intent": "diet",
            "desc": "Hunger Boost slows depletion rate; Hunger Restore refills hunger periodically",
        },
        {
            "name": "XP and Hatch Bonuses",
            "members": ["PetXpBoostI", "PetXpBoostII", "PetXpBoostIII",
                        "PetAgeBoostI", "PetAgeBoostII", "PetAgeBoostIII",
                        "PetHatchSizeBoostI", "PetHatchSizeBoostII", "PetHatchSizeBoostIII",
                        "SnowyPetXpBoost"],
            "intent": "hatching",
            "desc": "XP Boost adds XP on egg hatch. Hatch XP Boost ages pet on hatch. Max Strength increases STR cap",
        },
        {
            "name": "Mutation Granters",
            "members": ["RainDance", "SnowGranter", "FrostGranter",
                        "DawnlitGranter", "AmberlitGranter",
                        "GoldGranter", "RainbowGranter"],
            "intent": "mutation",
            "desc": "Apply mutations directly to crops without waiting for weather events",
        },
        {
            "name": "Harvest and Refund",
            "members": ["DoubleHarvest", "ProduceRefund", "ProduceEater",
                        "PetRefundI", "PetRefundII", "DoubleHatch"],
            "intent": "selling",
            "desc": "Double Harvest = 2x crop yield. Crop Refund = refund seed cost. "
                     "Pet Refund = partial refund selling pets. Double Hatch = chance for 2 pets from 1 egg",
        },
    ]

    owned = _get_owned_abilities(data)
    count = 0
    for family in families:
        lines = [f"[ABILITY FAMILY] {family['name']}", f"{family['desc']}", ""]

        for aid in family["members"]:
            ab = abilities.get(aid)
            if not ab:
                continue
            # Skip unimplemented abilities
            if aid not in owned:
                continue
            owners = ability_to_pets.get(aid, [])
            owner_str = ", ".join(f"{name} ({w}%)" for name, w in owners)

            # Key param
            params = ab.get("params", {})
            weather_req = params.get("requiredWeather")
            weather_names = {k: v for k, v in INTERNAL_TO_DISPLAY.items()
                                if k in ("Frost", "AmberMoon")}
            weather_str = f" [requires {weather_names.get(weather_req, weather_req)} weather]" if weather_req else ""

            param_val = ""
            param_readable = {
                "cropSellPriceIncreasePercentage": "sell price increase",
                "baseMaxCoinsFindable": "max coins findable",
                "plantGrowthReductionMinutes": "min growth reduction",
                "scaleIncreasePercentage": "scale increase",
                "mutationChanceIncreasePercentage": "mutation chance increase",
                "eggGrowthTimeReductionMinutes": "min hatch time reduction",
                "bonusXp": "bonus XP",
                "hungerDepletionRateDecreasePercentage": "hunger depletion decrease",
                "hungerRestorePercentage": "hunger restore",
                "maxStrengthIncreasePercentage": "max STR increase",
                "basePetAgeXp": "maturity XP on hatch",
                "petHatchSizeIncreasePercentage": "hatch size increase",
            }
            for k, v in params.items():
                if k in ("requiredWeather", "grantedMutations"):
                    continue
                label = param_readable.get(k, k)
                suffix = "%" if "ercentage" in k else ""
                param_val = f" — {v}{suffix} {label}"
                break

            prob = ab.get("baseProbability")
            prob_str = f"{prob}%×STR" if prob is not None else "passive"

            lines.append(f"  {ab['name']} ({prob_str}){param_val}{weather_str}")
            lines.append(f"    Owned by: {owner_str}")

        text = "\n".join(lines)
        chunk_id = f"family_{family['name'].lower().replace(' ', '_')}"
        write_chunk("relationships", chunk_id, text, {
            "entity_type": "ability", "query_intents": family["intent"],
            "layer": "relationship",
        })
        count += 1
    print(f"  {count} ability family chunks")


# ═══════════════════════════════════════════════════════════════
# LAYER 3: Summary Chunks
# ═══════════════════════════════════════════════════════════════

def gen_pets_by_egg_summary(data):
    eggs, pets, abilities = data["eggs"], data["pets"], data["abilities"]
    lines = ["[SUMMARY] All pets by egg type"]
    for eid, egg in eggs.items():
        hatch_s = egg["secondsToHatch"]
        hatch_str = f"{hatch_s // 60}min" if hatch_s < 3600 else f"{hatch_s // 3600}h"
        lines.append(f"\n{egg['name']} ({fmt(egg['coinPrice'])} coins, {hatch_str} hatch):")
        for pid, pct in egg["spawns"].items():
            pet = pets[pid]
            pname = PET_DISPLAY.get(pid, pet["name"])
            ab_names = [abilities.get(a, {}).get("name", a) for a in pet["abilities"]]
            lines.append(f"  {pname} {pct}% — abilities: {', '.join(ab_names)}")

    write_chunk("summaries", "pets_by_egg", "\n".join(lines), {
        "entity_type": "pet", "query_intents": "hatching", "layer": "summary",
    })
    print("  1 pets-by-egg summary")


def gen_crops_by_rarity_summary(data):
    crops = data["crops"]
    tiers: dict[str, list[tuple[str, int]]] = {}

    # Assign rarity tiers based on seed price (matching source code tiers)
    price_tiers = [
        (1_000, "Common"), (10_000, "Uncommon"), (100_000, "Rare"),
        (1_000_000, "Legendary"), (100_000_000, "Mythical"),
        (1_000_000_000, "Divine"), (float('inf'), "Celestial"),
    ]
    for cid, crop in crops.items():
        display = crop.get("displayName", CROP_DISPLAY.get(cid, cid))
        price = crop["seedPrice"]
        tier = "Celestial"
        for threshold, name in price_tiers:
            if price < threshold:
                tier = name
                break
        tiers.setdefault(tier, []).append((display, price))

    lines = ["[SUMMARY] Crops by rarity tier"]
    for tier in ["Common", "Uncommon", "Rare", "Legendary", "Mythical", "Divine", "Celestial"]:
        if tier in tiers:
            items = sorted(tiers[tier], key=lambda x: x[1])
            crops_str = ", ".join(f"{n} ({fmt(p)})" for n, p in items)
            lines.append(f"{tier} ({len(items)}): {crops_str}")

    write_chunk("summaries", "crops_by_rarity", "\n".join(lines), {
        "entity_type": "crop", "layer": "summary",
    })
    print("  1 crops-by-rarity summary")


def gen_cheapest_pets_summary(data):
    pets = data["pets"]
    sorted_pets = sorted(pets.items(), key=lambda x: x[1]["hunger"])
    lines = ["[SUMMARY] Pets ranked by hunger cost (cheapest to most expensive)"]
    for pid, pet in sorted_pets:
        pname = PET_DISPLAY.get(pid, pet["name"])
        lines.append(f"  {pname}: {fmt(pet['hunger'])} coins to fill ({pet['rarity']})")

    write_chunk("summaries", "pets_by_hunger", "\n".join(lines), {
        "entity_type": "pet", "query_intents": "diet", "layer": "summary",
    })
    print("  1 pets-by-hunger summary")


def gen_best_sell_crops_summary(data):
    crops = data["crops"]
    # Only single-harvest for pure sell value comparison
    singles = [(cid, c) for cid, c in crops.items() if c["harvestType"] == "Single"]
    singles.sort(key=lambda x: x[1]["sellPrice"], reverse=True)

    lines = ["[SUMMARY] Highest sell value single-harvest crops"]
    for cid, crop in singles[:15]:
        display = crop.get("displayName", CROP_DISPLAY.get(cid, cid))
        max_sell = crop["sellPrice"] * crop["maxScale"]
        lines.append(f"  {display}: {fmt(crop['sellPrice'])} base, {fmt(int(max_sell))} at max scale ({crop['maxScale']}x)")

    write_chunk("summaries", "best_sell_crops", "\n".join(lines), {
        "entity_type": "crop", "query_intents": "selling", "layer": "summary",
    })
    print("  1 best-sell-crops summary")


def gen_harvest_comparison_summary(data):
    crops = data["crops"]
    singles = [(cid, c) for cid, c in crops.items() if c["harvestType"] == "Single"]
    multis = [(cid, c) for cid, c in crops.items() if c["harvestType"] == "Multiple"]

    lines = ["[SUMMARY] Single-harvest vs multi-harvest crop comparison"]
    lines.append(f"\nSingle-harvest ({len(singles)} crops): One crop per plant, then replant.")
    lines.append("  Pros: Higher sell value per crop, better for pet feeding (hunger = sell value)")
    lines.append("  Cons: Must rebuy seeds each time")
    top_singles = sorted(singles, key=lambda x: x[1]["sellPrice"], reverse=True)[:5]
    for cid, c in top_singles:
        display = c.get("displayName", CROP_DISPLAY.get(cid, cid))
        lines.append(f"  Top: {display} ({fmt(c['sellPrice'])} sell)")

    lines.append(f"\nMulti-harvest ({len(multis)} crops): Regrows after harvesting, multiple slots.")
    lines.append("  Pros: Infinite harvests from one seed, more Sell Boost procs")
    lines.append("  Cons: Lower per-crop value, slower for mutations")
    top_multis = sorted(multis, key=lambda x: x[1].get("slots", 0), reverse=True)[:5]
    for cid, c in top_multis:
        display = c.get("displayName", CROP_DISPLAY.get(cid, cid))
        lines.append(f"  Top: {display} ({c.get('slots', '?')} slots, {fmt(c['sellPrice'])} sell)")

    write_chunk("summaries", "harvest_comparison", "\n".join(lines), {
        "entity_type": "crop", "query_intents": "growing", "layer": "summary",
    })
    print("  1 harvest-comparison summary")


def gen_pet_abilities_overview(data):
    """Summary of which pets have which ability categories."""
    pets = data["pets"]
    abilities = data["abilities"]

    lines = ["[SUMMARY] Pet ability categories overview"]
    lines.append("Which pets can do what (most common ability by pool weight):\n")

    categories = {
        "Coin finding": [], "Selling boost": [], "Seed finding": [],
        "Crop mutation": [], "Crop growth": [], "Egg hatching": [],
        "Hunger management": [], "Weather granting": [],
        "Harvesting": [], "Other": [],
    }

    cat_keywords = {
        "Coin": "Coin finding", "Sell": "Selling boost", "Seed": "Seed finding",
        "Mutation Boost": "Crop mutation", "Scale Boost": "Crop mutation",
        "Plant Growth": "Crop growth", "Egg Growth": "Egg hatching",
        "Hunger": "Hunger management", "Granter": "Weather granting",
        "Dance": "Weather granting", "Harvest": "Harvesting",
        "Refund": "Other", "Hatch": "Egg hatching",
        "Eater": "Harvesting", "Copycat": "Other",
        "XP": "Other", "Strength": "Other", "Age": "Other",
    }

    for pid, pet in pets.items():
        pname = PET_DISPLAY.get(pid, pet["name"])
        # Find dominant ability (highest weight)
        if not pet["abilities"]:
            continue
        top_aid = max(pet["abilities"], key=lambda a: pet["abilities"][a])
        top_ab = abilities.get(top_aid, {})
        ab_name = top_ab.get("name", top_aid)

        cat = "Other"
        for keyword, category in cat_keywords.items():
            if keyword in ab_name:
                cat = category
                break
        categories[cat].append(f"{pname} ({ab_name} {pet['abilities'][top_aid]}%)")

    for cat, pets_list in categories.items():
        if pets_list:
            lines.append(f"  {cat}: {', '.join(pets_list)}")

    write_chunk("summaries", "pet_abilities_overview", "\n".join(lines), {
        "entity_type": "pet", "query_intents": "abilities", "layer": "summary",
    })
    print("  1 pet-abilities-overview summary")


# ═══════════════════════════════════════════════════════════════
# LAYER 4: Strategy Chunks
# ═══════════════════════════════════════════════════════════════

def gen_strategy_chunks(data):
    strategies = [
        ("strat_early_game", """[STRATEGY] Early game progression (new player)
1. Plant free Carrot seed → sell for 20 coins
2. Buy Common Egg (100,000 coins) → likely Worm (60%)
   Worm has Seed Finder I (50%) + Crop Eater (50%)
3. Crop Eater auto-sells non-mutated crops at 150% × STR bonus
   Seed Finder I gives free common/uncommon seeds
4. Buy Strawberry (50 coins) / Blueberry (400 coins) seeds to feed Worm
5. Save for Uncommon Egg (1,000,000 coins) → Chicken (65%)
   Chicken has Egg Growth I (80%) + Pet Refund I (20%)
6. Chicken speeds egg hatching by 7 min × STR per proc
7. Target: Bunny (25%) for Coin Finder II (60%) + Sell Boost I (40%)
8. You have 3 active pet slots — run Worm + Chicken + Bunny early"""),

        ("strat_income", """[STRATEGY] Maximizing coin income
Income pets (pick 1-2 for 3 active slots):
  Squirrel: Coin Finder III (70%) — finds up to 10,000,000 × STR coins
  Peacock: Sell Boost IV (40%) — 16% chance of +50% sell bonus
  Pony: Coin Finder III (25%) + Sell Boost III (25%) — jack of all trades

Mutation stacking for max crop value:
  1. Grow high-value single-harvest: Mushroom (160K), Cactus (261K), Bamboo (500K), Violet Cort (600K)
  2. Get Frozen: Rain→Snow combo, or Caribou (Frost Granter 6%/min)
  3. Get Amberbound: plant Moonbinder adjacent, wait for Amber Moon
  4. Get Rainbow: 0.1% base, or Rainbow Granter pet at 0.72%/min
  5. Sell with Sell Boost active

Max theoretical single crop sale:
  Frozen (×6) + Amberbound (×10) + Rainbow (×50) = ×800
  Violet Cort at max scale: 600,000 × 800 × 3.5 = 1,680,000,000 coins"""),

        ("strat_loadouts", """[STRATEGY] Optimal 3-pet loadouts by game stage
Early: Worm (seeds + auto-sell) + Snail (coin finding) + Chicken (egg speed + pet refund)
Mid: Turkey (rain + egg speed + double hatch) + Cow (seeds + hunger + growth) + Bunny (coins + sell boost)
Late: Butterfly (mutation + size + seeds) + Squirrel (coins + sell + pet mutation) + Turtle (hunger + growth + eggs)
Winter: Snow Fox + Stoat + Caribou (full snowy ability suite — massive boost during Snow weather)
Horse: Horse (dawn boost + dawnlit granting) + Fire Horse (amber boost + amberlit granting) + Turtle (support)
Max income: Squirrel + Peacock + Pony (triple coin finding + sell boost stacking)"""),

        ("strat_journal", """[STRATEGY] Garden Journal completion guide
Crop variants: 44 crops × up to 12 journal entries each
  Entries include: Normal, Wet, Chilled, Frozen, Dawnlit, Amberlit, Thunderstruck,
  Gold, Rainbow, Dawnbound, Amberbound, Max Weight
  Max Weight is NOT a mutation — it's a size achievement (max scale at STR 100)

Pet variants: 21 pets × 4 entries each = 84 entries
  Entries: Normal, Gold, Rainbow, Max Weight

Tips:
  - Planter Pot (25K coins) logs crop variant without harvesting
  - Cheapest mutation path: Rain (Wet) → Snow (Frozen) covers 3 weather variants at once
  - Dawnlit/Amberlit from pet granters: Horse/Fire Horse are most reliable
  - Gold/Rainbow: 1% / 0.1% base chance on planting, or use granter pets
  - Max Weight pets need STR 100 (full XP maturity + max scale from Crop Size Boost)
  - Hardest: Celestial crop variants (1B+ seed cost), Capybara mutations (5% hatch × ability RNG)"""),
    ]

    for chunk_id, text in strategies:
        write_chunk("strategies", chunk_id, text, {
            "entity_type": "strategy", "query_intents": "strategy", "layer": "strategy",
        })
    print(f"  {len(strategies)} strategy chunks")


# ═══════════════════════════════════════════════════════════════
# LAYER 5: Pre-computed Price Cards
# ═══════════════════════════════════════════════════════════════

def _calc(crop_id, weather=None, lunar=None, colour=None, data=None):
    """Shorthand for calculate_sell_price with max scale, no bonuses."""
    return calculate_sell_price(
        crop_id=crop_id, weather_mutation=weather, lunar_mutation=lunar,
        colour_mutation=colour, at_max_scale=True, data=data,
    )


def gen_price_cards(data):
    """One chunk per crop with all mutation sell price combos pre-computed."""
    crops = data["crops"]
    count = 0

    for cid, crop in crops.items():
        display = crop.get("displayName", CROP_DISPLAY.get(cid, cid))
        base = crop["sellPrice"]
        scale = crop["maxScale"]
        scaled = int(base * scale)

        # Pre-compute key mutation combos
        combos = [
            (None,             None,            None,      "No mutation"),
            ("Wet",            None,            None,      "Wet"),
            ("Frozen",         None,            None,      "Frozen"),
            ("Thunderstruck",  None,            None,      "Thunderstruck"),
            (None,             "Dawncharged",   None,      "Dawnbound"),
            (None,             "Ambercharged",  None,      "Amberbound"),
            ("Frozen",         "Ambercharged",  None,      "Frozen + Amberbound"),
            (None,             None,            "Gold",    "Gold"),
            (None,             None,            "Rainbow", "Rainbow"),
            ("Frozen",         "Ambercharged",  "Gold",    "Frozen + Amberbound + Gold"),
            ("Frozen",         "Ambercharged",  "Rainbow", "Frozen + Amberbound + Rainbow"),
        ]

        lines = [
            f"[PRICE CARD] {display}",
            f"Base sell: {fmt(base)} coins | Max scale: {scale}x | Scaled sell: {fmt(scaled)} coins",
            f"",
            f"Sell prices at max scale with mutations:",
        ]

        for weather, lunar, colour, label in combos:
            r = _calc(cid, weather, lunar, colour, data)
            lines.append(f"  {label}: {fmt(r.final_price)} coins (×{r.combined_mutation_mult})")

        # Add with Sell Boost IV
        max_no_bonus = _calc(cid, "Frozen", "Ambercharged", "Rainbow", data)
        max_with_boost = calculate_sell_price(
            cid, "Frozen", "Ambercharged", "Rainbow",
            at_max_scale=True, sell_boost_tier="IV", data=data,
        )
        max_with_all = calculate_sell_price(
            cid, "Frozen", "Ambercharged", "Rainbow",
            at_max_scale=True, sell_boost_tier="IV", friend_count=5, data=data,
        )
        lines.append(f"")
        lines.append(f"Max mutated (Frozen+Amberbound+Rainbow): {fmt(max_no_bonus.final_price)} coins")
        lines.append(f"  + Sell Boost IV (+50%): {fmt(max_with_boost.final_price)} coins")
        lines.append(f"  + Sell Boost IV + 5 friends: {fmt(max_with_all.final_price)} coins")

        write_chunk("relationships", f"price_{cid}", "\n".join(lines), {
            "entity_type": "crop", "entity_name": display, "internal_id": cid,
            "query_intents": "selling", "layer": "relationship",
        })
        count += 1
    print(f"  {count} price card chunks")


def gen_top_crops_price_summary(data):
    """Summary chunk ranking all crops by max theoretical sell price."""
    crops = data["crops"]
    results = []

    for cid in crops:
        r = calculate_sell_price(
            cid, "Frozen", "Ambercharged", "Rainbow",
            at_max_scale=True, sell_boost_tier="IV", friend_count=5, data=data,
        )
        results.append(r)

    results.sort(key=lambda r: r.final_price, reverse=True)

    lines = [
        "[SUMMARY] Top crops by maximum theoretical sell price",
        "Conditions: Frozen + Amberbound + Rainbow + max scale + Sell Boost IV + 5 friends",
        "",
    ]
    for i, r in enumerate(results, 1):
        lines.append(
            f"  {i}. {r.crop_name}: {fmt(r.final_price)} coins "
            f"(base {fmt(r.base_sell)}, {r.max_scale}x scale, ×{r.combined_mutation_mult} mutations)"
        )

    write_chunk("summaries", "top_crops_by_max_sell", "\n".join(lines), {
        "entity_type": "crop", "query_intents": "selling", "layer": "summary",
    })
    print("  1 top-crops-by-max-sell summary")


# ═══════════════════════════════════════════════════════════════
# LAYER 6: Pre-computed Economics & Stats
# ═══════════════════════════════════════════════════════════════

def gen_crop_profit_ratios(data):
    """Per-crop seed-to-sell ratio and multi-harvest hourly output."""
    crops = data["crops"]

    # Single-harvest ROI
    singles = []
    for cid, c in crops.items():
        if c["harvestType"] != "Single":
            continue
        display = c.get("displayName", CROP_DISPLAY.get(cid, cid))
        ratio = (c["sellPrice"] * c["maxScale"]) / c["seedPrice"] if c["seedPrice"] > 0 else 0
        singles.append((display, cid, c["seedPrice"], c["sellPrice"], c["maxScale"], ratio))
    singles.sort(key=lambda x: x[5], reverse=True)

    lines = ["[CROP ROI] Single-harvest crops ranked by sell/seed ratio (at max scale)"]
    for display, cid, seed, sell, scale, ratio in singles:
        lines.append(f"  {display}: {fmt(seed)} seed → {fmt(int(sell * scale))} sell = {ratio:.1f}x return")

    write_chunk("summaries", "crop_roi_single", "\n".join(lines), {
        "entity_type": "crop", "query_intents": "selling", "layer": "summary",
    })

    # Multi-harvest hourly output
    multis = []
    for cid, c in crops.items():
        if c["harvestType"] != "Multiple" or not c.get("slots") or not c.get("secondsToMature"):
            continue
        display = c.get("displayName", CROP_DISPLAY.get(cid, cid))
        regrow_s = c["secondsToMature"]
        slots = c["slots"]
        harvests_per_hour = (3600 / regrow_s) * slots if regrow_s > 0 else 0
        coins_per_hour = harvests_per_hour * c["sellPrice"]
        multis.append((display, cid, c["seedPrice"], c["sellPrice"], slots, regrow_s, harvests_per_hour, coins_per_hour))
    multis.sort(key=lambda x: x[7], reverse=True)

    lines = ["[CROP ROI] Multi-harvest crops ranked by coins per hour (base sell, no mutations)"]
    lines.append("Formula: (3600 / regrow_seconds) × slots × sell_price")
    lines.append("")
    for display, cid, seed, sell, slots, regrow, hph, cph in multis:
        regrow_str = f"{regrow // 3600}h" if regrow >= 3600 else f"{regrow // 60}m" if regrow >= 60 else f"{regrow}s"
        lines.append(f"  {display}: {fmt(int(cph))} coins/hr ({slots} slots, {regrow_str} regrow, {fmt(sell)} sell)")

    write_chunk("summaries", "crop_roi_multi", "\n".join(lines), {
        "entity_type": "crop", "query_intents": "selling", "layer": "summary",
    })
    print(f"  2 crop ROI summaries")


def gen_egg_expected_value(data):
    """Per-egg expected pet maturity sell value from spawn weights."""
    eggs, pets = data["eggs"], data["pets"]

    lines = ["[EGG VALUE] Expected pet maturity sell value per egg"]
    lines.append("Formula: sum(spawn_chance% × pet_maturity_sell_price) for each pet in egg")
    lines.append("")

    egg_values = []
    for eid, egg in eggs.items():
        expected = 0
        pet_lines = []
        for pid, pct in egg["spawns"].items():
            pet = pets.get(pid, {})
            pname = PET_DISPLAY.get(pid, pet.get("name", pid))
            sell = pet.get("maturitySellPrice", 0)
            contrib = (pct / 100) * sell
            expected += contrib
            pet_lines.append(f"    {pname}: {pct}% × {fmt(sell)} = {fmt(int(contrib))}")

        cp = egg.get("creditPrice")
        credit_str = str(cp) if cp is not None else "N/A"
        coin_roi = expected / egg["coinPrice"] if egg["coinPrice"] > 0 else 0

        lines.append(f"{egg['name']} (cost: {fmt(egg['coinPrice'])} coins / {credit_str} credits)")
        lines.extend(pet_lines)
        lines.append(f"  Expected value: {fmt(int(expected))} coins ({coin_roi:.2f}x coin ROI)")
        lines.append("")
        egg_values.append((egg["name"], eid, expected, egg["coinPrice"], coin_roi))

    # Add ranking
    egg_values.sort(key=lambda x: x[4], reverse=True)
    lines.append("Ranked by coin ROI:")
    for name, _, exp_val, cost, roi in egg_values:
        lines.append(f"  {name}: {roi:.2f}x ({fmt(int(exp_val))} expected / {fmt(cost)} cost)")

    write_chunk("summaries", "egg_expected_value", "\n".join(lines), {
        "entity_type": "egg", "query_intents": "hatching", "layer": "summary",
    })
    print("  1 egg expected value summary")


def gen_instagrow_costs(data):
    """Credit cost to instant-grow each multi-harvest crop."""
    crops = data["crops"]
    cost_per_sec = data["constants"]["instaGrowCostPerSecond"]

    items = []
    for cid, c in crops.items():
        regrow = c.get("secondsToMature")
        if not regrow or c["harvestType"] != "Multiple":
            continue
        display = c.get("displayName", CROP_DISPLAY.get(cid, cid))
        credit_cost = regrow * cost_per_sec
        items.append((display, cid, regrow, credit_cost, c["sellPrice"]))

    items.sort(key=lambda x: x[3])

    lines = ["[INSTA-GROW] Credit cost to instant-grow multi-harvest crops"]
    lines.append(f"Rate: {cost_per_sec:.6f} credits per second")
    lines.append("")
    for display, cid, regrow, cost, sell in items:
        regrow_str = f"{regrow // 3600}h" if regrow >= 3600 else f"{regrow // 60}m" if regrow >= 60 else f"{regrow}s"
        lines.append(f"  {display}: {cost:.2f} credits ({regrow_str} regrow, {fmt(sell)} sell)")

    write_chunk("summaries", "instagrow_costs", "\n".join(lines), {
        "entity_type": "crop", "query_intents": "growing", "layer": "summary",
    })
    print("  1 insta-grow cost summary")


def gen_feeding_costs(data):
    """Per-pet feeding cost: diet crops ranked by seed price, total fill cost."""
    pets, crops = data["pets"], data["crops"]
    count = 0

    for pid, pet in pets.items():
        pname = PET_DISPLAY.get(pid, pet["name"])
        hunger = pet["hunger"]

        diet_info = []
        for cid in pet["diet"]:
            c = crops.get(cid, {})
            display = c.get("displayName", CROP_DISPLAY.get(cid, cid))
            seed = c.get("seedPrice", 0)
            sell = c.get("sellPrice", 0)
            # Feeding restores hunger equal to crop sell value
            crops_needed = (hunger / sell) if sell > 0 else float('inf')
            total_seed_cost = crops_needed * seed
            diet_info.append((display, seed, sell, crops_needed, total_seed_cost))

        diet_info.sort(key=lambda x: x[4])

        lines = [f"[FEEDING COST] {pname}"]
        lines.append(f"Hunger to fill: {fmt(hunger)} coins worth of crops")
        lines.append(f"Diet options (ranked by total seed cost to fill):")
        for display, seed, sell, needed, total in diet_info:
            lines.append(f"  {display}: {fmt(seed)} seed, {fmt(sell)} sell → "
                         f"{needed:.1f} crops needed, {fmt(int(total))} total seed cost")

        if diet_info:
            cheapest = diet_info[0]
            priciest = diet_info[-1]
            lines.append(f"Cheapest fill: {cheapest[0]} ({fmt(int(cheapest[4]))} coins)")
            if len(diet_info) > 1:
                lines.append(f"Most expensive fill: {priciest[0]} ({fmt(int(priciest[4]))} coins)")

        write_chunk("relationships", f"feed_cost_{pid}", "\n".join(lines), {
            "entity_type": "pet", "entity_name": pname, "internal_id": pid,
            "query_intents": "diet", "layer": "relationship",
        })
        count += 1
    print(f"  {count} feeding cost chunks")


def gen_growth_time_ranking(data):
    """All multi-harvest crops sorted by regrow time."""
    crops = data["crops"]

    items = []
    for cid, c in crops.items():
        if c["harvestType"] != "Multiple" or not c.get("secondsToMature"):
            continue
        display = c.get("displayName", CROP_DISPLAY.get(cid, cid))
        items.append((display, c["secondsToMature"], c.get("slots", 0), c["sellPrice"]))

    items.sort(key=lambda x: x[1])

    lines = ["[GROWTH TIMES] Multi-harvest crops ranked by regrow time (fastest first)"]
    for display, secs, slots, sell in items:
        if secs >= 3600:
            time_str = f"{secs // 3600}h {(secs % 3600) // 60}m" if secs % 3600 else f"{secs // 3600}h"
        elif secs >= 60:
            time_str = f"{secs // 60}m {secs % 60}s" if secs % 60 else f"{secs // 60}m"
        else:
            time_str = f"{secs}s"
        lines.append(f"  {display}: {time_str} regrow, {slots} slots, {fmt(sell)} sell")

    write_chunk("summaries", "growth_time_ranking", "\n".join(lines), {
        "entity_type": "crop", "query_intents": "growing", "layer": "summary",
    })
    print("  1 growth time ranking summary")


def gen_friend_bonus_table(data):
    """Top 15 crops with sell prices at 0-5 friends."""
    crops = data["crops"]
    bonus = data["constants"]["friendBonusPerPlayer"]

    # Sort by base sell × max scale
    ranked = []
    for cid, c in crops.items():
        display = c.get("displayName", CROP_DISPLAY.get(cid, cid))
        scaled = c["sellPrice"] * c["maxScale"]
        ranked.append((display, scaled))
    ranked.sort(key=lambda x: x[1], reverse=True)

    lines = ["[FRIEND BONUS] Sell prices with 0-5 friends (top 15 crops at max scale)"]
    lines.append(f"Each friend adds +{int(bonus * 100)}% sell price (additive)")
    lines.append("")
    header = f"  {'Crop':<16} {'0':>12} {'1':>12} {'2':>12} {'3':>12} {'4':>12} {'5':>12}"
    lines.append(header)

    for display, scaled in ranked[:15]:
        cols = [fmt(int(scaled * (1 + bonus * f))) for f in range(6)]
        lines.append(f"  {display:<16} " + " ".join(f"{c:>12}" for c in cols))

    write_chunk("summaries", "friend_bonus_table", "\n".join(lines), {
        "entity_type": "crop", "query_intents": "selling", "layer": "summary",
    })
    print("  1 friend bonus table summary")


def gen_weather_mutation_rates(data):
    """Expected mutations per crop per hour from each weather event."""
    weather = data["weather_events"]

    lines = ["[WEATHER RATES] Expected mutations per mature crop per hour"]
    lines.append("")

    for wid, w in weather.items():
        rate = w["chancePerMinutePerCrop"]
        group = w["groupId"]

        if group == "Hydro":
            # Hydro: ~every 20-30 min, lasts 5 min → ~12 min uptime per hour
            uptime_min = 12
            freq = "every 20-30 min, 5 min duration"
        else:
            # Lunar: every 4 hours, lasts 10 min → ~2.5 min per hour
            uptime_min = 2.5
            freq = "every 4 hours, 10 min duration"

        expected_per_hour = rate * uptime_min / 100
        chance_in_window = 1 - (1 - rate / 100) ** (5 if group == "Hydro" else 10)

        wname = INTERNAL_TO_DISPLAY.get(wid, w["name"])
        mut_name = INTERNAL_TO_DISPLAY.get(w["mutation"], w["mutation"])

        lines.append(f"{wname} ({freq})")
        lines.append(f"  Applies: {mut_name} mutation")
        lines.append(f"  Rate: {rate}% per minute per mature crop")
        lines.append(f"  Chance per crop per weather window: {chance_in_window * 100:.1f}%")
        lines.append(f"  Expected mutations per crop per hour: {expected_per_hour:.2f}")
        lines.append("")

    write_chunk("summaries", "weather_mutation_rates", "\n".join(lines), {
        "entity_type": "weather", "query_intents": "mutation", "layer": "summary",
    })
    print("  1 weather mutation rates summary")


def gen_pet_maturity_economics(data):
    """Per-pet: maturity sell value, hunger cost over lifetime, net profit/loss."""
    pets = data["pets"]

    items = []
    for pid, pet in pets.items():
        pname = PET_DISPLAY.get(pid, pet["name"])
        sell = pet["maturitySellPrice"]
        hours = pet["hoursToMature"]
        hunger = pet["hunger"]
        # Rough hunger cost: assume pet needs feeding once per hour of maturity
        # (this is just hunger_cost × hours as an upper bound reference)
        lifetime_hunger = hunger * hours
        net = sell - lifetime_hunger
        items.append((pname, pid, pet["rarity"], sell, hours, hunger, lifetime_hunger, net))

    items.sort(key=lambda x: x[7], reverse=True)

    lines = ["[PET VALUE] Pet maturity economics"]
    lines.append("Maturity sell price vs hunger cost over maturity hours")
    lines.append("Lifetime hunger = hunger_cost × hours_to_mature (upper bound)")
    lines.append("")
    for pname, pid, rarity, sell, hours, hunger, lifetime, net in items:
        sign = "+" if net >= 0 else ""
        lines.append(f"  {pname} ({rarity}): sells {fmt(sell)}, "
                     f"{hours}h to mature, {fmt(hunger)} hunger/fill, "
                     f"lifetime hunger {fmt(int(lifetime))}, "
                     f"net {sign}{fmt(int(net))}")

    write_chunk("summaries", "pet_maturity_economics", "\n".join(lines), {
        "entity_type": "pet", "query_intents": "selling", "layer": "summary",
    })
    print("  1 pet maturity economics summary")


def gen_mutation_path_costs(data):
    """Cost comparison: potion vs weather vs pet granter for each mutation."""
    mutations = data["mutations"]
    tools = data["tools"]
    abilities = data["abilities"]
    pets = data["pets"]
    weather = data["weather_events"]

    # Build ability→pet map
    ability_to_pets = {}
    for pid, pet in pets.items():
        pname = PET_DISPLAY.get(pid, pet["name"])
        for aid in pet["abilities"]:
            ability_to_pets.setdefault(aid, []).append(pname)

    # Map mutation → granter abilities
    granter_map = {}
    for aid, ab in abilities.items():
        granted = ab.get("params", {}).get("grantedMutations", [])
        for mid in granted:
            granter_map.setdefault(mid, []).append((aid, ab))

    # Map mutation → weather event
    weather_map = {}
    for wid, w in weather.items():
        weather_map[w["mutation"]] = (wid, w)

    # Map mutation → potion
    potion_map = {}
    for tid, t in tools.items():
        if t.get("mutation"):
            potion_map[t["mutation"]] = t

    lines = ["[MUTATION PATHS] How to obtain each mutation: weather, pet granter, or potion"]
    lines.append("")

    for mid, mut in mutations.items():
        display = INTERNAL_TO_DISPLAY.get(mid, mut["name"])
        lines.append(f"{display} (×{mut['coinMultiplier']} sell multiplier):")

        # Base planting chance
        if mut["baseChance"] > 0:
            lines.append(f"  Planting: {mut['baseChance'] * 100}% base chance when planting any crop")

        # Weather
        w_entry = weather_map.get(mid)
        if w_entry:
            wid, w = w_entry
            wname = INTERNAL_TO_DISPLAY.get(wid, w["name"])
            lines.append(f"  Weather: {wname} — {w['chancePerMinutePerCrop']}%/min per crop")

        # Pet granters
        granters = granter_map.get(mid, [])
        for aid, ab in granters:
            owners = ability_to_pets.get(aid, [])
            owner_str = ", ".join(owners) if owners else "unknown"
            lines.append(f"  Pet: {ab['name']} ({ab.get('baseProbability', '?')}%/min × STR) — {owner_str}")

        # Potion
        potion = potion_map.get(mid)
        if potion:
            lines.append(f"  Potion: {potion['name']} ({potion['rarity']}, "
                         f"{fmt(potion['coinPrice'])} coins)")

        if not w_entry and not granters and not potion and mut["baseChance"] == 0:
            lines.append(f"  Requires upgrade from a lower-tier mutation")

        lines.append("")

    write_chunk("summaries", "mutation_paths", "\n".join(lines), {
        "entity_type": "mutation", "query_intents": "mutation", "layer": "summary",
    })
    print("  1 mutation paths summary")


# ═══════════════════════════════════════════════════════════════
# LAYER 7: Probability & Rate Tables
# ═══════════════════════════════════════════════════════════════

def _eggs_for_confidence(p: float, confidence: float) -> int:
    """How many trials needed for P(at least 1 success) >= confidence.
    p = per-trial probability (0-1), confidence = target (e.g. 0.95)."""
    if p <= 0:
        return float('inf')
    if p >= 1:
        return 1
    return math.ceil(math.log(1 - confidence) / math.log(1 - p))


def gen_hatching_probability(data):
    """Per-egg per-pet: eggs needed for 50%, 86.7%, 95%, 99% confidence."""
    eggs, pets = data["eggs"], data["pets"]
    confidences = [0.50, 0.867, 0.95, 0.99]

    for eid, egg in eggs.items():
        lines = [
            f"[HATCHING ODDS] {egg['name']}",
            f"Price: {fmt(egg['coinPrice'])} coins / {egg.get('creditPrice', 'N/A')} credits",
            f"How many eggs to hatch a specific pet at each confidence level:",
            f"",
            f"  {'Pet':<16} {'Chance':>7} {'50%':>6} {'86.7%':>6} {'95%':>6} {'99%':>6}",
        ]

        for pid, pct in egg["spawns"].items():
            pet = pets.get(pid, {})
            pname = PET_DISPLAY.get(pid, pet.get("name", pid))
            p = pct / 100
            counts = [_eggs_for_confidence(p, c) for c in confidences]
            lines.append(
                f"  {pname:<16} {pct:>5.1f}% {counts[0]:>6} {counts[1]:>6} {counts[2]:>6} {counts[3]:>6}"
            )

        lines.append("")
        lines.append("Read as: '14 eggs gives you a 50% chance of hatching at least one Bunny'")

        write_chunk("summaries", f"hatch_odds_{eid}", "\n".join(lines), {
            "entity_type": "egg", "entity_name": egg["name"], "internal_id": eid,
            "query_intents": "hatching", "layer": "summary",
        })
    print(f"  {len(eggs)} hatching probability chunks")


def gen_pet_mutation_probability(data):
    """Gold/Rainbow mutation chance on pet hatch with 0-3 Pet Mutation Boost pets."""
    mutations = data["mutations"]
    abilities = data["abilities"]
    pets = data["pets"]

    gold_base = mutations["Gold"]["baseChance"]      # 0.01 = 1%
    rainbow_base = mutations["Rainbow"]["baseChance"]  # 0.001 = 0.1%

    # Pet Mutation Boost tiers (passive, increases mutation chance on hatch)
    boost_tiers = []
    for aid in ["PetMutationBoost", "PetMutationBoostII"]:
        ab = abilities.get(aid)
        if ab:
            pct = ab["params"].get("mutationChanceIncreasePercentage", 0)
            # Find which pets own this
            owners = []
            for pid, pet in pets.items():
                if aid in pet["abilities"]:
                    pname = PET_DISPLAY.get(pid, pet["name"])
                    owners.append(f"{pname} ({pet['abilities'][aid]}%)")
            boost_tiers.append((ab["name"], pct, owners))

    confidences = [0.50, 0.867, 0.95, 0.99]

    lines = [
        "[PET MUTATION ODDS] Gold & Rainbow pet probability on hatch",
        f"Base Gold chance: {gold_base * 100}% per hatch",
        f"Base Rainbow chance: {rainbow_base * 100}% per hatch",
        "",
        "Pet Mutation Boost abilities (passive — always active while pet is in party):",
    ]
    for name, pct, owners in boost_tiers:
        lines.append(f"  {name}: +{pct}% mutation chance — owned by {', '.join(owners)}")

    # Calculate effective rates with stacking (additive boosts)
    # 0, 1, 2, 3 Pet Mutation Boost pets (using highest tier available)
    best_boost_pct = max((t[1] for t in boost_tiers), default=0)

    lines.append("")
    lines.append(f"Eggs needed for Gold pet (with 0-3 Pet Mutation Boost II pets, +{best_boost_pct}% each):")
    lines.append(f"  {'Boosts':>8} {'Chance':>8} {'50%':>6} {'86.7%':>6} {'95%':>6} {'99%':>6}")

    for n_boosts in range(4):
        total_boost = 1 + (best_boost_pct / 100) * n_boosts
        p_gold = gold_base * total_boost
        counts = [_eggs_for_confidence(p_gold, c) for c in confidences]
        lines.append(
            f"  {n_boosts:>8} {p_gold * 100:>7.2f}% {counts[0]:>6} {counts[1]:>6} {counts[2]:>6} {counts[3]:>6}"
        )

    lines.append("")
    lines.append(f"Eggs needed for Rainbow pet (with 0-3 Pet Mutation Boost II pets):")
    lines.append(f"  {'Boosts':>8} {'Chance':>8} {'50%':>6} {'86.7%':>6} {'95%':>6} {'99%':>6}")

    for n_boosts in range(4):
        total_boost = 1 + (best_boost_pct / 100) * n_boosts
        p_rainbow = rainbow_base * total_boost
        counts = [_eggs_for_confidence(p_rainbow, c) for c in confidences]
        lines.append(
            f"  {n_boosts:>8} {p_rainbow * 100:>6.3f}% {counts[0]:>6} {counts[1]:>6} {counts[2]:>6} {counts[3]:>6}"
        )

    lines.append("")
    lines.append("Note: Pet Mutation Boost is passive — stacks across all 3 active pet slots.")
    lines.append("You can run 3 Dragonflies or 3 Squirrels (duplicate pets allowed in team).")

    write_chunk("summaries", "pet_mutation_odds", "\n".join(lines), {
        "entity_type": "pet", "query_intents": "mutation", "layer": "summary",
    })
    print("  1 pet mutation probability chunk")


def gen_ability_hourly_rates(data):
    """Per-ability: expected procs/hr and cumulative effect at STR 80 and 100.
    For growth boosts, also show effective grow time with 1-3 pets."""
    abilities = data["abilities"]
    pets = data["pets"]
    owned = _get_owned_abilities(data)

    # Build ability→pet map
    ability_to_pets: dict[str, list[tuple[str, int]]] = {}
    for pid, pet in pets.items():
        pname = PET_DISPLAY.get(pid, pet["name"])
        for aid, weight in pet["abilities"].items():
            ability_to_pets.setdefault(aid, []).append((pname, weight))

    # Group abilities by effect type for separate chunks
    growth_abilities = []  # plantGrowthReductionMinutes
    egg_abilities = []     # eggGrowthTimeReductionMinutes
    scale_abilities = []   # scaleIncreasePercentage
    coin_abilities = []    # baseMaxCoinsFindable
    sell_abilities = []    # cropSellPriceIncreasePercentage (sell boost on sell trigger)
    other_abilities = []

    for aid, ab in abilities.items():
        if aid not in owned:
            continue
        if ab.get("baseProbability") is None:
            continue  # passive abilities — no proc rate
        params = ab.get("params", {})
        if "plantGrowthReductionMinutes" in params:
            growth_abilities.append((aid, ab))
        elif "eggGrowthTimeReductionMinutes" in params:
            egg_abilities.append((aid, ab))
        elif "scaleIncreasePercentage" in params:
            scale_abilities.append((aid, ab))
        elif "baseMaxCoinsFindable" in params:
            coin_abilities.append((aid, ab))
        elif "cropSellPriceIncreasePercentage" in params and ab["trigger"] != "continuous":
            sell_abilities.append((aid, ab))
        elif not params.get("grantedMutations"):
            other_abilities.append((aid, ab))

    # ── Plant Growth Boost rates ──
    lines = [
        "[ABILITY RATES] Plant Growth Boost — expected crop time reduction per hour",
        "Formula: procs/hr = baseProbability% × (STR/100) × 60 min",
        "Each proc reduces remaining crop grow time by X minutes.",
        "",
        f"  {'Ability':<28} {'Prob':>5} {'Reduction':>10} {'Procs/hr':>10} {'Min saved/hr':>13} {'Weather':>8}",
        f"  {'':>28} {'':>5} {'':>10} {'STR80/100':>10} {'STR80/100':>13}",
    ]

    for aid, ab in growth_abilities:
        prob = ab["baseProbability"]
        reduction = ab["params"]["plantGrowthReductionMinutes"]
        weather = ab["params"].get("requiredWeather")
        weather_str = INTERNAL_TO_DISPLAY.get(weather, weather) if weather else "—"

        procs_80 = prob / 100 * 0.80 * 60
        procs_100 = prob / 100 * 1.00 * 60
        saved_80 = procs_80 * reduction
        saved_100 = procs_100 * reduction

        lines.append(
            f"  {ab['name']:<28} {prob:>4}% {reduction:>8} min "
            f"{procs_80:>4.1f}/{procs_100:<4.1f} "
            f"{saved_80:>5.0f}/{saved_100:<5.0f} {weather_str:>8}"
        )

    # Multi-pet stacking table for Plant Growth Boost II (most common)
    pgb2 = abilities.get("PlantGrowthBoostII")
    if pgb2:
        prob = pgb2["baseProbability"]
        reduction = pgb2["params"]["plantGrowthReductionMinutes"]
        lines.append("")
        lines.append("Plant Growth Boost II with multiple pets (STR 100, no weather required):")
        lines.append(f"  {'Pets':>4} {'Procs/hr':>10} {'Min saved/hr':>13} {'Effective rate':>16}")

        for n in range(1, 4):
            procs = prob / 100 * 1.00 * 60 * n
            saved = procs * reduction
            # A crop effectively ages (1 + saved/60) minutes per real minute
            effective = 1 + saved / 60
            lines.append(f"  {n:>4} {procs:>10.1f} {saved:>13.0f} {effective:>13.1f}x speed")

        lines.append("")
        lines.append("Example: 3× Plant Growth Boost II pets at STR 100")
        lines.append(f"  Crop with 60 min grow time → ~{60 / (1 + (prob / 100 * 1.0 * 60 * 3 * reduction) / 60):.0f} real minutes")
        lines.append(f"  Crop with 120 min grow time → ~{120 / (1 + (prob / 100 * 1.0 * 60 * 3 * reduction) / 60):.0f} real minutes")

    owners_str = ", ".join(f"{n} ({w}%)" for n, w in ability_to_pets.get("PlantGrowthBoostII", []))
    if owners_str:
        lines.append(f"  Owned by: {owners_str}")

    write_chunk("summaries", "ability_rates_growth", "\n".join(lines), {
        "entity_type": "ability", "query_intents": "growing", "layer": "summary",
    })

    # ── Egg Growth Boost rates ──
    lines = [
        "[ABILITY RATES] Egg Growth Boost — expected hatch time reduction per hour",
        "Formula: procs/hr = baseProbability% × (STR/100) × 60",
        "",
        f"  {'Ability':<28} {'Prob':>5} {'Reduction':>10} {'Procs/hr':>10} {'Min saved/hr':>13} {'Weather':>8}",
    ]

    for aid, ab in egg_abilities:
        prob = ab["baseProbability"]
        reduction = ab["params"]["eggGrowthTimeReductionMinutes"]
        weather = ab["params"].get("requiredWeather")
        weather_str = INTERNAL_TO_DISPLAY.get(weather, weather) if weather else "—"
        owners = ability_to_pets.get(aid, [])
        owner_str = ", ".join(f"{n}" for n, _ in owners)

        procs_100 = prob / 100 * 1.00 * 60
        saved_100 = procs_100 * reduction

        lines.append(
            f"  {ab['name']:<28} {prob:>4}% {reduction:>8} min "
            f"{procs_100:>10.1f} {saved_100:>13.0f} {weather_str:>8}"
        )
        lines.append(f"    Owned by: {owner_str}")

    # Multi-pet stacking for egg hatching
    lines.append("")
    lines.append("Multi-pet stacking at STR 100 (e.g. 3× Chicken with Egg Growth Boost I):")
    egb1 = abilities.get("EggGrowthBoost")
    if egb1:
        prob = egb1["baseProbability"]
        reduction = egb1["params"]["eggGrowthTimeReductionMinutes"]
        for n in range(1, 4):
            procs = prob / 100 * 1.00 * 60 * n
            saved = procs * reduction
            lines.append(f"  {n} pet(s): {procs:.1f} procs/hr, {saved:.0f} min saved/hr")

    write_chunk("summaries", "ability_rates_egg", "\n".join(lines), {
        "entity_type": "ability", "query_intents": "hatching", "layer": "summary",
    })

    # ── Crop Scale Boost rates ──
    lines = [
        "[ABILITY RATES] Crop Scale Boost — expected size increase per hour",
        "Formula: procs/hr = baseProbability% × (STR/100) × 60",
        "Each proc increases crop scale by X%.",
        "",
    ]

    for aid, ab in scale_abilities:
        prob = ab["baseProbability"]
        scale_pct = ab["params"]["scaleIncreasePercentage"]
        weather = ab["params"].get("requiredWeather")
        weather_str = f" [requires {INTERNAL_TO_DISPLAY.get(weather, weather)}]" if weather else ""
        owners = ability_to_pets.get(aid, [])
        owner_str = ", ".join(f"{n} ({w}%)" for n, w in owners)

        procs_100 = prob / 100 * 1.00 * 60
        pct_per_hr = procs_100 * scale_pct

        lines.append(f"{ab['name']}: {prob}% prob, +{scale_pct}% per proc{weather_str}")
        lines.append(f"  At STR 100: {procs_100:.2f} procs/hr → +{pct_per_hr:.1f}% scale/hr")
        lines.append(f"  Hours to double scale (100%→200%): ~{100 / pct_per_hr:.0f}h")
        lines.append(f"  Owned by: {owner_str}")
        lines.append("")

    write_chunk("summaries", "ability_rates_scale", "\n".join(lines), {
        "entity_type": "ability", "query_intents": "growing", "layer": "summary",
    })

    # ── Coin Finder rates ──
    lines = [
        "[ABILITY RATES] Coin Finder — expected coins per hour",
        "Formula: procs/hr = baseProbability% × (STR/100) × 60",
        "Each proc finds a random amount up to maxCoinsFindable × STR.",
        "Expected coins/proc ≈ maxCoins × STR / 2 (uniform distribution estimate)",
        "",
    ]

    for aid, ab in coin_abilities:
        prob = ab["baseProbability"]
        max_coins = ab["params"]["baseMaxCoinsFindable"]
        weather = ab["params"].get("requiredWeather")
        weather_str = f" [requires {INTERNAL_TO_DISPLAY.get(weather, weather)}]" if weather else ""
        owners = ability_to_pets.get(aid, [])
        owner_str = ", ".join(f"{n} ({w}%)" for n, w in owners)

        procs_100 = prob / 100 * 1.00 * 60
        # Expected = procs × avg coins per proc (avg = maxCoins × STR / 2)
        avg_per_proc = max_coins * 1.00 / 2
        expected_hr = procs_100 * avg_per_proc

        lines.append(f"{ab['name']}: {prob}% prob, max {fmt(max_coins)} × STR coins/proc{weather_str}")
        lines.append(f"  At STR 100: {procs_100:.1f} procs/hr, ~{fmt(int(expected_hr))} coins/hr expected")
        lines.append(f"  Owned by: {owner_str}")
        lines.append("")

    write_chunk("summaries", "ability_rates_coins", "\n".join(lines), {
        "entity_type": "ability", "query_intents": "selling", "layer": "summary",
    })

    # ── Sell Boost rates ──
    lines = [
        "[ABILITY RATES] Sell Boost — proc chance per sell action",
        "Trigger: sellAllCrops (procs per sell action, not per minute)",
        "Formula: proc chance = baseProbability% × (STR/100) per sell",
        "",
    ]

    for aid, ab in sell_abilities:
        prob = ab["baseProbability"]
        sell_pct = ab["params"]["cropSellPriceIncreasePercentage"]
        owners = ability_to_pets.get(aid, [])
        owner_str = ", ".join(f"{n} ({w}%)" for n, w in owners)

        chance_80 = prob / 100 * 0.80
        chance_100 = prob / 100 * 1.00

        lines.append(f"{ab['name']}: {prob}% base, +{sell_pct}% sell price when it procs")
        lines.append(f"  At STR 80: {chance_80 * 100:.1f}% chance per sell")
        lines.append(f"  At STR 100: {chance_100 * 100:.1f}% chance per sell")
        lines.append(f"  With 3 duplicate pets: {(1 - (1 - chance_100) ** 3) * 100:.1f}% chance at least one procs")
        lines.append(f"  Owned by: {owner_str}")
        lines.append("")

    write_chunk("summaries", "ability_rates_sell", "\n".join(lines), {
        "entity_type": "ability", "query_intents": "selling", "layer": "summary",
    })

    # ── Mutation Granter rates ──
    granter_abilities = [(aid, ab) for aid, ab in abilities.items()
                         if aid in owned and ab.get("params", {}).get("grantedMutations")]

    lines = [
        "[ABILITY RATES] Mutation Granters — expected mutations per hour",
        "Formula: procs/hr = baseProbability% × (STR/100) × 60",
        "Each proc applies the mutation to a random mature crop in garden.",
        "",
    ]

    for aid, ab in granter_abilities:
        prob = ab["baseProbability"]
        granted = ab["params"]["grantedMutations"]
        owners = ability_to_pets.get(aid, [])
        owner_str = ", ".join(f"{n} ({w}%)" for n, w in owners)
        mut_names = [INTERNAL_TO_DISPLAY.get(m, m) for m in granted]

        procs_100 = prob / 100 * 1.00 * 60

        lines.append(f"{ab['name']}: {prob}%/min × STR, grants {', '.join(mut_names)}")
        lines.append(f"  At STR 100: {procs_100:.1f} procs/hr")
        lines.append(f"  With 3 pets: {procs_100 * 3:.1f} procs/hr")
        lines.append(f"  Owned by: {owner_str}")
        lines.append("")

    write_chunk("summaries", "ability_rates_granters", "\n".join(lines), {
        "entity_type": "ability", "query_intents": "mutation", "layer": "summary",
    })

    # ── Other proc-based abilities ──
    if other_abilities:
        lines = [
            "[ABILITY RATES] Other proc-based abilities",
            "",
        ]

        for aid, ab in other_abilities:
            prob = ab["baseProbability"]
            trigger = ab["trigger"]
            owners = ability_to_pets.get(aid, [])
            owner_str = ", ".join(f"{n} ({w}%)" for n, w in owners)

            if trigger == "continuous":
                rate_str = f"{prob / 100 * 1.00 * 60:.1f} procs/hr at STR 100"
            else:
                rate_str = f"{prob / 100 * 1.00 * 100:.1f}% chance per {trigger} at STR 100"

            lines.append(f"{ab['name']} ({trigger}): {prob}% base → {rate_str}")
            lines.append(f"  Owned by: {owner_str}")
            lines.append("")

        write_chunk("summaries", "ability_rates_other", "\n".join(lines), {
            "entity_type": "ability", "query_intents": "abilities", "layer": "summary",
        })

    chunk_count = 7 + (1 if other_abilities else 0)
    print(f"  {chunk_count} ability rate chunks")


def gen_gold_rainbow_crop_probability(data):
    """How many crops to plant for Gold/Rainbow at various confidence levels,
    with and without Produce Mutation Boost pets."""
    mutations = data["mutations"]
    abilities = data["abilities"]
    pets = data["pets"]

    gold_base = mutations["Gold"]["baseChance"]      # 0.01
    rainbow_base = mutations["Rainbow"]["baseChance"]  # 0.001
    confidences = [0.50, 0.867, 0.95, 0.99]

    # Produce Mutation Boost tiers (passive, increases weather mutation chance on crops)
    boost_info = []
    for aid in ["ProduceMutationBoost", "ProduceMutationBoostII"]:
        ab = abilities.get(aid)
        if not ab:
            continue
        pct = ab["params"].get("mutationChanceIncreasePercentage", 0)
        owners = []
        for pid, pet in pets.items():
            if aid in pet["abilities"]:
                pname = PET_DISPLAY.get(pid, pet["name"])
                owners.append(pname)
        boost_info.append((ab["name"], pct, owners))

    best_pct = max((b[1] for b in boost_info), default=0)

    lines = [
        "[MUTATION ODDS] Gold & Rainbow crop probability on planting",
        f"Gold: {gold_base * 100}% base chance per crop planted",
        f"Rainbow: {rainbow_base * 100}% base chance per crop planted",
        "",
        "Crops to plant for Gold (at each confidence level):",
        f"  {'Boost':>12} {'Chance':>8} {'50%':>6} {'86.7%':>6} {'95%':>6} {'99%':>6}",
    ]

    for n_boosts in range(4):
        total_mult = 1 + (best_pct / 100) * n_boosts
        p = gold_base * total_mult
        label = f"{n_boosts}× +{best_pct}%" if n_boosts else "None"
        counts = [_eggs_for_confidence(p, c) for c in confidences]
        lines.append(
            f"  {label:>12} {p * 100:>7.2f}% {counts[0]:>6} {counts[1]:>6} {counts[2]:>6} {counts[3]:>6}"
        )

    lines.append("")
    lines.append("Crops to plant for Rainbow (at each confidence level):")
    lines.append(f"  {'Boost':>12} {'Chance':>8} {'50%':>6} {'86.7%':>6} {'95%':>6} {'99%':>6}")

    for n_boosts in range(4):
        total_mult = 1 + (best_pct / 100) * n_boosts
        p = rainbow_base * total_mult
        label = f"{n_boosts}× +{best_pct}%" if n_boosts else "None"
        counts = [_eggs_for_confidence(p, c) for c in confidences]
        lines.append(
            f"  {label:>12} {p * 100:>6.3f}% {counts[0]:>6} {counts[1]:>6} {counts[2]:>6} {counts[3]:>6}"
        )

    lines.append("")
    for name, pct, owners in boost_info:
        lines.append(f"{name} (+{pct}%): owned by {', '.join(owners)}")
    lines.append("Note: Produce Mutation Boost is passive — stacks with all 3 active pets.")
    lines.append("Duplicate pets allowed (e.g., 3× Butterfly for 3× boost).")

    write_chunk("summaries", "gold_rainbow_crop_odds", "\n".join(lines), {
        "entity_type": "mutation", "query_intents": "mutation", "layer": "summary",
    })
    print("  1 gold/rainbow crop mutation probability chunk")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    with open(SOURCE) as f:
        data = json.load(f)

    ensure_dirs()
    print("Generating chunks from source_truth.json...")

    # Layer 1: Entities
    gen_pet_chunks(data)
    gen_crop_chunks(data)
    gen_ability_chunks(data)
    gen_mutation_chunks(data)
    gen_weather_chunks(data)
    gen_egg_chunks(data)
    gen_tool_chunks(data)
    gen_constants_chunk(data)

    # Layer 2: Relationships
    gen_diet_chains(data)
    gen_crop_feeders(data)
    gen_weather_combos(data)
    gen_multiplier_guide(data)
    gen_snow_egg_comparison(data)
    gen_ability_families(data)

    # Layer 3: Summaries
    gen_pets_by_egg_summary(data)
    gen_crops_by_rarity_summary(data)
    gen_cheapest_pets_summary(data)
    gen_best_sell_crops_summary(data)
    gen_harvest_comparison_summary(data)
    gen_pet_abilities_overview(data)

    # Layer 4: Strategies
    gen_strategy_chunks(data)

    # Layer 5: Pre-computed prices
    gen_price_cards(data)
    gen_top_crops_price_summary(data)

    # Layer 6: Economics & stats
    gen_crop_profit_ratios(data)
    gen_egg_expected_value(data)
    gen_instagrow_costs(data)
    gen_feeding_costs(data)
    gen_growth_time_ranking(data)
    gen_friend_bonus_table(data)
    gen_weather_mutation_rates(data)
    gen_pet_maturity_economics(data)
    gen_mutation_path_costs(data)

    # Layer 7: Probability & rate tables
    gen_hatching_probability(data)
    gen_pet_mutation_probability(data)
    gen_ability_hourly_rates(data)
    gen_gold_rainbow_crop_probability(data)

    total = sum(1 for _ in OUT_DIR.rglob("*.json"))
    print(f"\n=== Generated {total} total chunks ===")


if __name__ == "__main__":
    main()
