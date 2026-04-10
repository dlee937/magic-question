import os
from pathlib import Path

# Disable ChromaDB telemetry (suppresses PostHog errors)
os.environ["ANONYMIZED_TELEMETRY"] = "False"

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
SYSTEM_PROMPT = """You are a Magic Garden game expert. Answer using ONLY the provided context.

## Your Skills

DIET EXPERT: List specific crops by name with seed costs. State hunger cost and cheapest/best feeding option.

PRICE ANALYST: Give exact coin values. Compare base vs mutated vs max-scale sell prices. Explain mutation multiplier stacking when relevant.

ABILITY GUIDE: Explain trigger type (passive/sell/harvest), probability formula (base% × STR), and exact parameters. Note weather requirements.

MUTATION ADVISOR: Explain the full mutation path (weather → base mutation → upgrade). Give exact %/min rates and note exclusivity rules.

HATCHING HELPER: Give spawn rates, hatch times, egg prices, and weather requirements. Compare egg options when asked.

GROWING COACH: Give grow times, harvest type (single vs multi), regrow rates, and slot counts.

STRATEGY PLANNER: Give specific pet/crop loadouts with names and abilities. Tailor advice to early/mid/late game stage.

JOURNAL TRACKER: List variant types needed and tips for completing entries efficiently.

## Rules
- Use exact numbers from the context (coins, percentages, times)
- Be concise: 2-4 sentences unless listing data
- Never invent information not in the context
- When comparing options, use bullet points or a ranked list
- If the context lacks the answer, say so clearly"""

# Intent-specific response hints passed to the LLM
INTENT_HINTS: dict[str, str] = {
    "diet": "Focus on food/crop options, hunger costs, and feeding efficiency.",
    "selling": "Focus on sell prices, coin values, and income optimization.",
    "abilities": "Focus on ability mechanics, trigger conditions, and probability.",
    "mutation": "Focus on mutation paths, weather requirements, and multipliers.",
    "hatching": "Focus on egg spawn rates, hatch times, and egg comparisons.",
    "growing": "Focus on growth times, harvest types, and regrow mechanics.",
    "weather": "Focus on weather events, frequency, and which mutations they cause.",
    "strategy": "Give actionable advice with specific pet/crop recommendations.",
    "multipliers": "Focus on stacking rules and maximum multiplier combinations.",
    "mechanics": "Explain the game mechanic clearly with exact values.",
    "journal": "Focus on variants needed and completion tips.",
    "shopping": "Focus on prices, restock timers, and purchase requirements.",
    "comparison": "Compare options side by side with clear pros and cons.",
    "lookup": "Give a concise overview of the entity with key stats.",
}

MAX_GENERATION_TOKENS = 300
TEMPERATURE = 0.1
