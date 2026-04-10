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
    assert "Horse" not in ids


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

    # 3 turns with no entity = carry-forward expires (age reaches ENTITY_CARRY_FORWARD_TURNS)
    for i in range(3):
        state.record_turn(f"question {i}", None, "lookup", [])

    carry = state.get_carry_forward()
    assert carry is None


def test_carry_forward_still_active():
    """Carry-forward should still work within the window."""
    state = ConversationState()
    from src.entity_registry import EntityMatch
    entity = EntityMatch("Butterfly", "Butterfly", "pet")
    state.record_turn("about butterfly", entity, "lookup", [entity])

    # 2 turns without entity — still within window
    for i in range(2):
        state.record_turn(f"question {i}", None, "lookup", [])

    carry = state.get_carry_forward()
    assert carry is not None
    assert carry.internal_id == "Butterfly"


def test_carry_forward_inject():
    """Query analyser should use carry-forward when no entity found."""
    from src.entity_registry import EntityMatch
    carry = EntityMatch("Turkey", "Turkey", "pet")
    result = analyse("what does it eat", carry_forward_entity=carry)
    assert any(e.internal_id == "Turkey" for e in result.entities)
    assert result.intent == "diet"


# ── Intent-Based Filter Tests ──

def test_diet_filter_has_or():
    """Diet query with entity should produce $or clause."""
    result = analyse("what does butterfly eat")
    f = result.metadata_filters
    assert "$or" in f
    conditions = f["$or"]
    # Should include entity_name match + query_intents match
    keys_used = {list(c.keys())[0] for c in conditions}
    assert "entity_name" in keys_used
    assert "query_intents" in keys_used


def test_strategy_filter_has_layer():
    """Strategy query with no entity should filter by strategy layer."""
    result = analyse("best early game strategy")
    f = result.metadata_filters
    # Single condition — no $or wrapper needed
    assert f == {"layer": {"$eq": "strategy"}}


def test_mutation_filter_includes_multipliers():
    """Mutation query should also pull multiplier chunks."""
    result = analyse("how do I get frozen mutation")
    f = result.metadata_filters
    assert "$or" in f
    intent_vals = [c["query_intents"]["$eq"] for c in f["$or"] if "query_intents" in c]
    assert "mutation" in intent_vals
    assert "multipliers" in intent_vals


def test_lookup_no_intent_filter():
    """Plain lookup with entity but no intent keywords → entity-only filter."""
    result = analyse("tell me about butterfly")
    f = result.metadata_filters
    # Should still have entity filters via $or
    assert "$or" in f
    conditions = f["$or"]
    keys_used = {list(c.keys())[0] for c in conditions}
    assert "entity_name" in keys_used
    # No query_intents since lookup has no mapping
    assert "query_intents" not in keys_used


def test_no_entity_no_intent_empty_filter():
    """Generic query with no entity and no intent → empty filter."""
    result = analyse("hello")
    assert result.metadata_filters == {}


# ── Calculator Module Tests ──

def test_calculator_basic():
    from src.calculator import calculate_sell_price
    result = calculate_sell_price("Bamboo", colour_mutation="Gold", at_max_scale=True)
    # Bamboo: 500,000 base × 2x scale × Gold ×25 = 25,000,000
    assert result.final_price == 25_000_000


def test_calculator_stacking():
    from src.calculator import calculate_sell_price
    result = calculate_sell_price(
        "Bamboo", weather_mutation="Frozen", lunar_mutation="Ambercharged",
        colour_mutation="Rainbow", at_max_scale=True,
    )
    # Bamboo: 500,000 × 2x scale = 1,000,000
    # Frozen(6) + Amberbound(10) additive = ×15, × Rainbow(50) = ×750
    # 1,000,000 × 750 = 750,000,000
    assert result.final_price == 750_000_000


def test_calculator_max():
    from src.calculator import max_sell_price
    result = max_sell_price("Bamboo")
    # 500,000 × 2 × 750 × 1.5 × 1.5 = 1,687,500,000
    assert result.final_price == 1_687_500_000


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
