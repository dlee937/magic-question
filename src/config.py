from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CHUNKS_DIR = DATA_DIR / "chunks"
SOURCE_TRUTH = DATA_DIR / "source_truth.json"
CHROMA_DIR = DATA_DIR / "chromadb"

# Ollama endpoints
OLLAMA_BASE = "http://localhost:11434"
GENERATION_MODEL = "mistral:7b-instruct-v0.3-q4_K_M"
EMBEDDING_MODEL = "nomic-embed-text"

# Retrieval
MAX_CHUNKS_RETRIEVED = 6
SIMILARITY_THRESHOLD = 0.30
MAX_CONTEXT_TOKENS = 1200

# Conversation
MAX_CONVERSATION_TURNS = 10
ENTITY_CARRY_FORWARD_TURNS = 3

# Generation
SYSTEM_PROMPT = """You are a helpful Magic Garden game assistant. Answer questions
using ONLY the provided context. If the context doesn't contain the answer, say so.
Be concise and specific. Use exact numbers from the context.
Do not make up information. Do not add disclaimers about being an AI."""

MAX_GENERATION_TOKENS = 300
TEMPERATURE = 0.1
