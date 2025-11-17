"""
Chart Generation Service using LLM
Generates D3.js visualizations from query results
"""
import json
import logging
from typing import Dict, Any, List, Optional
from app.pipeline.llm.client import call_llm
from app.pipeline.llm.parsers import parse_json

logger = logging.getLogger(__name__)


class ChartService:
    """
    Service for generating chart specifications using LLM

    Instead of manually writing D3.js code, we use the LLM to:
    1. Analyze the data structure
    2. Choose the best chart type
    3. Generate D3.js code or config
    """

    def generate_chart_config(
        self,
        columns: List[str],
        data: List[List[Any]],
        question: str,
        chart_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate chart configuration using LLM

        Args:
            columns: Column names from query result
            data: First few rows of data (for analysis)
            question: Original user question (provides context)
            chart_hint: Optional hint like "use bar chart" or "show trend"

        Returns:
            Dict with D3.js code and metadata:
            {
                "type": "bar|line|scatter|pie|area",
                "d3_code": "// D3.js code as string",
                "title": "Chart Title",
                "description": "Why this chart type was chosen"
            }
        """
        logger.info(f"Generating chart for question: '{question[:50]}...'")

        # Build prompt for LLM
        messages = self._build_chart_prompt(columns, data, question, chart_hint)

        # Call LLM
        response = call_llm(messages, temperature=0.3, max_tokens=2000)

        # Parse response
        try:
            chart_config = parse_json(response)
            logger.info(f"Generated chart type: {chart_config.get('type')}")
            return chart_config
        except Exception as e:
            logger.error(f"Failed to parse chart config: {e}")
            # Fallback to simple bar chart
            return self._create_fallback_chart(columns, data)

    def regenerate_chart(
        self,
        current_config: Dict[str, Any],
        columns: List[str],
        data: List[List[Any]],
        edit_instruction: str
    ) -> Dict[str, Any]:
        """
        Regenerate chart based on user's natural language edit

        Args:
            current_config: Current chart configuration
            columns: Column names
            data: Data rows
            edit_instruction: User instruction like "make it blue" or "change to line chart"

        Returns:
            Updated chart configuration
        """
        logger.info(f"Regenerating chart with instruction: '{edit_instruction}'")

        messages = [
            {
                "role": "system",
                "content": "You are a data visualization expert. Modify charts based on user instructions."
            },
            {
                "role": "user",
                "content": f"""
Current chart configuration:
{json.dumps(current_config, indent=2)}

Data columns: {columns}
Sample data (first 5 rows): {json.dumps(data[:5])}

User wants to modify the chart: "{edit_instruction}"

Generate updated chart configuration following the same JSON format.
Preserve what works, only change what the user requested.
"""
            }
        ]

        response = call_llm(messages, temperature=0.3, max_tokens=2000)

        try:
            updated_config = parse_json(response)
            logger.info(f"Chart regenerated successfully")
            return updated_config
        except Exception as e:
            logger.error(f"Failed to regenerate chart: {e}")
            return current_config  # Return original if regeneration fails

    def _build_chart_prompt(
        self,
        columns: List[str],
        data: List[List[Any]],
        question: str,
        chart_hint: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Build prompt for chart generation"""

        system_prompt = """You are a data visualization expert.

Your task: Analyze data and generate a simple chart configuration.

IMPORTANT RULES:
1. Return ONLY valid JSON (no markdown, no explanations)
2. Choose the best chart type for the data
3. Use professional colors (#3b82f6, #10b981, #f59e0b, #ef4444)

OUTPUT FORMAT (JSON):
{
  "type": "bar|line|scatter|pie|area",
  "title": "Descriptive title",
  "description": "Why this chart type fits the data",
  "config": {
    "xField": "column_name",
    "yField": "column_name",
    "color": "#hex_color",
    "showLegend": true,
    "showGrid": true
  }
}

CHART TYPE SELECTION:
- bar: Comparing categories (sales by product, users by country)
- line: Trends over time (revenue by month, growth)
- scatter: Correlation between two variables
- pie: Parts of a whole (market share, distribution)
- area: Volume over time (cumulative metrics)
"""

        hint_text = f"\nUser hint: {chart_hint}" if chart_hint else ""

        user_prompt = f"""
Question: "{question}"{hint_text}

Data structure:
Columns: {', '.join(columns)}
Data types: {self._infer_types(columns, data)}
Sample (first 5 rows):
{json.dumps(data[:5], indent=2)}

Generate the best chart configuration for this data.
"""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

    def _infer_types(self, columns: List[str], data: List[List[Any]]) -> Dict[str, str]:
        """Infer data types from first row"""
        if not data or not data[0]:
            return {}

        types = {}
        first_row = data[0]

        for i, col in enumerate(columns):
            if i >= len(first_row):
                continue

            value = first_row[i]
            if isinstance(value, (int, float)):
                types[col] = "numeric"
            elif isinstance(value, str):
                # Check if looks like a date
                if any(indicator in value.lower() for indicator in ['2024', '2023', 'jan', 'feb', 'mar', '/', '-']):
                    types[col] = "date/text"
                else:
                    types[col] = "text"
            else:
                types[col] = "unknown"

        return types

    def _create_fallback_chart(
        self,
        columns: List[str],
        data: List[List[Any]]
    ) -> Dict[str, Any]:
        """Create a simple fallback bar chart when LLM fails"""
        return {
            "type": "bar",
            "title": "Data Visualization",
            "description": "Simple bar chart (fallback)",
            "config": {
                "xField": columns[0] if len(columns) > 0 else "x",
                "yField": columns[1] if len(columns) > 1 else "y",
                "color": "#3b82f6",
                "showLegend": False,
                "showGrid": True
            }
        }
