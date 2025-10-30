"""
Response parsing node - extracts and cleans LLM response
"""
from app.pipeline.llm.nodes.base import BaseNode, LLMResponse, ParsedContent


class ParseResponseNode(BaseNode[LLMResponse, ParsedContent]):
    """Extracts and cleans content from LLM response"""

    def process(self, input_data: LLMResponse) -> ParsedContent:
        # If from cache, content is already clean
        if input_data.cache_hit:
            return ParsedContent(
                content=input_data.raw_response.get("content", ""),
                tokens_used=None,
                estimated_cost_usd=None
            )

        # Extract content
        content = input_data.raw_response["choices"][0]["message"]["content"]
        content = content.strip()

        # Remove code fences
        content = self._clean_code_fences(content)

        # Extract metrics
        usage = input_data.raw_response.get("usage", {})
        tokens = usage.get("total_tokens")
        # GPT-4 pricing: ~$0.03 input + $0.06 output per 1K tokens (avg $0.045)
        cost = (tokens / 1000 * 0.045) if tokens else None

        self.logger.debug(
            f"Parsed: {len(content)} chars, "
            f"{tokens} tokens, "
            f"${cost:.4f}" if cost else "Parsed response"
        )

        return ParsedContent(
            content=content,
            tokens_used=tokens,
            estimated_cost_usd=cost
        )

    def _clean_code_fences(self, content: str) -> str:
        """Removes markdown code fences (```sql ... ```)"""
        if content.startswith("```"):
            content = content.strip("`")
            # Remove language identifier (e.g., "sql")
            if "\n" in content:
                lines = content.split("\n")
                if lines[0].strip().isalpha():
                    content = "\n".join(lines[1:])

        return content.strip()
