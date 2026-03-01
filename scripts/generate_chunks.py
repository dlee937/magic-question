#!/usr/bin/env python3
"""
Reads source_truth.json → generates chunk JSON files for indexing.
Run once after data extraction, re-run when game updates.

Usage: python -m scripts.generate_chunks
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = PROJECT_ROOT / "data"
SOURCE = DATA_DIR / "source_truth.json"
OUT_DIR = DATA_DIR / "chunks"

# Internal→display crop name mapping
CROP_DISPLAY = {
    "OrangeTulip": "Tulip", "FavaBean": "Fava Bean", "BurrosTail": "Burro's Tail",
    "PineTree": "Pine Tree", "VioletCort": "Violet Cort", "DragonFruit": "Dragon Fruit",
    "PassionFruit": "Passion Fruit", "DawnCelestial": "Dawnbinder",
    "MoonCelestial": "Moonbinder",
}

PET_DISPLAY = {
    "SnowFox": "Snow Fox", "FireHorse": "Fire Horse", "WhiteCaribou": "Caribou",
}


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
        mut_display = {
            "Ambershine": "Amberlit", "Ambercharged": "Amberbound",
            "Dawnlit": "Dawnlit", "Dawncharged": "Dawnbound",
        }
        weather_display = {"AmberMoon": "Amber Moon", "Dawn": "Dawn", "Frost": "Snow"}
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

    for aid, ab in abilities.items():
        owners = ability_to_pets.get(aid, [])
        owner_str = ", ".join(f"{name} ({w}%)" for name, w in owners)
        if not owner_str:
            owner_str = "No known pet (data-mined)"

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
        prob_str = f"{prob}% × STR" if prob else "passive (always active)"

        text = (
            f"[ABILITY] {ab['name']}\n"
            f"Internal ID: {aid}\n"
            f"Trigger: {ab['trigger']} | Probability: {prob_str}\n"
        )
        if param_lines:
            text += "Effect:\n" + "\n".join(param_lines) + "\n"
        if weather_req:
            weather_names = {"Frost": "Snow", "AmberMoon": "Amber Moon"}
            text += f"Requires weather: {weather_names.get(weather_req, weather_req)}\n"
        text += f"Owned by: {owner_str}"

        write_chunk("entities", f"ability_{aid}", text, {
            "entity_type": "ability", "entity_name": ab["name"],
            "internal_id": aid, "ability_trigger": ab["trigger"], "layer": "entity",
        })
    print(f"  {len(abilities)} ability chunks")


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
            weather_display = {"Frost": "Snow", "AmberMoon": "Amber Moon"}
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

        credit_str = str(tool.get("creditPrice", "N/A"))

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

    count = 0
    for family in families:
        lines = [f"[ABILITY FAMILY] {family['name']}", f"{family['desc']}", ""]

        for aid in family["members"]:
            ab = abilities.get(aid)
            if not ab:
                continue
            owners = ability_to_pets.get(aid, [])
            owner_str = ", ".join(f"{name} ({w}%)" for name, w in owners)
            if not owner_str:
                owner_str = "no pet (data-mined)"

            # Key param
            params = ab.get("params", {})
            weather_req = params.get("requiredWeather")
            weather_names = {"Frost": "Snow", "AmberMoon": "Amber Moon"}
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
            prob_str = f"{prob}%×STR" if prob else "passive"

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

    total = sum(1 for _ in OUT_DIR.rglob("*.json"))
    print(f"\n=== Generated {total} total chunks ===")


if __name__ == "__main__":
    main()
