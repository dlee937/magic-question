"""
Ollama generation wrapper. Single function, single LLM call per query.
"""

import httpx
from .config import (
    OLLAMA_BASE, GENERATION_MODEL, SYSTEM_PROMPT,
    MAX_GENERATION_TOKENS, TEMPERATURE,
)

_http = httpx.Client(timeout=60.0)


def generate(context: str, query: str, conversation_context: str = "") -> str:
    """Generate a response from retrieved context + user query."""
    full_system = SYSTEM_PROMPT
    if conversation_context:
        full_system += f"\n{conversation_context}"

    user_message = f"""Context:
{context}

Question: {query}

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
