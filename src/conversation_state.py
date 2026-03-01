"""
Tracks entities and context across conversation turns.
Enables pronoun resolution and follow-up queries.
Zero LLM cost — pure state management.
"""

from dataclasses import dataclass, field
from collections import deque
from .entity_registry import EntityMatch
from .config import ENTITY_CARRY_FORWARD_TURNS, MAX_CONVERSATION_TURNS


@dataclass
class Turn:
    query: str
    primary_entity: EntityMatch | None
    intent: str
    mentioned_entities: list[EntityMatch] = field(default_factory=list)


class ConversationState:
    def __init__(self):
        self.turns: deque[Turn] = deque(maxlen=MAX_CONVERSATION_TURNS)
        self.active_entity: EntityMatch | None = None
        self.active_entity_age: int = 0

    def get_carry_forward(self) -> EntityMatch | None:
        """Get entity to inject if next query has no explicit entity."""
        if self.active_entity and self.active_entity_age < ENTITY_CARRY_FORWARD_TURNS:
            return self.active_entity
        return None

    def record_turn(self, query: str, primary_entity: EntityMatch | None,
                    intent: str, all_entities: list[EntityMatch]):
        """Record a completed turn and update state."""
        self.turns.append(Turn(
            query=query,
            primary_entity=primary_entity,
            intent=intent,
            mentioned_entities=all_entities,
        ))
        if primary_entity:
            self.active_entity = primary_entity
            self.active_entity_age = 0
        else:
            self.active_entity_age += 1

    def get_context_line(self) -> str:
        """One-line conversation summary for LLM prompt (~20 tokens)."""
        if not self.turns:
            return ""
        last = self.turns[-1]
        if last.primary_entity:
            names = ', '.join(e.display_name for e in last.mentioned_entities)
            return f"Previous topic: {names} ({last.intent})"
        return ""
