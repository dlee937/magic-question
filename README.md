# Magic Garden RAG Bot

Local RAG chatbot for the Magic Garden game. Runs entirely on a Mac Mini M4 base model (16GB RAM, $599).

## Architecture

```
User Query → Entity Registry (regex) → Intent Detection → Query Reformulation
          → ChromaDB Retrieval (nomic-embed-text) → Context Assembly
          → Mistral 7B Generation (Metal GPU) → Response

LLM calls per query: exactly 1 (generation only)
Average latency: ~1.5-2 seconds
Context window usage: ~5-8% of 8K
```

## Data Source

All game data extracted directly from the game client JavaScript source code (Feb 2026 build). 250 chunks across 4 layers:

| Layer | Type | Count | Description |
|-------|------|-------|-------------|
| 1 | Entity | 167 | One chunk per game entity (21 pets, 44 crops, 67 abilities, etc.) |
| 2 | Relationship | 73 | Diet chains, crop feeders, ability families, weather combos, multiplier guide |
| 3 | Summary | 6 | Pets by egg, crops by rarity, hunger costs, sell values, harvest types, ability overview |
| 4 | Strategy | 4 | Early game, income maximization, pet loadouts, journal completion |

## Quick Start (Mac Mini M4)

```bash
# 1. Prerequisites
brew install python@3.12 ollama

# 2. Models (~4.4 GB download)
ollama serve &
ollama pull mistral:7b-instruct-v0.3-q4_K_M
ollama pull nomic-embed-text

# 3. Python setup
cd magic-garden-bot
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 4. Generate & index chunks
python scripts/generate_chunks.py    # → 250 chunks
python scripts/index_chunks.py       # → ChromaDB indexed

# 5a. Interactive chat
python scripts/chat.py

# 5b. API server
uvicorn api.server:app --host 0.0.0.0 --port 8000
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" \
  -d '{"query": "what does butterfly eat"}'
```

## Memory Budget (16 GB)

```
macOS idle .............. ~4.5 GB
Mistral 7B Q4_K_M ....... 4.1 GB  (Metal GPU)
nomic-embed-text ......... 0.3 GB  (CPU)
ChromaDB + Python ........ 0.5 GB
Headroom ................ ~6.5 GB
```

## Testing

```bash
# Offline tests (no Ollama needed)
python tests/test_core.py

# Interactive debug mode (Ollama required)
python scripts/chat.py
# Type 'debug' to see retrieval details per query
```

## Project Structure

```
src/
├── config.py              # Paths, model names, thresholds
├── entity_registry.py     # Display↔internal name resolution (regex)
├── query_analyser.py      # Intent detection + query reformulation
├── conversation_state.py  # Cross-turn entity carry-forward
├── vector_store.py        # ChromaDB + Ollama embedding wrapper
├── llm.py                 # Ollama generation wrapper
└── bot.py                 # Pipeline orchestrator

scripts/
├── generate_chunks.py     # source_truth.json → chunk JSON files
├── index_chunks.py        # Chunks → ChromaDB
└── chat.py                # Interactive CLI

api/
└── server.py              # FastAPI endpoint
```

## Key Design Decisions

- **Ollama over raw llama.cpp**: Auto Metal GPU detection, model management, HTTP API. Saves ~1.5 GB vs PyTorch+sentence-transformers.
- **Regex entity matching before vector search**: 90%+ of queries name a specific entity. Regex resolves it in <1ms, pre-filters ChromaDB search space from 250 to ~10 chunks.
- **No LLM reformulation**: Query analysis is entirely rule-based. Only 1 LLM call per turn (generation).
- **Internal↔display name mapping**: Game source uses `Ambercharged`, players type `Amberbound`. Registry handles bidirectional resolution.
- **Weighted ability pools**: Wiki showed flat ability lists. Source code reveals weighted probability pools per pet, critical for strategy advice.

## Legal & Data

This project is an unaffiliated, non-commercial learning project. It is not
endorsed by, sponsored by, or associated with the developers or publishers of
Magic Garden.

Game data in `data/source_truth.json` and any chunks generated from it were
extracted from the publicly served game client JavaScript for personal study
and to power this local RAG prototype. All game content, entity names, stats,
and mechanics remain the property of their respective owners. The extracted
data is included here only to make the project reproducible and is **not
licensed for redistribution or commercial use**.

The source code in this repository is released under the MIT License (see
`LICENSE`). The MIT License applies only to the code, not to the game data.
If you are a rights holder and would like the data removed, please open an
issue.
