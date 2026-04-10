#!/usr/bin/env python3
"""
Live end-to-end test — runs queries through the full RAG pipeline
(requires Ollama running + ChromaDB indexed).

Usage: python scripts/test_live.py
       python scripts/test_live.py --verbose

Shows: entity detection, intent, filters used, chunks retrieved,
       context tokens, and the actual LLM response.
"""

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.bot import MagicGardenBot


# (query, expected_intent, expected_entities, answer_must_contain)
LIVE_TEST_CASES = [
    # ── Diet ──
    (
        "what does butterfly eat",
        "diet", ["Butterfly"],
        ["crop", "seed"],  # answer should mention crops/seeds
    ),
    (
        "what can I feed my bunny",
        "diet", ["Bunny"],
        [],
    ),

    # ── Selling ──
    (
        "how much is mushroom worth",
        "selling", ["Mushroom"],
        ["coin"],
    ),
    (
        "what is the sell price of bamboo",
        "selling", ["Bamboo"],
        ["coin"],
    ),

    # ── Abilities ──
    (
        "what abilities does turkey have",
        "abilities", ["Turkey"],
        [],
    ),

    # ── Mutation ──
    (
        "how do I get frozen on my crops",
        "mutation", ["Frozen"],
        ["rain", "snow"],  # should mention the weather path
    ),
    (
        "what is the maximum mutation multiplier",
        "multipliers", [],
        ["800", "rainbow"],  # max is x800 with rainbow
    ),

    # ── Hatching ──
    (
        "what spawns from common egg",
        "hatching", ["CommonEgg"],
        ["worm"],  # Worm is 60% from Common Egg
    ),

    # ── Strategy ──
    (
        "what's the best strategy for early game",
        "strategy", [],
        [],
    ),

    # ── Growing ──
    (
        "is strawberry single or multi harvest",
        "growing", ["Strawberry"],
        [],
    ),

    # ── Comparison ──
    (
        "snow egg vs winter egg",
        "comparison", ["SnowEgg", "WinterEgg"],
        ["coin"],
    ),

    # ── Carry-forward (sequential pair) ──
    (
        "tell me about squirrel",
        "lookup", ["Squirrel"],
        [],
    ),
    (
        "what does it eat",  # should carry-forward Squirrel
        "diet", ["Squirrel"],
        [],
    ),

    # ── Plurals ──
    (
        "how much are butterflies worth",
        "selling", ["Butterfly"],
        ["coin"],
    ),
]


def run_live_tests(verbose=False):
    print("=" * 70)
    print("MAGIC GARDEN BOT — Live End-to-End Tests")
    print("Requires: Ollama running + ChromaDB indexed")
    print("=" * 70)

    try:
        bot = MagicGardenBot()
    except Exception as e:
        print(f"\nFailed to initialize bot: {e}")
        print("Make sure Ollama is running and chunks are indexed.")
        return False

    chunk_count = bot.store.count()
    print(f"ChromaDB chunks: {chunk_count}")
    if chunk_count == 0:
        print("No chunks indexed! Run: python scripts/index_chunks.py")
        return False

    passed = 0
    failed = 0
    total_time = 0

    for query, expected_intent, expected_entities, must_contain in LIVE_TEST_CASES:
        print(f"\n{'─' * 60}")
        print(f"Query: \"{query}\"")

        start = time.time()
        try:
            result = bot.debug_answer(query)
        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1
            continue
        elapsed = time.time() - start
        total_time += elapsed

        # Check intent
        intent_ok = result["intent"] == expected_intent
        # Check entities
        entities_ok = result["entities"] == expected_entities
        # Check answer contains expected terms
        answer_lower = result["answer"].lower()
        contains_ok = all(term.lower() in answer_lower for term in must_contain)
        missing = [t for t in must_contain if t.lower() not in answer_lower]

        all_ok = intent_ok and entities_ok and contains_ok

        status = "PASS" if all_ok else "FAIL"
        if all_ok:
            passed += 1
        else:
            failed += 1

        print(f"  [{status}] Intent: {result['intent']}"
              f"{'' if intent_ok else f' (expected: {expected_intent})'}")
        print(f"         Entities: {result['entities']}"
              f"{'' if entities_ok else f' (expected: {expected_entities})'}")
        print(f"         Chunks: {result['chunks_retrieved']} | "
              f"Tokens: ~{result['context_tokens']} | "
              f"Time: {elapsed:.2f}s")

        if missing:
            print(f"         Missing in answer: {missing}")

        if verbose or not all_ok:
            # Truncate long answers for readability
            answer = result["answer"]
            if len(answer) > 200:
                answer = answer[:200] + "..."
            print(f"         Answer: {answer}")

        if verbose:
            print(f"         Embedding: {result['embedding_query']}")
            if result["conversation_context"]:
                print(f"         Conv ctx: {result['conversation_context']}")

    # ── Summary ──
    print(f"\n{'=' * 70}")
    total = passed + failed
    print(f"Results: {passed}/{total} passed, {failed} failed")
    print(f"Total time: {total_time:.1f}s ({total_time / max(total, 1):.1f}s avg per query)")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    success = run_live_tests(verbose=verbose)
    sys.exit(0 if success else 1)
