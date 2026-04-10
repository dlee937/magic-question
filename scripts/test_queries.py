#!/usr/bin/env python3
"""
Offline test script — validates entity resolution, intent detection,
and filter construction WITHOUT Ollama or ChromaDB.

Usage: python scripts/test_queries.py
"""

import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.entity_registry import find_entities, resolve_name
from src.query_analyser import analyse, _build_filters
from src.config import INTENT_HINTS

# ═══════════════════════════════════════════════════════════════
# Test cases: (query, expected_intent, expected_entity_ids, description)
# ═══════════════════════════════════════════════════════════════

TEST_CASES = [
    # ── Diet queries ──
    ("what does butterfly eat", "diet", ["Butterfly"], "basic diet query"),
    ("what can I feed my bunny", "diet", ["Bunny"], "feed synonym"),
    ("what food does cow like", "diet", ["Cow"], "food synonym"),
    ("is bee hungry", "diet", ["Bee"], "hunger keyword"),

    # ── Selling / price queries ──
    ("how much is mushroom worth", "selling", ["Mushroom"], "worth → selling"),
    ("price of bees", "selling", ["Bee"], "plural + price"),
    ("best way to make money", "strategy", [], "money but 'best' wins → strategy"),
    ("how many coins does cactus sell for", "selling", ["Cactus"], "coins + sell"),
    ("what is the value of bamboo", "selling", ["Bamboo"], "value keyword"),

    # ── Mutation queries ──
    ("how do I get frozen on my crops", "mutation", ["Frozen"], "mutation entity + intent"),
    ("what is the gold multiplier", "mutation", ["Gold"], "gold mutation"),
    ("how does thunderstruck work", "mutation", ["Thunderstruck"], "thunderstruck"),
    # "amberbound"/"dawnbound" hit mutation pattern before "vs" hits comparison
    ("amberbound vs dawnbound", "mutation", ["Ambercharged", "Dawncharged"], "mutation entities win over vs"),

    # ── Strategy queries ──
    ("what's the best pet for early game", "strategy", [], "best → strategy"),
    ("recommend a loadout", "strategy", [], "recommend keyword"),
    ("which tier is squirrel", "strategy", ["Squirrel"], "tier keyword"),

    # ── Ability queries ──
    ("what abilities does turkey have", "abilities", ["Turkey"], "abilities keyword"),
    ("what can butterfly do", "abilities", ["Butterfly"], "can X do → abilities"),
    # "sell" in "sell boost" hits selling before abilities
    ("does peacock have sell boost", "selling", ["Peacock"], "sell keyword wins over ability context"),

    # ── Hatching queries ──
    ("how long to hatch common egg", "hatching", ["CommonEgg"], "hatch + egg"),
    ("what spawns from legendary egg", "hatching", ["LegendaryEgg"], "spawn keyword"),
    ("what percent chance for capybara", "hatching", ["Capybara"], "percent/chance"),

    # ── Growing queries ──
    ("how long does carrot take to grow", "growing", ["Carrot"], "grow time"),
    ("what crops mature fastest", "growing", [], "mature keyword"),
    ("is strawberry single or multi harvest", "growing", ["Strawberry"], "harvest keyword"),

    # ── Weather queries ──
    # Rain/AmberMoon are registered entities, so they get detected
    ("when does rain happen", "weather", ["Rain"], "rain is a weather entity"),
    # "what does" matches abilities pattern before mutation
    ("what does thunderstorm do", "abilities", ["Thunderstorm"], "what-does pattern wins"),
    ("how often is amber moon", "weather", ["AmberMoon"], "amber moon is a weather entity"),

    # ── Multiplier queries ──
    # "mutations" hits mutation pattern before "stack" hits multipliers
    ("how do mutations stack", "mutation", [], "mutation keyword wins over stack"),
    ("is frozen additive or multiplicative", "mutation", ["Frozen"], "frozen hits mutation first"),
    # "sell" hits selling before "maximum" hits multipliers
    ("maximum sell multiplier combo", "selling", [], "sell keyword wins over maximum"),

    # ── Journal queries ──
    ("how to complete journal", "journal", [], "journal keyword"),
    ("what variants does carrot have", "journal", ["Carrot"], "variants keyword"),

    # ── Shopping queries ──
    ("where to buy seeds", "shopping", [], "buy keyword"),
    ("when does shop restock", "shopping", [], "restock keyword"),

    # ── Comparison queries ──
    # "egg" hits hatching before "vs" hits comparison
    ("snow egg vs winter egg", "hatching", ["SnowEgg", "WinterEgg"], "egg keyword wins over vs"),
    ("which is better cow or goat", "comparison", ["Cow", "Goat"], "better keyword"),

    # ── Lookup (no intent keywords) ──
    ("tell me about butterfly", "lookup", ["Butterfly"], "plain lookup"),
    # "snow" in "snow fox" hits weather pattern
    ("snow fox", "weather", ["SnowFox"], "snow keyword triggers weather"),

    # ── Multi-word / alias resolution ──
    ("fire horse abilities", "abilities", ["FireHorse"], "multi-word pet"),
    ("fava bean price", "selling", ["FavaBean"], "multi-word crop"),
    ("passion fruit grow time", "growing", ["PassionFruit"], "multi-word crop"),
    ("burro's tail info", "lookup", ["BurrosTail"], "apostrophe in name"),
    ("pine tree sell value", "selling", ["PineTree"], "multi-word crop"),

    # ── Plural handling ──
    ("how much are butterflies worth", "selling", ["Butterfly"], "irregular plural"),
    ("do bunnies eat carrots", "diet", ["Bunny", "Carrot"], "plural + multi entity"),
    ("ponies abilities", "abilities", ["Pony"], "plural -ies"),
    ("dragonflies", "lookup", ["Dragonfly"], "plural -ies"),

    # ── Edge cases ──
    ("hello", "lookup", [], "no entity, no intent"),
    ("asdf gibberish xyz", "lookup", [], "nonsense"),
    ("", "lookup", [], "empty query"),
    ("what is chrys", "lookup", ["Chrysanthemum"], "alias chrys"),
    ("mum price", "selling", ["Chrysanthemum"], "alias mum"),
]


