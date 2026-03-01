"""
FastAPI server — single endpoint.
Run: uvicorn api.server:app --host 0.0.0.0 --port 8000
"""

import sys
from pathlib import Path
from fastapi import FastAPI
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.bot import MagicGardenBot

app = FastAPI(title="Magic Garden RAG Bot")
_sessions: dict[str, MagicGardenBot] = {}


class QueryRequest(BaseModel):
    query: str
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
        _sessions[req.session_id] = MagicGardenBot()
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
