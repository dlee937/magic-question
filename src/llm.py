"""
Ollama generation wrapper. Single function, single LLM call per query.
"""

import httpx
from .config import (
    OLLAMA_BASE, GENERATION_MODEL, SYSTEM_PROMPT,
    MAX_GENERATION_TOKENS, TEMPERATURE, INTENT_HINTS,
)

_http = httpx.Client(timeout=60.0)


def generate(context: str, query: str, conversation_context: str = "",
             intent: str = "lookup") -> str:
    """Generate a response from retrieved context + user query."""
    full_system = SYSTEM_PROMPT
    if conversation_context:
        full_system += f"\n{conversation_context}"

    hint = INTENT_HINTS.get(intent, "")
    hint_line = f"\nInstruction: {hint}" if hint else ""

    user_message = f"""Context:
{context}

Question: {query}
{hint_line}
Answer concisely using only the context above."""

    resp = _http.post(
        f"{OLLAMA_BASE}/api/chat",
        json={
            "model": GENERATION_MODEL,
            "messages": [
                {"role": "system", "content": full_system},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
            "options": {
                "temperature": TEMPERATURE,
                "num_predict": MAX_GENERATION_TOKENS,
            },
        },
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]
