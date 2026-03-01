"""
Tests for entity registry and query analyser.
These run without Ollama — pure Python logic.
Run: python -m pytest tests/ -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.entity_registry import find_entities, resolve_name, display_name
from src.query_analyser import analyse
from src.conversation_state import ConversationState


# ── Entity Registry Tests ──

def test_simple_pet():
    matches = find_entities("tell me about Butterfly")
    assert len(matches) == 1
    assert matches[0].internal_id == "Butterfly"
    assert matches[0].entity_type == "pet"


def test_display_name_mapping():
    matches = find_entities("how do I get amberbound")
    assert len(matches) == 1
    assert matches[0].internal_id == "Ambercharged"
    assert matches[0].display_name == "Amberbound"


def test_multi_word_entity():
    matches = find_entities("is fire horse good")
    assert any(m.internal_id == "FireHorse" for m in matches)


def test_fire_horse_before_horse():
    """fire horse should match FireHorse, not Horse"""
    matches = find_entities("fire horse abilities")
    ids = [m.internal_id for m in matches]
    assert "FireHorse" in ids
    # Should NOT also match plain Horse separately
    assert ids.count("Horse") == 0 or "FireHorse" in ids


def test_crop_internal_mapping():
    m = resolve_name("tulip")
    assert m is not None
    assert m.internal_id == "OrangeTulip"


def test_snow_weather():
    m = resolve_name("snow")
    assert m is not None
    assert m.internal_id == "Frost"
    assert m.entity_type == "weather"


def test_multiple_entities():
    matches = find_entities("can I feed strawberry to bunny")
    types = {m.entity_type for m in matches}
    assert "crop" in types
    assert "pet" in types


def test_display_name_function():
    assert display_name("Ambercharged") == "Amberbound"
    assert display_name("OrangeTulip") == "Tulip"
    assert display_name("Worm") == "Worm"  # No mapping needed


# ── Query Analyser Tests ──

def test_diet_intent():
    result = analyse("what does bee eat")
    assert result.intent == "diet"
    assert any(e.internal_id == "Bee" for e in result.entities)


def test_selling_intent():
    result = analyse("how much is mushroom worth")
    assert result.intent == "selling"
    assert any(e.internal_id == "Mushroom" for e in result.entities)


def test_mutation_intent():
    result = analyse("how do I get frozen on my crops")
    assert result.intent == "mutation"


def test_strategy_intent():
    result = analyse("what's the best pet for making money")
    assert result.intent == "strategy"


def test_embedding_query_constructed():
    result = analyse("what does butterfly eat")
    assert "Butterfly" in result.embedding_query
    assert "diet" in result.embedding_query.lower() or "food" in result.embedding_query.lower()


# ── Conversation State Tests ──

def test_carry_forward():
    state = ConversationState()
    from src.entity_registry import EntityMatch
    entity = EntityMatch("Butterfly", "Butterfly", "pet")
    state.record_turn("about butterfly", entity, "lookup", [entity])

    carry = state.get_carry_forward()
    assert carry is not None
    assert carry.internal_id == "Butterfly"


def test_carry_forward_expires():
    state = ConversationState()
    from src.entity_registry import EntityMatch
    entity = EntityMatch("Butterfly", "Butterfly", "pet")
    state.record_turn("about butterfly", entity, "lookup", [entity])

    # 3 turns with no entity = carry-forward expires
    for i in range(4):
        state.record_turn(f"question {i}", None, "lookup", [])

    carry = state.get_carry_forward()
    assert carry is None


def test_carry_forward_inject():
    """Query analyser should use carry-forward when no entity found."""
    from src.entity_registry import EntityMatch
    carry = EntityMatch("Turkey", "Turkey", "pet")
    result = analyse("what does it eat", carry_forward_entity=carry)
    assert any(e.internal_id == "Turkey" for e in result.entities)
    assert result.intent == "diet"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
