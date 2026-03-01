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
    def __init__(self):
        self.store = VectorStore()
        self.conversation = ConversationState()

    def answer(self, user_query: str) -> str:
        # ── Stage 1: Query Analysis (free) ──
        carry = self.conversation.get_carry_forward()
        analysis = analyse(user_query, carry_forward_entity=carry)

        # ── Stage 2: Retrieval (~50ms) ──
        chunks = self.store.retrieve(
            query=analysis.embedding_query,
            metadata_filters=analysis.metadata_filters if analysis.entities else None,
        )

        # Fall back to unfiltered if nothing matched
        if not chunks:
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
            )

        # ── Stage 5: Update State (free) ──
        primary = analysis.entities[0] if analysis.entities else None
        self.conversation.record_turn(
            query=user_query,
            primary_entity=primary,
            intent=analysis.intent,
            all_entities=analysis.entities,
        )

        return response

    def debug_answer(self, user_query: str) -> dict:
        """Like answer() but returns debug info alongside the response."""
        carry = self.conversation.get_carry_forward()
        analysis = analyse(user_query, carry_forward_entity=carry)

        chunks = self.store.retrieve(
            query=analysis.embedding_query,
            metadata_filters=analysis.metadata_filters if analysis.entities else None,
        )
        if not chunks:
            chunks = self.store.retrieve(query=analysis.embedding_query)

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

        if not context.strip():
            response = "I don't have information about that in my game database."
        else:
            response = generate(context=context, query=user_query, conversation_context=conv_line)

        primary = analysis.entities[0] if analysis.entities else None
        self.conversation.record_turn(
            query=user_query, primary_entity=primary,
            intent=analysis.intent, all_entities=analysis.entities,
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
