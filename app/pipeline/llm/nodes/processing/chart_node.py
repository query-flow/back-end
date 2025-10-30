"""
Chart generation node using matplotlib (NOT LLM)
"""
import base64
import os
from io import BytesIO
from typing import Optional, Tuple, List
from app.pipeline.llm.nodes.base import BaseNode, InsightsGenerated, ChartGenerated

# Set matplotlib backend before importing
os.environ.setdefault("MPLBACKEND", "Agg")


class GenerateChartNode(BaseNode[InsightsGenerated, ChartGenerated]):
    """
    Generates bar chart from query results

    Uses matplotlib (NOT LLM)
    """

    def process(self, input_data: InsightsGenerated) -> ChartGenerated:
        chart_base64 = None

        if input_data.generate_chart:
            chart_base64 = self._make_chart(input_data.query_result)

        return ChartGenerated(
            pergunta=input_data.pergunta,
            query_result=input_data.query_result,
            insights=input_data.insights,
            chart_base64=chart_base64,
            chart_mime="image/png"
        )

    def _make_chart(self, query_result) -> Optional[str]:
        """Generates bar chart"""
        try:
            import matplotlib
            matplotlib.use("Agg", force=True)
            import matplotlib.pyplot as plt
        except ImportError:
            self.logger.warning("matplotlib not available")
            return None

        # Detect axes
        axes = self._pick_axes(query_result)
        if not axes:
            self.logger.debug("Could not detect axes for chart")
            return None

        labels, values, title = axes

        # Create chart
        fig = plt.figure(figsize=(10, 6))
        plt.bar(labels, values, color='steelblue')
        plt.xticks(rotation=45, ha="right")
        plt.title(title)
        plt.tight_layout()

        # Convert to base64
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=150)
        plt.close(fig)

        self.logger.debug(f"Chart generated: {title}")

        return base64.b64encode(buf.getvalue()).decode()

    def _pick_axes(self, query_result) -> Optional[Tuple[List[str], List[float], str]]:
        """
        Auto-detects categorical and numerical columns

        Heuristic:
        - First string-ish column = category
        - First numerical column (different from category) = values
        """
        colunas = query_result.colunas
        dados = query_result.dados

        if not colunas or not dados:
            return None

        # Detect categorical column (first string-ish)
        cat_idx = None
        for i, col in enumerate(colunas):
            sample = [row[i] if i < len(row) else None for row in dados[:5]]
            non_numeric = sum(1 for v in sample if v and not self._is_numeric(v))
            if non_numeric >= len(sample) // 2:
                cat_idx = i
                break

        if cat_idx is None:
            cat_idx = 0  # Fallback: first column

        # Detect numerical column (first numeric different from category)
        num_idx = None
        for j, col in enumerate(colunas):
            if j == cat_idx:
                continue
            sample = [row[j] if j < len(row) else None for row in dados[:5]]
            if all(self._is_numeric(v) for v in sample if v is not None):
                num_idx = j
                break

        if num_idx is None:
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

        title = f"{colunas[num_idx]} por {colunas[cat_idx]}"

        return labels, values, title

    def _is_numeric(self, value) -> bool:
        """Checks if value is numeric"""
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False
