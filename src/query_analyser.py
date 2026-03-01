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
    (r'\b(sell|price|worth|value|coins?|how much|money|income|profit|rich)\b', 'selling', 'sell price coins value'),
    (r'\b(abilit|skill|power|does? it do|can .+ do|what does)\b', 'abilities', 'abilities effects skills'),
    (r'\b(hatch|egg|spawn|chance|percent)\b', 'hatching', 'egg hatch spawn chance'),
    (r'\b(grow|time|long|fast|slow|mature|regrow|harvest)\b', 'growing', 'grow time harvest mature'),
    (r'\b(mutat|frozen|wet|chilled|gold|rainbow|amberbound|dawnbound|dawnlit|amberlit|thunderstruck)\b',
     'mutation', 'mutation multiplier weather'),
    (r'\b(weather|rain|snow|thunderstorm|dawn|amber moon|event)\b', 'weather', 'weather event mutation'),
    (r'\b(best|optimal|recommend|should i|strategy|guide|tier|rank)\b', 'strategy', 'strategy guide best optimal'),
    (r'\b(journal|variant|collection|complet)\b', 'journal', 'journal variant collection completion'),
    (r'\b(stack|multiply|combin|additive|multiplicative|maximum)\b',
     'multipliers', 'mutation stacking multiplier combination'),
    (r'\b(strength|str|xp|level|experience)\b', 'mechanics', 'strength STR XP mechanics'),
    (r'\b(shop|buy|purchase|store|restock)\b', 'shopping', 'shop buy purchase restock'),
    (r'\b(compare|vs|versus|difference|better)\b', 'comparison', 'compare difference'),
]


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

    # Metadata filters for ChromaDB pre-filtering
    filters: dict = {}
    if entities:
        primary = entities[0]
        filters["entity_type"] = primary.entity_type

    return QueryAnalysis(
        raw_query=query,
        entities=entities,
        intent=intent,
        embedding_query=embedding_query,
        metadata_filters=filters,
    )
