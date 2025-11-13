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
# CHART GENERATION (JSON Spec for Interactive Charts)
# ============================================

def generate_chart(query_result: QueryResult) -> dict | None:
    """
    Generate interactive chart specification (JSON) from query results

    Returns chart spec compatible with Recharts:
    {
        "type": "bar" | "line" | "pie" | "scatter" | "area",
        "data": [{"col1": val1, "col2": val2}, ...],
        "config": {
            "title": "Chart Title",
            "xAxis": {"label": "column_name", "name": "Display Name"},
            "yAxis": {"label": "column_name", "name": "Display Name"},
            "colors": ["#2563eb", "#10b981", ...],
            "theme": "light"
        },
        "recommendation_reason": "Why this chart type was chosen"
    }

    Returns None if data is not suitable for charting
    """
    from datetime import datetime, date

    colunas = query_result.colunas
    dados = query_result.dados

    if not colunas or not dados:
        return None

    # Limit to top 50 rows for better visualization
    display_limit = 50
    if len(dados) > display_limit:
        logger.info(f"Limiting chart to top {display_limit} of {len(dados)} rows")
        dados = dados[:display_limit]

    # Analyze column types
    col_types = _analyze_column_types(colunas, dados)

    # Detect best chart configuration
    chart_config = _detect_chart_config(colunas, dados, col_types)

    if not chart_config:
        logger.debug("Could not determine suitable chart configuration")
        return None

    # Convert data to chart format
    chart_data = _convert_to_chart_data(colunas, dados)

    # Build complete chart specification
    chart_spec = {
        "type": chart_config["type"],
        "data": chart_data,
        "config": {
            "title": chart_config["title"],
            "xAxis": chart_config["xAxis"],
            "yAxis": chart_config["yAxis"],
            "colors": ["#2563eb", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"],
            "theme": "light"
        },
        "recommendation_reason": chart_config["reason"]
    }

    logger.info(f"Chart spec generated ({chart_config['type']}): {chart_config['title']}")

    return chart_spec


def _analyze_column_types(colunas: list[str], dados: list[list]) -> dict:
    """
    Analyze data types of each column

    Returns dict mapping column index to type info:
    {
        0: {"name": "col1", "type": "numeric", "is_integer": True},
        1: {"name": "col2", "type": "string", "is_date": False},
        ...
    }
    """
    from datetime import datetime, date

    col_types = {}

    for i, col_name in enumerate(colunas):
        # Sample values from column (first 10 non-null rows)
        sample = [row[i] for row in dados[:10] if i < len(row) and row[i] is not None]

        if not sample:
            col_types[i] = {"name": col_name, "type": "empty"}
            continue

        # Check if date/datetime
        if any(isinstance(v, (datetime, date)) for v in sample):
            col_types[i] = {"name": col_name, "type": "date", "is_date": True}
            continue

        # Check if numeric
        numeric_count = sum(1 for v in sample if _is_numeric(v))
        if numeric_count >= len(sample) * 0.8:  # 80% numeric
            # Check if integers
            is_integer = all(float(v) == int(float(v)) for v in sample if _is_numeric(v))
            col_types[i] = {
                "name": col_name,
                "type": "numeric",
                "is_integer": is_integer,
                "is_id": "id" in col_name.lower()
            }
            continue

        # Default: string/categorical
        col_types[i] = {"name": col_name, "type": "string"}

    return col_types


def _detect_chart_config(colunas: list[str], dados: list[list], col_types: dict) -> dict | None:
    """
    Detect best chart type and configuration based on data

    Returns:
    {
        "type": "bar" | "line" | "pie" | "scatter" | "area",
        "title": "Chart Title",
        "xAxis": {"label": "column_name", "name": "Display Name"},
        "yAxis": {"label": "column_name", "name": "Display Name"},
        "reason": "Explanation of why this chart was chosen"
    }
    """
    # Find categorical/label column (prefer strings, then dates)
    cat_idx = None
    for i, info in col_types.items():
        if info["type"] == "string":
            cat_idx = i
            break

    if cat_idx is None:
        for i, info in col_types.items():
            if info["type"] == "date":
                cat_idx = i
                break

    # If no categorical column, use first column
    if cat_idx is None:
        cat_idx = 0

    # Find numeric column (prefer non-ID numerics)
    num_idx = None
    for i, info in col_types.items():
        if i == cat_idx:
            continue
        if info["type"] == "numeric" and not info.get("is_id", False):
            num_idx = i
            break

    # Fallback: any numeric column
    if num_idx is None:
        for i, info in col_types.items():
            if i == cat_idx:
                continue
            if info["type"] == "numeric":
                num_idx = i
                break

    if num_idx is None:
        return None

    cat_col = colunas[cat_idx]
    num_col = colunas[num_idx]

    # Determine chart type
    is_timeseries = col_types[cat_idx]["type"] == "date"
    row_count = len(dados)

    if is_timeseries:
        chart_type = "line"
        reason = "Gráfico de linha ideal para visualizar tendências ao longo do tempo"
    elif row_count <= 7:
        chart_type = "pie"
        reason = "Gráfico de pizza ideal para comparar proporções de poucas categorias"
    else:
        chart_type = "bar"
        reason = "Gráfico de barras ideal para comparar valores entre categorias"

    return {
        "type": chart_type,
        "title": f"{num_col} por {cat_col}",
        "xAxis": {
            "label": cat_col,
            "name": _format_column_name(cat_col)
        },
        "yAxis": {
            "label": num_col,
            "name": _format_column_name(num_col)
        },
        "reason": reason
    }


def _convert_to_chart_data(colunas: list[str], dados: list[list]) -> list[dict]:
    """
    Convert tabular data to chart data format

    Input: colunas=["col1", "col2"], dados=[[val1, val2], ...]
    Output: [{"col1": val1, "col2": val2}, ...]
    """
    from datetime import datetime, date

    chart_data = []

    for row in dados:
        row_dict = {}
        for i, col_name in enumerate(colunas):
            if i < len(row):
                value = row[i]

                # Convert dates to ISO strings
                if isinstance(value, (datetime, date)):
                    row_dict[col_name] = value.strftime("%Y-%m-%d")
                # Convert decimals to float
                elif _is_numeric(value):
                    row_dict[col_name] = float(value)
                # Keep strings as-is, truncate if too long
                else:
                    value_str = str(value)
                    row_dict[col_name] = value_str[:100] if len(value_str) > 100 else value_str
            else:
                row_dict[col_name] = None

        chart_data.append(row_dict)

    return chart_data


def _format_column_name(col_name: str) -> str:
    """Format column name for display (convert snake_case to Title Case)"""
    # Replace underscores with spaces and capitalize
    formatted = col_name.replace("_", " ").title()
    return formatted


def _is_numeric(value) -> bool:
    """Check if value is numeric"""
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False
