"""
Base classes and Pydantic models for LLM node pipeline
"""
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List, Any
from pydantic import BaseModel, Field
import logging

# Type variables for generic nodes
InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class BaseNode(ABC, Generic[InputT, OutputT]):
    """
    Base class for all pipeline nodes

    Each node:
    - Receives typed input (Pydantic)
    - Processes data
    - Returns typed output (Pydantic)
    """

    def __init__(self, name: Optional[str] = None):
        self.name = name or self.__class__.__name__
        self.logger = logging.getLogger(f"pipeline.{self.name}")

    @abstractmethod
    def process(self, input_data: InputT) -> OutputT:
        """Process input and return output"""
        pass

    def __call__(self, input_data: InputT) -> OutputT:
        """Allow calling node as a function"""
        self.logger.debug(f"Processing {self.name}")
        return self.process(input_data)


class NodeChain(Generic[InputT, OutputT]):
    """
    Chains multiple nodes together

    Example:
        chain = NodeChain([node1, node2, node3])
        result = chain.run(input_data)
    """

    def __init__(self, nodes: List[BaseNode], name: str = "Chain"):
        self.nodes = nodes
        self.name = name
        self.logger = logging.getLogger(f"pipeline.{name}")

    def run(self, input_data: InputT) -> OutputT:
        """Execute all nodes in sequence"""
        current_data = input_data

        self.logger.info(f"Starting chain: {self.name}")

        for i, node in enumerate(self.nodes, 1):
            self.logger.info(f"[{i}/{len(self.nodes)}] {node.name}")
            current_data = node(current_data)

        self.logger.info(f"Chain {self.name} completed")
        return current_data


# ===================================
# PYDANTIC MODELS - LLM
# ===================================

class LLMRequest(BaseModel):
    """Initial input for LLM chain"""
    prompt_name: str = Field(..., description="Prompt template name")
    variables: dict = Field(default_factory=dict, description="Template variables")
    temperature: float = Field(0.1, ge=0.0, le=2.0, description="LLM temperature")
    max_tokens: int = Field(800, gt=0, description="Max tokens in response")
    use_cache: bool = Field(True, description="Enable caching")


class PromptBuilt(BaseModel):
    """Output of BuildPromptNode"""
    messages: List[dict] = Field(..., description="Messages array for LLM")
    temperature: float
    max_tokens: int
    cache_key: str = Field(..., description="Cache key")
    use_cache: bool

    # Optional fields (filled by CacheCheckNode)
    cache_hit: bool = False
    cached_content: Optional[str] = None


class LLMResponse(BaseModel):
    """Output of ExecuteLLMNode"""
    raw_response: dict = Field(..., description="Raw LLM response")
    cache_hit: bool = False
    retry_count: int = 0
    latency_ms: float = 0.0


class ParsedContent(BaseModel):
    """Output of ParseResponseNode"""
    content: str = Field(..., description="Cleaned content (no code fences)")
    tokens_used: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    cache_key: Optional[str] = None  # For CacheSaveNode


# ===================================
# PYDANTIC MODELS - ENRICHMENT
# ===================================

class QueryResult(BaseModel):
    """SQL query execution result"""
    colunas: List[str]
    dados: List[List[Any]]
    sql: str
    schema: str


class EnrichmentRequest(BaseModel):
    """Input for enrichment pipeline"""
    pergunta: str
    query_result: QueryResult
    biz_context: str = ""
    generate_chart: bool = True
    generate_insights: bool = True


class InsightsGenerated(BaseModel):
    """Output after generating insights"""
    pergunta: str
    query_result: QueryResult
    insights: Optional[str] = None
    biz_context: str = ""
    generate_chart: bool = True


class ChartGenerated(BaseModel):
    """Output after generating chart"""
    pergunta: str
    query_result: QueryResult
    insights: Optional[str] = None
    chart_base64: Optional[str] = None
    chart_mime: str = "image/png"


class EnrichedResponse(BaseModel):
    """Final enriched output"""
    sql: str
    schema: str
    resultado: dict  # {colunas: [...], dados: [...]}
    insights: Optional[str] = None
    chart: Optional[dict] = None  # {mime: "image/png", base64: "..."}
