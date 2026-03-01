#!/usr/bin/env python3
"""
Interactive CLI for testing the bot locally.
Usage: python -m scripts.chat
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.bot import MagicGardenBot


def main():
    print("Magic Garden RAG Bot — Interactive Mode")
    print("Type 'quit' to exit, 'debug' to toggle debug info\n")

    bot = MagicGardenBot()
    debug_mode = False

    while True:
        try:
            query = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not query:
            continue
        if query.lower() == "quit":
            break
        if query.lower() == "debug":
            debug_mode = not debug_mode
            print(f"Debug mode: {'ON' if debug_mode else 'OFF'}")
            continue

        if debug_mode:
            result = bot.debug_answer(query)
            print(f"\n--- Debug ---")
            print(f"Entities: {result['entities']}")
            print(f"Intent: {result['intent']}")
            print(f"Embedding query: {result['embedding_query']}")
            print(f"Chunks retrieved: {result['chunks_retrieved']}")
            print(f"Context tokens: ~{result['context_tokens']}")
            print(f"Conv context: {result['conversation_context']}")
            print(f"--- Answer ---")
            print(f"Bot: {result['answer']}\n")
        else:
            answer = bot.answer(query)
            print(f"Bot: {answer}\n")


if __name__ == "__main__":
    main()
