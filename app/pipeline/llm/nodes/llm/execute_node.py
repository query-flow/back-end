"""
LLM execution node with retry logic
"""
import time
import httpx
from app.pipeline.llm.nodes.base import BaseNode, PromptBuilt, LLMResponse
from app.core.config import settings


class ExecuteLLMNode(BaseNode[PromptBuilt, LLMResponse]):
    """
    Executes LLM call with automatic retry

    If cache_hit=True in input, skips execution
    """

    def __init__(self, max_retries: int = 3):
        super().__init__()
        self.max_retries = max_retries

    def process(self, input_data: PromptBuilt) -> LLMResponse:
        # Skip if cache hit
        if hasattr(input_data, 'cache_hit') and input_data.cache_hit:
            self.logger.info("Cache hit, skipping execution")
            return LLMResponse(
                raw_response={"cached": True, "content": input_data.cached_content},
                cache_hit=True,
                retry_count=0,
                latency_ms=0.0
            )

        # Execute with retry
        for attempt in range(self.max_retries):
            try:
                self.logger.info(f"Attempt {attempt + 1}/{self.max_retries}")

                start = time.time()
                response = self._http_call(input_data)
                latency = (time.time() - start) * 1000

                self.logger.info(f"LLM responded in {latency:.0f}ms")

                return LLMResponse(
                    raw_response=response,
                    cache_hit=False,
                    retry_count=attempt,
                    latency_ms=latency
                )

            except httpx.HTTPStatusError as e:
                status = e.response.status_code

                # Don't retry on 4xx errors (except 429)
                if status in [400, 401, 403, 404]:
                    self.logger.error(f"Non-retryable error: {status}")
                    raise

                if attempt < self.max_retries - 1:
                    wait = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    self.logger.warning(
                        f"Error {status}, waiting {wait}s before retry..."
                    )
                    time.sleep(wait)
                else:
                    self.logger.error(f"Failed after {self.max_retries} attempts")
                    raise

            except httpx.TimeoutException as e:
                if attempt < self.max_retries - 1:
                    wait = 2 ** attempt
                    self.logger.warning(
                        f"Timeout, waiting {wait}s before retry..."
                    )
                    time.sleep(wait)
                else:
                    self.logger.error(f"Timeout after {self.max_retries} attempts")
                    raise

            except Exception as e:
                self.logger.error(f"Unexpected error: {e}")
                raise

    def _http_call(self, input_data: PromptBuilt) -> dict:
        """Makes HTTP request to Azure OpenAI"""
        url = (
            f"{settings.AZURE_OPENAI_ENDPOINT}/openai/deployments/"
            f"{settings.AZURE_OPENAI_DEPLOYMENT}/chat/completions?"
            f"api-version={settings.AZURE_OPENAI_API_VERSION}"
        )

        headers = {
            "Content-Type": "application/json",
            "api-key": settings.AZURE_OPENAI_API_KEY
        }

        payload = {
            "messages": input_data.messages,
            "temperature": input_data.temperature,
            "max_tokens": input_data.max_tokens,
            "top_p": 0.95
        }

        with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
