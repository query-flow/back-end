"""
Pre-defined node chains for common LLM operations
"""
from app.services.llm.nodes.base import (
    NodeChain,
    BaseNode,
    LLMRequest,
    EnrichmentRequest,
    InsightsGenerated
)
from app.services.llm.nodes.llm.prompt_node import BuildPromptNode
from app.services.llm.nodes.llm.cache_node import CacheCheckNode, CacheSaveNode
from app.services.llm.nodes.llm.execute_node import ExecuteLLMNode
from app.services.llm.nodes.llm.parse_node import ParseResponseNode
from app.services.llm.nodes.processing.chart_node import GenerateChartNode
from app.services.llm.nodes.processing.format_node import FormatResponseNode


# ========================================
# CHAIN 1: NL → SQL
# ========================================

def create_nl_to_sql_chain() -> NodeChain:
    """
    Chain for NL → SQL generation

    Nodes:
    1. BuildPromptNode - Build prompt
    2. CacheCheckNode - Check cache
    3. ExecuteLLMNode - Call LLM (skip if cache hit)
    4. ParseResponseNode - Clean response
    5. CacheSaveNode - Save to cache
    """
    return NodeChain(
        nodes=[
            BuildPromptNode(),
            CacheCheckNode(),
            ExecuteLLMNode(max_retries=3),
            ParseResponseNode(),
            CacheSaveNode(ttl_seconds=3600),  # 1 hour
        ],
        name="NL_to_SQL"
    )


# ========================================
# CHAIN 2: Insights Generation (LLM only)
# ========================================

def create_insights_llm_chain() -> NodeChain:
    """
    Chain for insights generation (LLM only, no chart)
    """
    return NodeChain(
        nodes=[
            BuildPromptNode(),
            CacheCheckNode(),
            ExecuteLLMNode(max_retries=3),
            ParseResponseNode(),
            CacheSaveNode(ttl_seconds=1800),  # 30 minutes
        ],
        name="Insights_LLM"
    )


# ========================================
# CHAIN 3: COMPLETE ENRICHMENT (LLM + Chart)
# ========================================

class GenerateInsightsNode(BaseNode[EnrichmentRequest, InsightsGenerated]):
    """
    Node that uses LLM chain internally to generate insights
    """

    def __init__(self):
        super().__init__(name="GenerateInsights")
        self.llm_chain = create_insights_llm_chain()

    def process(self, input_data: EnrichmentRequest) -> InsightsGenerated:
        insights = None

        if input_data.generate_insights:
            # Prepare LLM request
            llm_request = LLMRequest(
                prompt_name="insights",
                variables={
                    "pergunta": input_data.pergunta,
                    "colunas": input_data.query_result.colunas,
                    "dados": input_data.query_result.dados[:10],  # Limit to 10 rows
                    "biz_context": input_data.biz_context
                },
                temperature=0.2,
                max_tokens=500,
                use_cache=True
            )

            # Execute LLM chain
            result = self.llm_chain.run(llm_request)
            insights = result.content

        return InsightsGenerated(
            pergunta=input_data.pergunta,
            query_result=input_data.query_result,
            insights=insights,
            biz_context=input_data.biz_context,
            generate_chart=input_data.generate_chart
        )


def create_enrichment_chain() -> NodeChain:
    """
    COMPLETE enrichment chain

    Input: EnrichmentRequest (question, SQL result, context)
    Output: EnrichedResponse (insights + chart + formatting)

    Combines LLM and non-LLM nodes:
    1. GenerateInsightsNode (uses LLM internally)
    2. GenerateChartNode (matplotlib)
    3. FormatResponseNode (formatting)
    """
    return NodeChain(
        nodes=[
            GenerateInsightsNode(),   # LLM
            GenerateChartNode(),      # matplotlib
            FormatResponseNode(),     # formatting
        ],
        name="Enrichment"
    )
