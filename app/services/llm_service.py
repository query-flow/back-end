import httpx
from typing import Optional, List
from app.core.config import settings

SYSTEM_PROMPT_TEMPLATE = """Você é um tradutor NL→SQL no dialeto {dialeto}. Regras obrigatórias:
- Gere SOMENTE um SELECT SQL válido (sem comentários, sem ```).
- Use apenas tabelas/colunas do esquema fornecido.
- Prefira JOINs com PK/FK explícitas.
- NUNCA modifique dados (sem INSERT/UPDATE/DELETE/DDL).
- Se o usuário não pedir limite explícito, inclua LIMIT {limit}.
- Dialeto alvo: {dialeto}.
"""

PROMPT_BASE = """{esquema}

Pergunta do usuário:
{pergunta}

Responda SOMENTE com o SQL válido (sem explicações)."""


def _azure_chat_url() -> str:
    """Build Azure OpenAI chat completion URL"""
    return (
        f"{settings.AZURE_OPENAI_ENDPOINT}/openai/deployments/"
        f"{settings.AZURE_OPENAI_DEPLOYMENT}/chat/completions?"
        f"api-version={settings.AZURE_OPENAI_API_VERSION}"
    )


def chamar_llm_azure(prompt_usuario: str, limit: int = 100, dialeto: str = "MySQL") -> str:
    """
    Call Azure OpenAI to generate SQL from natural language
    """
    if (
        settings.DISABLE_AZURE_LLM
        or not settings.AZURE_OPENAI_API_KEY
        or not settings.AZURE_OPENAI_ENDPOINT
        or not settings.AZURE_OPENAI_DEPLOYMENT
    ):
        return f"SELECT 1 AS ok LIMIT {limit};"

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(dialeto=dialeto, limit=limit)
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_usuario}
        ],
        "temperature": 0.1,
        "max_tokens": 800,
        "top_p": 0.95
    }
    headers = {
        "Content-Type": "application/json",
        "api-key": settings.AZURE_OPENAI_API_KEY
    }
    url = _azure_chat_url()

    try:
        with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            r = client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()

        content = data["choices"][0]["message"]["content"].strip()

        # Remove code fences if present
        if content.startswith("```"):
            content = content.strip("`")
            if content.lower().startswith("sql"):
                content = content[3:].lstrip()

        return content.strip()
    except Exception:
        return f"SELECT 1 AS ok LIMIT {limit};"


def ask_llm_pick_schema(allowed: List[str], pergunta: str) -> Optional[str]:
    """
    Ask LLM to pick the most appropriate schema based on the question
    """
    if (
        settings.DISABLE_AZURE_LLM
        or not settings.AZURE_OPENAI_API_KEY
        or not settings.AZURE_OPENAI_ENDPOINT
        or not settings.AZURE_OPENAI_DEPLOYMENT
    ):
        return None

    system = "Você escolhe UM schema dentre os permitidos. Responda com uma única palavra (nome exato), sem explicações."
    user = f"Schemas permitidos: {', '.join(allowed)}\nPergunta: {pergunta}\nResponda apenas com o schema."

    payload = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "temperature": 0.0,
        "max_tokens": 10
    }
    headers = {
        "Content-Type": "application/json",
        "api-key": settings.AZURE_OPENAI_API_KEY
    }
    url = _azure_chat_url()

    try:
        with httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0)) as cli:
            r = cli.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()

        choice = data["choices"][0]["message"]["content"].strip()

        # Extract schema name from response
        import re
        cand = re.findall(r"[a-zA-Z0-9_]+", choice)
        if not cand:
            return None

        name = cand[0].lower()
        for s in allowed:
            if s.lower() == name:
                return s

        return None
    except Exception:
        return None
