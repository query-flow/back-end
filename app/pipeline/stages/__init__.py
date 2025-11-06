"""
Pipeline stages (ordered execution flow)

1. intent_analyzer → Analyze user intent
2. sql_generator → Generate SQL (with voting)
3. sql_validator → Validate SQL
4. result_enricher → Generate insights + chart
"""
from app.pipeline.stages.intent_analyzer import (
    analyze_intent,
    pick_schema,
    build_clarified_question,
    IntentAnalysis
)
from app.pipeline.stages.sql_generator import (
    generate_sql,
    generate_sql_parallel,
    correct_sql
)
from app.pipeline.stages.sql_validator import (
    vote_best_sql,
    validate_sql_against_rules,
    select_best_candidate
)
from app.pipeline.stages.result_enricher import (
    generate_insights,
    generate_chart,
    QueryResult,
    InsightsGenerated
)

__all__ = [
    # Stage 1: Intent
    "analyze_intent",
    "pick_schema",
    "build_clarified_question",
    "IntentAnalysis",
    # Stage 2: SQL Generation
    "generate_sql",
    "generate_sql_parallel",
    "correct_sql",
    # Stage 3: Validation
    "vote_best_sql",
    "validate_sql_against_rules",
    "select_best_candidate",
    # Stage 5: Enrichment
    "generate_insights",
    "generate_chart",
    "QueryResult",
    "InsightsGenerated",
]
