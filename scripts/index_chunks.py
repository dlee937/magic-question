#!/usr/bin/env python3
"""Load generated chunks into ChromaDB. Run after generate_chunks.py."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.vector_store import VectorStore
from src.config import CHUNKS_DIR


def main():
    store = VectorStore()
    store.index_chunks(CHUNKS_DIR)
    print(f"Total chunks in database: {store.count()}")


if __name__ == "__main__":
    main()
