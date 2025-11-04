"""Low-level LLM utilities"""
import httpx
import json
import time
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================
# LLM CALL (with retry)
# ============================================

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


# ============================================
# PROMPT BUILDERS
# ============================================

def build_intent_analysis_prompt(pergunta: str, esquema: str) -> list[dict]:
    """Build intent analysis prompt with schema validation"""
    system = """Você é um analista de negócios experiente. VALIDE O SCHEMA PRIMEIRO, depois avalie clareza.

FORMATO DE RESPOSTA:
{
  "confidence": 0.85,
  "is_clear": true,
  "schema_mismatch": false,
  "missing_data": [],
  "ambiguities": [],
  "questions": []
}

═══════════════════════════════════════════════
PASSO 1: VALIDAR SCHEMA (PRIORIDADE MÁXIMA)
═══════════════════════════════════════════════

Se a pergunta pede dados que NÃO EXISTEM no schema:
{
  "confidence": 0.0,
  "is_clear": false,
  "schema_mismatch": true,
  "missing_data": ["Descrição do que falta"],
  "ambiguities": [],
  "questions": [{
    "id": "alternatives",
    "text": "Esses dados não estão disponíveis. Posso mostrar:",
    "options": ["Sugestão 1 baseada no schema real", "Sugestão 2", "Sugestão 3"]
  }]
}

EXEMPLOS DE SCHEMA MISMATCH:

Schema: actor(id, name, birth_date), film(title, year)
Pergunta: "Qual ator ganhou mais Oscars?"
→ schema_mismatch=true (não há dados de prêmios)
→ missing_data: ["Informações sobre prêmios/Oscars não disponíveis"]
→ Sugestões: ["Listar todos os atores", "Atores mais antigos", "Filmes por ano"]

Schema: products(id, name, price), sales(product_id, quantity)
Pergunta: "Quais funcionários vendem mais?"
→ schema_mismatch=true (não há tabela de funcionários)
→ missing_data: ["Tabela 'employees' ou 'funcionarios' não existe"]
→ Sugestões: ["Produtos mais vendidos", "Total de vendas", "Produtos em baixo estoque"]

═══════════════════════════════════════════════
PASSO 2: SE SCHEMA OK, AVALIAR CLAREZA
═══════════════════════════════════════════════

ACEITE (confidence > 0.7, schema_mismatch=false):
- Análises exploratórias: "mostre vendas", "liste produtos"
- Contagens simples: "quantos clientes"
- Listagens: "top 10 produtos", "últimos 5 pedidos"

BLOQUEIE (confidence < 0.5, schema_mismatch=false):
- Métricas financeiras críticas: "lucro líquido", "ROI"
- Comparações sem baseline: "crescimento de vendas"
- Análises causais: "por que vendas caíram"

DEFAULTS (use sempre que razoável):
- Período: últimos 30 dias ou todo histórico
- Ranking: por volume/valor
- "Ativos": últimos 90 dias

IMPORTANTE: Seja específico sobre o que falta no schema. Ofereça APENAS alternativas que EXISTEM nos dados disponíveis."""

    user = f"""SCHEMA DISPONÍVEL:
{esquema}

PERGUNTA DO USUÁRIO:
{pergunta}

AVALIE: (1º) Schema suporta? (2º) Se sim, está claro ou precisa clarificação?"""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ]


# ============================================
# VERSÃO ALTERNATIVA: FEW-SHOT (ainda mais eficaz)
# ============================================

def criar_prompt_few_shot(esquema: str, pergunta: str) -> list:
    """
    Versão few-shot: ensina por exemplos em vez de regras longas.
    Geralmente mais eficaz que instruções extensas.
    """
    
    system = """Analista de negócios: assuma defaults inteligentes, só bloqueie quando crítico.

FORMATO DE RESPOSTA:
{"confidence": 0.0-1.0, "is_clear": bool, "ambiguities": [], "questions": [{"id": str, "text": str, "options": [str]}]}

EXEMPLOS:

Pergunta: "Quais são os 5 atores mais bem pagos?"
Resposta: {"confidence": 0.75, "is_clear": true, "ambiguities": [], "questions": []}
Razão: Exploratória, pode assumir ordenação por salário/cache

Pergunta: "Mostre as vendas"
Resposta: {"confidence": 0.7, "is_clear": true, "ambiguities": [], "questions": []}
Razão: Assume últimos 30 dias, análise exploratória

Pergunta: "Qual o ROI da campanha X?"
Resposta: {
  "confidence": 0.35,
  "is_clear": false,
  "ambiguities": ["Período não especificado", "Custos incluídos ambíguos"],
  "questions": [
    {"id": "period", "text": "Período da análise?", "options": ["Última semana", "Último mês", "Desde lançamento"]},
    {"id": "costs", "text": "Custos a incluir?", "options": ["Só mídia paga", "Mídia + produção", "Todos custos"]}
  ]
}
Razão: Métrica financeira crítica, múltiplas interpretações

Pergunta: "Crescimento de vendas?"
Resposta: {
  "confidence": 0.4,
  "is_clear": false,
  "ambiguities": ["Baseline indefinida"],
  "questions": [
    {"id": "comparison", "text": "Crescimento comparado a quê?", "options": ["Mês anterior", "Mesmo período ano passado", "Trimestre anterior"]}
  ]
}
Razão: Comparação sem baseline gera conclusões opostas

Pergunta: "Total de clientes"
Resposta: {"confidence": 0.9, "is_clear": true, "ambiguities": [], "questions": []}
Razão: Contagem simples, sem ambiguidade"""

    user = f"""SCHEMA:
{esquema}

PERGUNTA:
{pergunta}

Avalie:"""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ]


