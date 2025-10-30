"""
Response formatting node - formats final API response
"""
from app.pipeline.llm.nodes.base import BaseNode, ChartGenerated, EnrichedResponse


class FormatResponseNode(BaseNode[ChartGenerated, EnrichedResponse]):
    """
    Formats final response in the expected API format
    """

    def process(self, input_data: ChartGenerated) -> EnrichedResponse:
        # Format result in old format
        resultado = {
            "colunas": input_data.query_result.colunas,
            "dados": input_data.query_result.dados
        }

        # Format chart (if present)
        chart = None
        if input_data.chart_base64:
            chart = {
                "mime": input_data.chart_mime,
                "base64": input_data.chart_base64
            }

        self.logger.debug("Response formatted")

        return EnrichedResponse(
            sql=input_data.query_result.sql,
            schema=input_data.query_result.schema,
            resultado=resultado,
            insights=input_data.insights,
            chart=chart
        )
