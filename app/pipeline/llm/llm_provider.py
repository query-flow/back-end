"""
LLM clients - high-level interface for LLM operations
"""
from typing import Optional, List, Any, Dict
import re
from app.pipeline.llm.nodes.base import LLMRequest, QueryResult, EnrichmentRequest
from app.pipeline.llm.chains import create_nl_to_sql_chain, create_enrichment_chain


class LLMClient:
    """
    Client for LLM operations (SQL generation, correction, etc)

    Example:
        client = LLMClient()
        sql = client.generate_sql(pergunta="...", esquema="...")
    """

    def __init__(self):
        self.nl_to_sql_chain = create_nl_to_sql_chain()

    def generate_sql(
        self,
        pergunta: str,
        esquema: str,
        limit: int = 100
    ) -> str:
        """
        Generates SQL from natural language question

        Args:
            pergunta: Question in Portuguese
            esquema: Database schema description
            limit: Row limit for query

        Returns:
            Generated SQL query
        """
        request = LLMRequest(
            prompt_name="nl_to_sql",
            variables={
                "pergunta": pergunta,
                "esquema": esquema,
                "limit": limit
            },
            temperature=0.1,
            max_tokens=800,
            use_cache=True
        )

        result = self.nl_to_sql_chain.run(request)
        return result.content

    def correct_sql(
        self,
        sql_original: str,
        erro: str,
        esquema: str,
        limit: int = 100
    ) -> str:
        """
        Corrects SQL that generated an error

        Args:
            sql_original: Original SQL that failed
            erro: Error message
            esquema: Database schema description
            limit: Row limit

        Returns:
            Corrected SQL query
        """
        request = LLMRequest(
            prompt_name="sql_correction",
            variables={
                "sql_original": sql_original,
                "erro": erro,
                "esquema": esquema,
                "limit": limit
            },
            temperature=0.1,
            max_tokens=800,
            use_cache=False  # Don't cache corrections
        )

        result = self.nl_to_sql_chain.run(request)
        return result.content

    def pick_schema(
        self,
        schemas: List[str],
        pergunta: str
    ) -> Optional[str]:
        """
        Uses LLM to pick the best schema

        Args:
            schemas: List of available schemas
            pergunta: User question

        Returns:
            Selected schema name or None if failed
        """
        request = LLMRequest(
            prompt_name="schema_selection",
            variables={
                "schemas": ", ".join(schemas),
                "pergunta": pergunta
            },
            temperature=0.0,
            max_tokens=10,
            use_cache=False
        )

        try:
            result = self.nl_to_sql_chain.run(request)
            response = result.content

            # Extract schema name
            candidates = re.findall(r"[a-zA-Z0-9_]+", response)
            if candidates:
                name = candidates[0].lower()
                for s in schemas:
                    if s.lower() == name:
                        return s
        except Exception as e:
            import logging
            logger = logging.getLogger("llm.client")
            logger.warning(f"Schema selection via LLM failed: {e}")

        return None

    def extract_document_metadata(self, text: str) -> Dict[str, Any]:
        """
        Extracts metadata from document text

        Args:
            text: Raw document text

        Returns:
            Dict with summary, kpis, goals, timeframe, notes
        """
        import json

        request = LLMRequest(
            prompt_name="document_metadata",
            variables={
                "text": text[:12000]  # Limit size
            },
            temperature=0.1,
            max_tokens=900,
            use_cache=False
        )

        result = self.nl_to_sql_chain.run(request)

        try:
            return json.loads(result.content)
        except json.JSONDecodeError:
            return {"summary": result.content}


class EnrichmentClient:
    """
    Client for complete enrichment (insights + charts)

    Example:
        client = EnrichmentClient()
        enriched = client.enrich(
            pergunta="...",
            query_result=QueryResult(...),
            biz_context="..."
        )
    """

    def __init__(self):
        self.enrichment_chain = create_enrichment_chain()

    def enrich(
        self,
        pergunta: str,
        query_result: QueryResult,
        biz_context: str = "",
        generate_insights: bool = True,
        generate_chart: bool = True
    ) -> dict:
        """
        Enriches query result with insights and chart

        Args:
            pergunta: Original question
            query_result: SQL execution result
            biz_context: Business context from documents
            generate_insights: Generate insights via LLM
            generate_chart: Generate chart via matplotlib

        Returns:
            {
                "sql": "SELECT ...",
                "schema": "vendas",
                "resultado": {"colunas": [...], "dados": [...]},
                "insights": "Analysis...",
                "chart": {"mime": "image/png", "base64": "..."}
            }
        """
        request = EnrichmentRequest(
            pergunta=pergunta,
            query_result=query_result,
            biz_context=biz_context,
            generate_insights=generate_insights,
            generate_chart=generate_chart
        )

        result = self.enrichment_chain.run(request)

        return {
            "sql": result.sql,
            "schema": result.schema,
            "resultado": result.resultado,
            "insights": result.insights,
            "chart": result.chart
        }


# Global instances (singleton pattern)
llm_client = LLMClient()
enrichment_client = EnrichmentClient()
