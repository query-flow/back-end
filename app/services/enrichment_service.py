"""
Service for query result enrichment
Generates insights and charts from SQL results
"""
import logging
from typing import Optional
from app.dtos import QueryExecutionContext, OrgContext
from app.pipeline.stages import generate_insights, generate_chart, QueryResult

logger = logging.getLogger(__name__)


class EnrichmentService:
    """
    Handles result enrichment (insights + chart generation)
    Eliminates code duplication from controller
    """

    def enrich_results(
        self,
        ctx: QueryExecutionContext,
        org_ctx: OrgContext
    ) -> None:
        """
        Enrich query results with insights and chart

        Modifies ctx in place:
        - Sets ctx.insights_text
        - Sets ctx.chart_base64

        Args:
            ctx: Query execution context with results
            org_ctx: Organization context for business context
        """
        if not ctx.colunas or not ctx.dados:
            logger.debug("Skipping enrichment: no data to enrich")
            return

        # Generate insights
        try:
            ctx.insights_text = self._generate_insights(ctx, org_ctx)
            logger.info("Insights generated successfully")
        except Exception as e:
            logger.warning(f"Failed to generate insights: {e}")
            ctx.insights_text = None

        # Generate chart
        try:
            ctx.chart_spec = self._generate_chart(ctx)
            if ctx.chart_spec:
                logger.info("Chart spec generated successfully")
            else:
                logger.debug("No chart generated (data not suitable)")
        except Exception as e:
            logger.warning(f"Failed to generate chart: {e}")
            ctx.chart_spec = None

    def _generate_insights(
        self,
        ctx: QueryExecutionContext,
        org_ctx: OrgContext
    ) -> str:
        """
        Generate business insights from query results

        Uses LLM to analyze data and provide actionable insights
        """
        return generate_insights(
            pergunta=ctx.pergunta,
            colunas=ctx.colunas,
            dados=ctx.dados,
            biz_context=org_ctx.biz_context
        )

    def _generate_chart(
        self,
        ctx: QueryExecutionContext
    ) -> Optional[dict]:
        """
        Generate interactive chart specification from query results

        Returns:
            Chart spec dict with type, data, config, and recommendation_reason
            or None if not suitable for charting
        """
        if not ctx.sql_executed or not ctx.schema_used:
            return None

        query_result = QueryResult(
            sql=ctx.sql_executed,
            schema=ctx.schema_used,
            colunas=ctx.colunas,
            dados=ctx.dados
        )

        return generate_chart(query_result)
