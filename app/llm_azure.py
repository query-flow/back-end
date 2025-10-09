# app/llm_azure.py
import os
import httpx

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

SYSTEM_PROMPT_TEMPLATE = """Você é um tradutor NL→SQL no dialeto {dialeto}. Regras obrigatórias:
- Gere SOMENTE um SELECT SQL válido (sem comentários, sem ```).
- Use apenas tabelas/colunas do esquema fornecido.
- Prefira JOINs com PK/FK explícitas.
- NUNCA modifique dados (sem INSERT/UPDATE/DELETE/DDL).
- Se o usuário não pedir limite explícito, inclua LIMIT {limit}.
- Formate datas e funções para {dialeto} (MySQL).
- Evite CTEs desnecessárias.
"""

def _endpoint_url() -> str:
    if not (AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT and AZURE_OPENAI_API_KEY):
        raise RuntimeError("Credenciais Azure OpenAI ausentes. Defina AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY e AZURE_OPENAI_DEPLOYMENT.")
    return f"{AZURE_OPENAI_ENDPOINT}/openai/deployments/{AZURE_OPENAI_DEPLOYMENT}/chat/completions?api-version={AZURE_OPENAI_API_VERSION}"

def chamar_llm_azure(prompt_usuario: str, limit: int = 100, dialeto: str = "MySQL") -> str:
    """
    Chama Azure OpenAI Chat Completions e devolve APENAS o SQL (string).
    """
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(dialeto=dialeto, limit=limit)

    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            # Se quiser, injete aqui few-shots antes do user
            {"role": "user", "content": prompt_usuario}
        ],
        "temperature": 0.1,
        "max_tokens": 800,
        "top_p": 0.95
    }

    headers = {
        "Content-Type": "application/json",
        "api-key": AZURE_OPENAI_API_KEY
    }

    url = _endpoint_url()
    # timeout curto para não travar sua API
    with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    # Extrai a primeira resposta
    try:
        content = data["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"Resposta inesperada do Azure OpenAI: {data}") from e

    # Sanitiza: remove possíveis cercas de código
    content = content.strip()
    if content.startswith("```"):
        # remove blocos ```sql ... ```
        content = content.strip("`")
        # às vezes vem com "sql\n"
        if content.lower().startswith("sql"):
            content = content[3:].lstrip()
    return content.strip()
