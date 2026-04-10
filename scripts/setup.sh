#!/bin/bash
# ════════════════════════════════════════════════════════
# Magic Garden RAG Bot — Mac Mini M4 Setup
# Run: chmod +x scripts/setup.sh && ./scripts/setup.sh
# ════════════════════════════════════════════════════════
set -e

echo "╔══════════════════════════════════════╗"
echo "║  Magic Garden RAG Bot — Setup        ║"
echo "╚══════════════════════════════════════╝"

# ── 1. Check/install Homebrew ──
if ! command -v brew &>/dev/null; then
    echo "→ Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# ── 2. Install system deps ──
echo "→ Installing Python 3.12..."
brew install python@3.12 2>/dev/null || true

# ── 3. Install Ollama ──
if ! command -v ollama &>/dev/null; then
    echo "→ Installing Ollama..."
    brew install ollama
fi

# ── 4. Start Ollama daemon ──
echo "→ Starting Ollama..."
if ! pgrep -x "ollama" > /dev/null; then
    ollama serve &>/dev/null &
    sleep 3
fi

# ── 5. Pull models ──
echo "→ Pulling Mistral 7B (~4.1 GB)..."
ollama pull mistral:7b-instruct-v0.3-q4_K_M

echo "→ Pulling nomic-embed-text (~274 MB)..."
ollama pull nomic-embed-text

# ── 6. Python venv ──
echo "→ Setting up Python environment..."
cd "$(dirname "$0")/.."
python3.12 -m venv .venv 2>/dev/null || python3 -m venv .venv
source .venv/bin/activate
pip install --quiet -r requirements.txt

# ── 7. Generate chunks ──
echo "→ Generating chunks from game data..."
python scripts/generate_chunks.py

# ── 8. Index into ChromaDB ──
echo "→ Indexing chunks (this takes ~2-3 min for embedding)..."
ANONYMIZED_TELEMETRY=False python scripts/index_chunks.py

echo ""
echo "╔══════════════════════════════════════╗"
echo "║  Setup complete!                     ║"
echo "║                                      ║"
echo "║  To chat:                            ║"
echo "║    source .venv/bin/activate          ║"
echo "║    python scripts/chat.py            ║"
echo "║                                      ║"
echo "║  To start API server:                ║"
echo "║    source .venv/bin/activate          ║"
echo "║    uvicorn api.server:app \\           ║"
echo "║      --host 0.0.0.0 --port 8000     ║"
echo "╚══════════════════════════════════════╝"
