"""
FastAPI server — single endpoint.
Run: uvicorn api.server:app --host 0.0.0.0 --port 8000
"""

import sys
from pathlib import Path
from fastapi import FastAPI
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.bot import MagicGardenBot
from src.vector_store import VectorStore

app = FastAPI(title="Magic Garden RAG Bot")

# Single shared VectorStore — avoids ChromaDB locking issues
_store = VectorStore()
_sessions: dict[str, MagicGardenBot] = {}
_MAX_SESSIONS = 100


class QueryRequest(BaseModel):
    query: str = Field(max_length=2000)
    session_id: str = "default"


class QueryResponse(BaseModel):
    answer: str
    entities_detected: list[str]
    intent: str
    chunks_retrieved: int
    context_tokens: int


@app.post("/ask", response_model=QueryResponse)
def ask(req: QueryRequest):
    if req.session_id not in _sessions:
        # Evict oldest session if at capacity
        if len(_sessions) >= _MAX_SESSIONS:
            oldest = next(iter(_sessions))
            del _sessions[oldest]
        _sessions[req.session_id] = MagicGardenBot(store=_store)
    bot = _sessions[req.session_id]
    result = bot.debug_answer(req.query)
    return QueryResponse(
        answer=result["answer"],
        entities_detected=result["entities"],
        intent=result["intent"],
        chunks_retrieved=result["chunks_retrieved"],
        context_tokens=result["context_tokens"],
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.delete("/session/{session_id}")
def clear_session(session_id: str):
    if session_id in _sessions:
        del _sessions[session_id]
    return {"cleared": session_id}
