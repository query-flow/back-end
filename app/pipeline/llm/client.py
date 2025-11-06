"""
LLM client for Azure OpenAI
"""
import httpx
import time
import asyncio
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


def call_llm(
    messages: list[dict],
    temperature: float = 0.1,
    max_tokens: int = 800
) -> str:
    """
    Call Azure OpenAI with retry
    Returns content string directly
    """
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
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    # Retry 3 times
    for attempt in range(3):
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt == 2:
                logger.error(f"LLM call failed after 3 attempts: {e}")
                raise
            wait_time = 2 ** attempt
            logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time}s...")
            time.sleep(wait_time)


async def call_llm_async(
    messages: list[dict],
    temperature: float = 0.1,
    max_tokens: int = 800
) -> str:
    """
    Async version of call_llm for parallel execution
    Returns content string directly
    """
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
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    # Retry 3 times
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt == 2:
                logger.error(f"Async LLM call failed after 3 attempts: {e}")
                raise
            wait_time = 2 ** attempt
            logger.warning(f"Async attempt {attempt + 1} failed, retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)
