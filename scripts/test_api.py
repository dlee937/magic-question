#!/usr/bin/env python3
"""
API server test — sends queries to the running FastAPI server and validates responses.

Requires: uvicorn api.server:app --host 0.0.0.0 --port 8000

Usage: python scripts/test_api.py
       python scripts/test_api.py --base-url http://localhost:8000
"""

import sys
import time
import argparse
import httpx


API_TESTS = [
    # (query, session_id, expected_intent, expected_entities, description)
    ("what does butterfly eat", "test1", "diet", ["Butterfly"], "diet query"),
    ("how much is mushroom worth", "test1", "selling", ["Mushroom"], "selling query"),
    ("how do I get frozen", "test1", "mutation", ["Frozen"], "mutation query"),
    ("best early game strategy", "test1", "strategy", [], "strategy query"),
    ("what spawns from common egg", "test1", "hatching", ["CommonEgg"], "hatching query"),

    # Carry-forward test (same session)
    ("tell me about squirrel", "carry_test", "lookup", ["Squirrel"], "carry-forward setup"),
    ("what does it eat", "carry_test", "diet", ["Squirrel"], "carry-forward follow-up"),

    # Separate session — no carry-forward
    ("what does it eat", "fresh_session", "diet", [], "no carry-forward in new session"),

    # Plural handling
    ("how much are butterflies worth", "test2", "selling", ["Butterfly"], "plural entity"),
    ("what do bunnies eat", "test2", "diet", ["Bunny"], "irregular plural"),

    # Multi-word entities
    ("fire horse abilities", "test2", "abilities", ["Fire Horse"], "multi-word entity"),
    ("snow egg vs winter egg", "test2", "comparison", ["SnowEgg", "WinterEgg"], "comparison query"),
]


def run_api_tests(base_url: str):
    print("=" * 70)
    print("MAGIC GARDEN BOT — API Server Tests")
    print(f"Target: {base_url}")
    print("=" * 70)

    client = httpx.Client(timeout=30.0)

    # ── Health check ──
    print("\nHealth check...", end=" ")
    try:
        resp = client.get(f"{base_url}/health")
        resp.raise_for_status()
        print(f"OK ({resp.json()})")
    except Exception as e:
        print(f"FAILED: {e}")
        print("\nMake sure the server is running:")
        print("  source .venv/bin/activate")
        print("  uvicorn api.server:app --host 0.0.0.0 --port 8000")
        return False

    # ── Clean up test sessions ──
    for sid in {"test1", "test2", "carry_test", "fresh_session"}:
        client.delete(f"{base_url}/session/{sid}")

    passed = 0
    failed = 0
    total_time = 0

    for query, session_id, expected_intent, expected_entities, desc in API_TESTS:
        print(f"\n{'─' * 60}")
        print(f"[{session_id}] \"{query}\" — {desc}")

        start = time.time()
        try:
            resp = client.post(f"{base_url}/ask", json={
                "query": query,
                "session_id": session_id,
            })
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1
            continue
        elapsed = time.time() - start
        total_time += elapsed

        intent_ok = data["intent"] == expected_intent
        entities_ok = data["entities_detected"] == expected_entities

        all_ok = intent_ok and entities_ok

        if all_ok:
            passed += 1
            print(f"  PASS  intent={data['intent']} entities={data['entities_detected']}")
        else:
            failed += 1
            if not intent_ok:
                print(f"  FAIL  intent: got '{data['intent']}' expected '{expected_intent}'")
            if not entities_ok:
                print(f"  FAIL  entities: got {data['entities_detected']} expected {expected_entities}")

        print(f"         chunks={data['chunks_retrieved']} tokens=~{data['context_tokens']} time={elapsed:.2f}s")
        answer = data["answer"]
        if len(answer) > 150:
            answer = answer[:150] + "..."
        print(f"         answer: {answer}")

    # ── Session cleanup test ──
    print(f"\n{'─' * 60}")
    print("Session cleanup test...")
    resp = client.delete(f"{base_url}/session/carry_test")
    if resp.status_code == 200 and resp.json().get("cleared") == "carry_test":
        passed += 1
        print("  PASS  session deleted successfully")
    else:
        failed += 1
        print(f"  FAIL  unexpected response: {resp.json()}")

    # ── Summary ──
    print(f"\n{'=' * 70}")
    total = passed + failed
    print(f"Results: {passed}/{total} passed, {failed} failed")
    print(f"Total time: {total_time:.1f}s ({total_time / max(len(API_TESTS), 1):.1f}s avg)")
    print("=" * 70)

    client.close()
    return failed == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test the Magic Garden API server")
    parser.add_argument("--base-url", default="http://localhost:8000",
                        help="API server base URL (default: http://localhost:8000)")
    args = parser.parse_args()
    success = run_api_tests(args.base_url)
    sys.exit(0 if success else 1)