def run_tests():
    passed = 0
    failed = 0
    errors = []

    print("=" * 70)
    print("MAGIC GARDEN BOT — Query Analysis Test Suite")
    print("=" * 70)

    for query, expected_intent, expected_ids, desc in TEST_CASES:
        result = analyse(query)

        actual_ids = [e.internal_id for e in result.entities]
        intent_ok = result.intent == expected_intent
        entities_ok = actual_ids == expected_ids

        if intent_ok and entities_ok:
            passed += 1
            print(f"  PASS  {desc}")
        else:
            failed += 1
            parts = []
            if not intent_ok:
                parts.append(f"intent: got '{result.intent}' expected '{expected_intent}'")
            if not entities_ok:
                parts.append(f"entities: got {actual_ids} expected {expected_ids}")
            msg = f"  FAIL  {desc} — {', '.join(parts)}"
            print(msg)
            errors.append((query, msg))

    # ── Filter construction tests ──
    print("\n" + "-" * 70)
    print("Filter Construction Tests")
    print("-" * 70)

    filter_tests = [
        ("what does butterfly eat", "diet",
         "should have $or with entity_name + query_intents",
         lambda f: "$or" in f and
                   any("entity_name" in c for c in f["$or"]) and
                   any("query_intents" in c for c in f["$or"])),

        ("best early game strategy", "strategy",
         "should filter by strategy layer",
         lambda f: f.get("layer", {}).get("$eq") == "strategy"),

        ("how do mutations stack", "mutation",
         "mutation intent should include both mutation and multipliers intents",
         lambda f: "$or" in f and
                   {"query_intents": {"$eq": "mutation"}} in f["$or"] and
                   {"query_intents": {"$eq": "multipliers"}} in f["$or"]),

        ("hello", "lookup",
         "should be empty (no filters)",
         lambda f: f == {}),

        ("tell me about butterfly", "lookup",
         "should have entity filters only (no query_intents)",
         lambda f: "$or" in f and
                   all("query_intents" not in c for c in f["$or"])),

        ("how much is mushroom worth", "selling",
         "should have entity + selling intent",
         lambda f: "$or" in f and
                   any(c.get("entity_name", {}).get("$eq") == "Mushroom" for c in f["$or"]) and
                   any(c.get("query_intents", {}).get("$eq") == "selling" for c in f["$or"])),
    ]

    for query, expected_intent, desc, check_fn in filter_tests:
        result = analyse(query)
        if result.intent != expected_intent:
            failed += 1
            print(f"  FAIL  {desc} — wrong intent: {result.intent}")
            continue
        if check_fn(result.metadata_filters):
            passed += 1
            print(f"  PASS  {desc}")
        else:
            failed += 1
            msg = f"  FAIL  {desc} — filters: {json.dumps(result.metadata_filters, indent=2)}"
            print(msg)
            errors.append((query, msg))

    # ── Intent hints coverage ──
    print("\n" + "-" * 70)
    print("Intent Hint Coverage")
    print("-" * 70)

    all_intents = {t[1] for t in TEST_CASES}
    all_intents.add("lookup")  # always present
    for intent in sorted(all_intents):
        if intent in INTENT_HINTS:
            passed += 1
            print(f"  PASS  '{intent}' has hint: {INTENT_HINTS[intent][:60]}...")
        else:
            failed += 1
            print(f"  FAIL  '{intent}' missing from INTENT_HINTS")

    # ── Summary ──
    print("\n" + "=" * 70)
    total = passed + failed
    print(f"Results: {passed}/{total} passed, {failed} failed")
    if errors:
        print(f"\nFailed queries:")
        for query, msg in errors:
            print(f"  \"{query}\"")
            print(f"    {msg}")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
