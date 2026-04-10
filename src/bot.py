"""
Main pipeline: query → analyse → retrieve → generate.
One LLM call per turn. Everything else is deterministic Python.
"""

from .query_analyser import analyse
from .conversation_state import ConversationState
from .vector_store import VectorStore
from .llm import generate
from .config import MAX_CONTEXT_TOKENS


class MagicGardenBot:
    def __init__(self, store: VectorStore | None = None):
        self.store = store or VectorStore()
        self.conversation = ConversationState()

    def _run_pipeline(self, user_query: str) -> dict:
        """Core pipeline: analyse → retrieve → assemble → generate."""
        # ── Stage 1: Query Analysis (free) ──
        carry = self.conversation.get_carry_forward()
        analysis = analyse(user_query, carry_forward_entity=carry)

        # ── Stage 2: Retrieval (~50ms) ──
        chunks = self.store.retrieve(
            query=analysis.embedding_query,
            metadata_filters=analysis.metadata_filters or None,
        )

        # Fall back to unfiltered if filters were too restrictive
        if not chunks and analysis.metadata_filters:
            chunks = self.store.retrieve(query=analysis.embedding_query)

        # ── Stage 3: Context Assembly (free) ──
        context_parts = []
        token_estimate = 0
        for chunk in chunks:
            chunk_tokens = len(chunk["text"].split()) * 1.3
            if token_estimate + chunk_tokens > MAX_CONTEXT_TOKENS:
                break
            context_parts.append(chunk["text"])
            token_estimate += chunk_tokens

        context = "\n\n".join(context_parts)
        conv_line = self.conversation.get_context_line()

        # ── Stage 4: Generation (~1-2s on Mac Mini M4) ──
        if not context.strip():
            response = "I don't have information about that in my game database."
        else:
            response = generate(
                context=context,
                query=user_query,
                conversation_context=conv_line,
                intent=analysis.intent,
            )

        # ── Stage 5: Update State (free) ──
        primary = analysis.entities[0] if analysis.entities else None
        self.conversation.record_turn(
            query=user_query,
            primary_entity=primary,
            intent=analysis.intent,
            all_entities=analysis.entities,
        )

        return {
            "answer": response,
            "entities": [e.display_name for e in analysis.entities],
            "intent": analysis.intent,
            "embedding_query": analysis.embedding_query,
            "chunks_retrieved": len(chunks),
            "context_tokens": int(token_estimate),
            "conversation_context": conv_line,
        }

    def answer(self, user_query: str) -> str:
        return self._run_pipeline(user_query)["answer"]

    def debug_answer(self, user_query: str) -> dict:
        """Like answer() but returns debug info alongside the response."""
        return self._run_pipeline(user_query)
