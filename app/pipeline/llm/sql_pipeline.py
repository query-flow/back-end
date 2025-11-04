"""SQL generation pipeline with clarification"""
import logging
from pydantic import BaseModel
from app.pipeline.llm.llm_helpers import (
    call_llm,
    build_intent_analysis_prompt,
    build_sql_generation_prompt,
    build_sql_correction_prompt,
    build_insights_prompt,
    parse_json,
    parse_sql
)

logger = logging.getLogger(__name__)


# ============================================
# DATA MODELS
# ============================================

class IntentAnalysis(BaseModel):
    """Result of intent analysis"""
    confidence: float
    is_clear: bool
    ambiguities: list[str]
    questions: list[dict]
    # Schema validation
    schema_mismatch: bool = False
    missing_data: list[str] = []


class QueryResult(BaseModel):
    """SQL query execution result"""
    colunas: list[str]
    dados: list[list]
    sql: str
    schema: str


class InsightsGenerated(BaseModel):
    """Output after generating insights"""
    pergunta: str
    query_result: QueryResult
    insights: str | None = None
    biz_context: str = ""
    generate_chart: bool = True


# ============================================
# INTENT ANALYSIS
# ============================================

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

    return IntentAnalysis(**data)


# ============================================
# SQL GENERATION
# ============================================

def generate_sql(
    pergunta: str,
    esquema: str,
    limit: int = 100
) -> str:
    """
    Generate SQL from natural language

    Simple 3-step process:
    1. Build SQL generation prompt
    2. Call LLM
    3. Parse SQL from response

    Returns SQL string
    """
    logger.info(f"Generating SQL for: '{pergunta[:50]}...'")

    # Step 1: Build prompt
    messages = build_sql_generation_prompt(pergunta, esquema, limit)

    # Step 2: Call LLM
    response = call_llm(messages, temperature=0.1, max_tokens=800)

    # Step 3: Parse SQL
    sql = parse_sql(response)

    logger.info(f"Generated SQL: {sql[:100]}...")

    return sql


def correct_sql(
    sql_original: str,
    erro: str,
    esquema: str,
    limit: int = 100
) -> str:
    """
    Correct SQL that failed execution

    Simple 3-step process:
    1. Build correction prompt
    2. Call LLM
    3. Parse corrected SQL

    Returns corrected SQL string
    """
    logger.info("Correcting SQL after error")

    # Step 1: Build prompt
    messages = build_sql_correction_prompt(sql_original, erro, esquema, limit)

    # Step 2: Call LLM
    response = call_llm(messages, temperature=0.1, max_tokens=800)

    # Step 3: Parse SQL
    corrected_sql = parse_sql(response)

    logger.info(f"Corrected SQL: {corrected_sql[:100]}...")

    return corrected_sql


# ============================================
# INSIGHTS GENERATION
# ============================================

def generate_insights(
    pergunta: str,
    colunas: list[str],
    dados: list[list],
    biz_context: str = ""
) -> str:
    """
    Generate business insights from query results

    Simple 3-step process:
    1. Build insights prompt
    2. Call LLM
    3. Return insights text

    Returns insights string
    """
    logger.info("Generating insights")

    # Step 1: Build prompt
    # Limit to first 10 rows for insights
    dados_sample = dados[:10]
    messages = build_insights_prompt(pergunta, colunas, dados_sample, biz_context)

    # Step 2: Call LLM
    response = call_llm(messages, temperature=0.2, max_tokens=500)

    # Step 3: Return insights
    logger.info("Insights generated successfully")

    return response.strip()


# ============================================
# SCHEMA SELECTION
# ============================================

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


# ============================================
# CLARIFICATION HELPER
# ============================================

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


# ============================================
# CHART GENERATION
# ============================================

def generate_chart(query_result: QueryResult) -> str | None:
    """
    Generate bar chart from query results using matplotlib

    Simple heuristic:
    - First string column = category (X axis)
    - First numeric column = values (Y axis)

    Returns base64 encoded PNG or None if failed
    """
    import base64
    import os
    from io import BytesIO

    # Set matplotlib backend
    os.environ.setdefault("MPLBACKEND", "Agg")

    try:
        import matplotlib
        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not available")
        return None

    colunas = query_result.colunas
    dados = query_result.dados

    if not colunas or not dados:
        return None

    # Find categorical column (first string-ish)
    cat_idx = 0
    for i, col in enumerate(colunas):
        sample = [row[i] if i < len(row) else None for row in dados[:5]]
        non_numeric = sum(1 for v in sample if v and not _is_numeric(v))
        if non_numeric >= len(sample) // 2:
            cat_idx = i
            break

    # Find numerical column (first numeric, different from category)
    num_idx = None
    for j, col in enumerate(colunas):
        if j == cat_idx:
            continue
        sample = [row[j] if j < len(row) else None for row in dados[:5]]
        if all(_is_numeric(v) for v in sample if v is not None):
            num_idx = j
            break

    if num_idx is None:
        logger.debug("Could not detect numerical column for chart")
        return None

    # Extract data
    labels = [str(row[cat_idx]) if cat_idx < len(row) else "" for row in dados]
    values = []
    for row in dados:
        try:
            val = float(row[num_idx]) if num_idx < len(row) else 0.0
            values.append(val)
        except (ValueError, TypeError):
            values.append(0.0)

    # Create chart
    fig = plt.figure(figsize=(10, 6))
    plt.bar(labels, values, color='steelblue')
    plt.xticks(rotation=45, ha="right")
    plt.title(f"{colunas[num_idx]} por {colunas[cat_idx]}")
    plt.tight_layout()

    # Convert to base64
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)

    logger.info(f"Chart generated: {colunas[num_idx]} por {colunas[cat_idx]}")

    return base64.b64encode(buf.getvalue()).decode()


def _is_numeric(value) -> bool:
    """Check if value is numeric"""
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False
