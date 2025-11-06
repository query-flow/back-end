"""
Stage 5: Result Enrichment
Generates business insights and charts from query results
"""
import logging
from pydantic import BaseModel
from app.pipeline.llm.client import call_llm
from app.pipeline.llm.prompts import build_insights_prompt

logger = logging.getLogger(__name__)


# ============================================
# DATA MODELS (kept for compatibility)
# ============================================

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
