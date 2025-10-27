"""
Cache nodes for LLM responses
"""
from app.services.llm.nodes.base import BaseNode, PromptBuilt, ParsedContent
from app.services.llm.cache import _cache


class CacheCheckNode(BaseNode[PromptBuilt, PromptBuilt]):
    """
    Checks if response is in cache

    If found:
    - Adds cached_content to PromptBuilt
    - Sets cache_hit = True
    """

    def process(self, input_data: PromptBuilt) -> PromptBuilt:
        if not input_data.use_cache:
            self.logger.debug("Cache disabled")
            return input_data

        cached = _cache.get(input_data.cache_key)

        if cached:
            self.logger.info(f"Cache HIT [{input_data.cache_key[:12]}...]")
            # Add dynamic fields
            input_data.cache_hit = True
            input_data.cached_content = cached
        else:
            self.logger.debug("Cache MISS")

        return input_data


class CacheSaveNode(BaseNode[ParsedContent, ParsedContent]):
    """Saves result to cache"""

    def __init__(self, ttl_seconds: int = 3600):
        super().__init__()
        self.ttl_seconds = ttl_seconds

    def process(self, input_data: ParsedContent) -> ParsedContent:
        # Cache key needs to come from previous context
        if hasattr(input_data, 'cache_key') and input_data.cache_key:
            _cache.set(
                input_data.cache_key,
                input_data.content,
                ttl_seconds=self.ttl_seconds
            )
            self.logger.debug(f"Saved to cache [ttl={self.ttl_seconds}s]")

        return input_data