def build_sql_generation_prompt(
    pergunta: str,
    esquema: str,
    limit: int
) -> list[dict]:
    """Build NL→SQL prompt"""
    system = f"""Você é um tradutor de linguagem natural para SQL (dialeto MySQL).

REGRAS OBRIGATÓRIAS:
- Gere SOMENTE uma query SELECT válida
- Use apenas tabelas e colunas do schema fornecido
- Prefira JOINs com PK/FK explícitas
- NUNCA modifique dados (sem INSERT/UPDATE/DELETE/DDL)
- Inclua LIMIT {limit} se não houver LIMIT explícito
- Responda APENAS com o SQL, sem explicações

FORMATO DE RESPOSTA:
- Uma única query SQL
- Sem múltiplos statements (sem vários ponto-e-vírgulas)
- Sem comentários
- Sem explicações

EXEMPLO CORRETO:
SELECT coluna FROM tabela WHERE condicao LIMIT 10;

EXEMPLOS INCORRETOS:
❌ SELECT coluna FROM tabela; LIMIT 10;  (ponto-e-vírgula no meio)
❌ SELECT coluna FROM tabela;  (falta LIMIT quando necessário)
❌ -- Este SQL busca... SELECT coluna FROM tabela;  (tem comentário)"""

    user = f"""Schema:
{esquema}

Pergunta:
{pergunta}

SQL:"""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ]


def build_sql_correction_prompt(
    sql_original: str,
    erro: str,
    esquema: str,
    limit: int
) -> list[dict]:
    """Build SQL correction prompt"""
    system = f"""Você corrige SQL que gerou erros.

REGRAS:
- Retorne APENAS o SQL corrigido (uma única query)
- Sem múltiplos statements (sem vários ponto-e-vírgulas)
- Sem explicações
- Sem comentários
- Inclua LIMIT {limit} se necessário

EXEMPLO CORRETO:
SELECT coluna FROM tabela WHERE condicao LIMIT 10;

EXEMPLOS INCORRETOS:
❌ SELECT coluna FROM tabela; LIMIT 10;  (ponto-e-vírgula no meio)
❌ Aqui está o SQL corrigido: SELECT...  (tem explicação)"""

    user = f"""Schema:
{esquema}

SQL que gerou erro:
{sql_original}

Erro:
{erro}

SQL corrigido:"""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ]


def build_insights_prompt(
    pergunta: str,
    colunas: list[str],
    dados: list[list],
    biz_context: str
) -> list[dict]:
    """Build insights generation prompt"""
    system = """Você é um analista de BI.
Explique resultados em linguagem de negócio simples.
Conecte com o contexto de negócio fornecido.
Seja objetivo (máximo 8 linhas)."""

    user = f"""Contexto de negócio:
{biz_context}

Pergunta: {pergunta}

Dados (primeiras 10 linhas):
Colunas: {colunas}
{dados}

Escreva uma síntese com pontos principais e próximos passos."""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ]


# ============================================
# RESPONSE PARSERS
# ============================================

def parse_sql(response: str) -> str:
    """Extract SQL from LLM response (remove code fences and clean syntax)"""
    import logging
    logger = logging.getLogger(__name__)

    content = response.strip()
    logger.info(f"[parse_sql] Original response: {repr(content[:200])}")

    # Remove ```sql ... ```
    if content.startswith("```"):
        lines = content.split("```")
        if len(lines) >= 2:
            content = lines[1]
            # Remove language identifier
            if content.startswith("sql"):
                content = content[3:]
            elif content.startswith("SQL"):
                content = content[3:]

    content = content.strip()

    # Remove ALL semicolons (will add one at the end)
    content = content.replace(';', '')

    # Replace all newlines and multiple spaces with single space
    content = content.replace('\n', ' ').replace('\r', ' ')
    content = ' '.join(content.split())

    # Add single semicolon at end
    content += ';'

    logger.info(f"[parse_sql] Cleaned SQL: {repr(content[:200])}")

    return content


def parse_json(response: str) -> dict:
    """Parse JSON from LLM response with validation"""
    content = response.strip()

    # Remove ```json ... ```
    if content.startswith("```"):
        lines = content.split("```")
        if len(lines) >= 2:
            content = lines[1]
            if content.startswith("json"):
                content = content[4:]

    data = json.loads(content.strip())

    # Validate and fix questions format
    if "questions" in data:
        fixed_questions = []
        for q in data["questions"]:
            # If question is a string, skip it (LLM error)
            if isinstance(q, str):
                logger.warning(f"Skipping invalid question format: {q}")
                continue
            # If question is a dict, validate it has required fields
            if isinstance(q, dict):
                if "id" in q and "text" in q and "options" in q:
                    fixed_questions.append(q)
                else:
                    logger.warning(f"Question missing required fields: {q}")
        data["questions"] = fixed_questions

    return data
