"""
Detects user intent and reformulates queries for embedding search.
Zero LLM cost — regex patterns + entity registry.
"""

import re
from dataclasses import dataclass, field
from .entity_registry import EntityMatch, find_entities


@dataclass
class QueryAnalysis:
    raw_query: str
    entities: list[EntityMatch]
    intent: str
    embedding_query: str
    metadata_filters: dict = field(default_factory=dict)


# (regex, intent_name, embedding_keywords)
_INTENT_PATTERNS: list[tuple[str, str, str]] = [
    (r'\b(eat|feed|diet|food|hungry|hunger)\b', 'diet', 'diet food crops feeding'),
    (r'\b(best|optimal|recommend|should i|strategy|guide|tier|rank)\b', 'strategy', 'strategy guide best optimal'),
    (r'\b(sell|price|worth|value|coins?|how much|money|income|profit|rich)\b', 'selling', 'sell price coins value'),
    (r'\b(abilit\w*|skill|power|does? it do|can .+ do|what does)\b', 'abilities', 'abilities effects skills'),
    (r'\b(hatch|egg|spawn|chance|percent)\b', 'hatching', 'egg hatch spawn chance'),
    (r'\b(grow|time|long|fast|slow|mature|regrow|harvest)\b', 'growing', 'grow time harvest mature'),
    (r'\b(mutat\w*|frozen|wet|chilled|gold|rainbow|amberbound|dawnbound|dawnlit|amberlit|thunderstruck)\b',
     'mutation', 'mutation multiplier weather'),
    (r'\b(weather|rain|snow|thunderstorm|dawn|amber moon|event)\b', 'weather', 'weather event mutation'),
    (r'\b(journal|variants?|collection|complet\w*)\b', 'journal', 'journal variant collection completion'),
    (r'\b(stack|multiply|combin\w*|additive|multiplicative|maximum)\b',
     'multipliers', 'mutation stacking multiplier combination'),
    (r'\b(strength|str|xp|level|experience)\b', 'mechanics', 'strength STR XP mechanics'),
    (r'\b(shop|buy|purchase|store|restock)\b', 'shopping', 'shop buy purchase restock'),
    (r'\b(compare|vs|versus|difference|better)\b', 'comparison', 'compare difference'),
]


# Maps intent → query_intents metadata values to include via $or
_INTENT_QUERY_INTENTS: dict[str, list[str]] = {
    "diet": ["diet"],
    "selling": ["selling"],
    "abilities": ["abilities"],
    "hatching": ["hatching"],
    "growing": ["growing"],
    "mutation": ["mutation", "multipliers"],
    "weather": ["mutation"],
    "multipliers": ["multipliers", "mutation"],
    "comparison": ["comparison"],
    "journal": ["strategy"],  # journal tips live in strategy chunks
}

# Intents that should also filter by chunk layer
_INTENT_LAYER: dict[str, str] = {
    "strategy": "strategy",
}


def _build_filters(entities: list[EntityMatch], intent: str) -> dict | None:
    """Build a ChromaDB where clause combining entity + intent filters with $or."""
    conditions: list[dict] = []

    # Entity-specific conditions: match chunks about this entity
    if entities:
        primary = entities[0]
        conditions.append({"entity_name": {"$eq": primary.display_name}})
        conditions.append({"internal_id": {"$eq": primary.internal_id}})

    # Intent-based conditions: match chunks tagged for this query type
    intent_values = _INTENT_QUERY_INTENTS.get(intent)
    if intent_values:
        for val in intent_values:
            conditions.append({"query_intents": {"$eq": val}})

    # Layer-based conditions (e.g., strategy → strategy layer)
    layer = _INTENT_LAYER.get(intent)
    if layer:
        conditions.append({"layer": {"$eq": layer}})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$or": conditions}


def analyse(query: str, carry_forward_entity: EntityMatch | None = None) -> QueryAnalysis:
    """Analyse user query → structured retrieval instructions."""
    entities = find_entities(query)

    # Inject carry-forward if no entities found
    if not entities and carry_forward_entity:
        entities = [carry_forward_entity]

    # Detect intent
    intent = 'lookup'
    intent_suffix = ''
    query_lower = query.lower()
    for pattern, intent_name, suffix in _INTENT_PATTERNS:
        if re.search(pattern, query_lower):
            intent = intent_name
            intent_suffix = suffix
            break

    # Build embedding query
    entity_names = ' '.join(e.display_name for e in entities)
    embedding_query = f"{entity_names} {intent_suffix}".strip()
    if not embedding_query:
        embedding_query = query

    # Build ChromaDB where clause from entities + intent
    filters = _build_filters(entities, intent)

    return QueryAnalysis(
        raw_query=query,
        entities=entities,
        intent=intent,
        embedding_query=embedding_query,
        metadata_filters=filters or {},
    )
