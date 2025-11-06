"""
Stage 1: Intent Analysis
Analyzes user question to determine if it's clear enough or needs clarification
"""
import logging
from app.pipeline.llm.client import call_llm
from app.pipeline.llm.prompts import build_intent_analysis_prompt
from app.pipeline.llm.parsers import parse_json

logger = logging.getLogger(__name__)


class IntentAnalysis:
    """Result of intent analysis (kept for compatibility)"""
    def __init__(self, data: dict):
        self.confidence = data.get("confidence", 0.0)
        self.is_clear = data.get("is_clear", False)
        self.ambiguities = data.get("ambiguities", [])
        self.questions = data.get("questions", [])
        self.schema_mismatch = data.get("schema_mismatch", False)
        self.missing_data = data.get("missing_data", [])

    def dict(self):
        return {
            "confidence": self.confidence,
            "is_clear": self.is_clear,
            "ambiguities": self.ambiguities,
            "questions": self.questions,
            "schema_mismatch": self.schema_mismatch,
            "missing_data": self.missing_data
        }


def analyze_intent(
    pergunta: str,
    esquema: str,
    confidence_threshold: float = 0.7
) -> IntentAnalysis:
    """
    Analyze if user question is clear enough

    Steps:
    1. Build intent analysis prompt
    2. Call LLM
    3. Parse JSON response
    4. Check confidence threshold

    Returns IntentAnalysis with is_clear flag
    """
    logger.info("Analyzing intent")

    # Step 1: Build prompt
    messages = build_intent_analysis_prompt(pergunta, esquema)

    # Step 2: Call LLM
    response = call_llm(messages, temperature=0.2, max_tokens=500)

    # Step 3: Parse JSON
    data = parse_json(response)

    # Step 4: Apply threshold
    data["is_clear"] = data["confidence"] >= confidence_threshold

    logger.info(f"Intent confidence: {data['confidence']:.2f}, is_clear: {data['is_clear']}")

    return IntentAnalysis(data)


def pick_schema(schemas: list[str], pergunta: str) -> str | None:
    """
    Use LLM to pick the best schema from available options

    Args:
        schemas: List of available schema names
        pergunta: User question

    Returns:
        Selected schema name or None if failed
    """
    import re

    logger.info(f"Picking schema from {len(schemas)} options")

    # Build simple prompt
    messages = [
        {
            "role": "system",
            "content": "Você escolhe UM schema dentre os permitidos. Responda com uma única palavra (nome exato), sem explicações."
        },
        {
            "role": "user",
            "content": f"Schemas permitidos: {', '.join(schemas)}\nPergunta: {pergunta}\nResponda apenas com o schema."
        }
    ]

    try:
        # Call LLM
        response = call_llm(messages, temperature=0.0, max_tokens=10)

        # Extract schema name
        candidates = re.findall(r"[a-zA-Z0-9_]+", response)
        if candidates:
            name = candidates[0].lower()
            for s in schemas:
                if s.lower() == name:
                    logger.info(f"Selected schema: {s}")
                    return s
    except Exception as e:
        logger.warning(f"Schema selection via LLM failed: {e}")

    return None


def build_clarified_question(
    original_question: str,
    clarifications: dict
) -> str:
    """
    Build clarified question from user's answers

    Takes original question and adds clarification details
    Returns natural language question with context
    """
    logger.info(f"Building clarified question from: {clarifications}")

    parts = [original_question]

    # Map common clarification IDs to natural language
    time_period_map = {
        "today": "de hoje",
        "yesterday": "de ontem",
        "last_week": "da última semana",
        "last_month": "do último mês",
        "last_year": "do último ano",
        "this_month": "deste mês",
        "this_year": "deste ano"
    }

    scope_map = {
        "all": "todos",
        "by_product": "por produto",
        "by_region": "por região",
        "by_customer": "por cliente",
        "by_category": "por categoria"
    }

    # Add time period
    if time_period := clarifications.get("time_period"):
        parts.append(time_period_map.get(time_period, time_period))

    # Add scope
    if scope := clarifications.get("scope"):
        parts.append(scope_map.get(scope, scope))

    # Add any other clarifications as-is
    for key, value in clarifications.items():
        if key not in ["time_period", "scope"] and value:
            parts.append(str(value))

    clarified = " ".join(parts)
    logger.info(f"Clarified question: {clarified}")

    return clarified
