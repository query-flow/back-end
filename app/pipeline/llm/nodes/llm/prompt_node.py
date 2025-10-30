"""
Prompt building node - constructs LLM prompts from templates
"""
import hashlib
from app.pipeline.llm.nodes.base import BaseNode, LLMRequest, PromptBuilt


# Prompt templates
PROMPTS = {
    "nl_to_sql": {
        "system": """Você é um tradutor NL→SQL no dialeto MySQL. Regras obrigatórias:
- Gere SOMENTE um SELECT SQL válido (sem comentários, sem ```).
- Use apenas tabelas/colunas do esquema fornecido.
- Prefira JOINs com PK/FK explícitas.
- NUNCA modifique dados (sem INSERT/UPDATE/DELETE/DDL).
- Se o usuário não pedir limite explícito, inclua LIMIT {limit}.
- Dialeto alvo: MySQL.""",
        "user": """{esquema}

Pergunta do usuário:
{pergunta}

Responda SOMENTE com o SQL válido (sem explicações)."""
    },

    "sql_correction": {
        "system": "Você é um especialista SQL. Corrija o SQL que gerou erro, seguindo as mesmas regras anteriores.",
        "user": """Esquema:
{esquema}

SQL que gerou erro:
{sql_original}

Erro:
{erro}

Corrija o SQL (somente SELECT, LIMIT {limit} se faltar)."""
    },

    "insights": {
        "system": """Você é um analista de BI. Explique resultados em linguagem de negócio,
conectando com o contexto fornecido, sem jargões técnicos desnecessários. Seja objetivo.""",
        "user": """{biz_context}

Pergunta do usuário: {pergunta}

Prévia dos dados (tabela):
Colunas: {colunas}
Amostra (até 10 linhas): {dados}

Escreva uma síntese de até 8 linhas com o que é mais relevante,
seguida de 3 pontos de atenção / próximos passos."""
    },

    "schema_selection": {
        "system": "Você escolhe UM schema dentre os permitidos. Responda com uma única palavra (nome exato), sem explicações.",
        "user": "Schemas permitidos: {schemas}\nPergunta: {pergunta}\nResponda apenas com o schema."
    },

    "document_metadata": {
        "system": """Você extrai metadados de documentos de contexto de negócio, devolvendo JSON com as chaves:
summary (string curta), kpis (lista de {name, formula?, current?, target?, unit?}),
goals (lista de strings), timeframe (string), notes (string). Responda somente JSON.""",
        "user": "Documento (texto puro):\n{text}"
    }
}


class BuildPromptNode(BaseNode[LLMRequest, PromptBuilt]):
    """Builds prompt from template and variables"""

    def process(self, input_data: LLMRequest) -> PromptBuilt:
        # Get template
        if input_data.prompt_name not in PROMPTS:
            raise ValueError(f"Prompt '{input_data.prompt_name}' não existe")

        template = PROMPTS[input_data.prompt_name]

        # Format with variables
        system = template["system"].format(**input_data.variables)
        user = template["user"].format(**input_data.variables)

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]

        # Generate cache key
        cache_key = self._make_cache_key(
            messages,
            input_data.temperature,
            input_data.max_tokens
        )

        self.logger.debug(
            f"Prompt built: system={len(system)} chars, user={len(user)} chars"
        )

        return PromptBuilt(
            messages=messages,
            temperature=input_data.temperature,
            max_tokens=input_data.max_tokens,
            cache_key=cache_key,
            use_cache=input_data.use_cache
        )

    def _make_cache_key(
        self,
        messages: list,
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate unique cache key"""
        key_data = f"{messages}:{temperature}:{max_tokens}"
        return hashlib.sha256(key_data.encode()).hexdigest()
