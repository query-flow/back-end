import os
import base64
import httpx
from typing import Dict, Any, Optional, List, Tuple
from io import BytesIO

from app.core.config import settings
from app.models import Org

# Set matplotlib backend before importing
os.environ.setdefault("MPLBACKEND", "Agg")
try:
    import matplotlib
    matplotlib.use("Agg", force=True)
except Exception:
    pass


def collect_biz_context_for_org(org: Org) -> str:
    """
    Collect business context from organization documents
    """
    if not org.docs:
        return "Sem documentos de negócio cadastrados."

    partes = []
    for d in org.docs:
        md = d.metadata_json or {}
        md_txt = "; ".join(f"{k}: {v}" for k, v in md.items())
        partes.append(f"- {d.title} ({md_txt})" if md_txt else f"- {d.title}")

    return "Documentos de negócio cadastrados:\n" + "\n".join(partes)


def pick_chart_axes(resultado: Dict[str, Any]) -> Optional[Tuple[List[str], List[float], str]]:
    """
    Auto-detect categorical and numerical columns for charting
    """
    cols = resultado.get("colunas", [])
    rows = resultado.get("dados", [])
    if not cols or not rows:
        return None

    # Try to detect first categorical column (string-ish)
    cat_idx = None
    for i, c in enumerate(cols):
        sample = [r.get(c) for r in rows[:10]]
        non_num = 0
        for v in sample:
            try:
                float(v)
            except:
                non_num += 1
        if non_num >= max(1, len(sample) // 2):
            cat_idx = i
            break

    # If no categorical column found, use column 0 as label
    if cat_idx is None:
        cat_idx = 0

    # Try to find a numerical column different from categorical
    num_idx = None
    for j, c in enumerate(cols):
        if j == cat_idx:
            continue
        ok = True
        for v in [r.get(c) for r in rows[:10]]:
            try:
                float(v)
            except:
                ok = False
                break
        if ok:
            num_idx = j
            break

    if num_idx is None:
        return None

    labels = [str(r.get(cols[cat_idx])) for r in rows]
    values = []
    for r in rows:
        try:
            values.append(float(r.get(cols[num_idx]) or 0))
        except:
            values.append(0.0)

    title = f"{cols[num_idx]} por {cols[cat_idx]}"
    return labels, values, title


def make_bar_chart_base64_generic(resultado: Dict[str, Any]) -> Optional[str]:
    """
    Generate a bar chart from query results and return as base64
    """
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return None

    picked = pick_chart_axes(resultado)
    if not picked:
        return None

    labels, values, title = picked

    fig = plt.figure()
    plt.bar(labels, values)
    plt.xticks(rotation=45, ha="right")
    plt.title(title)
    plt.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)

    return base64.b64encode(buf.getvalue()).decode()


def insights_from_llm(pergunta: str, resultado: Dict[str, Any], biz_context: str) -> str:
    """
    Generate business insights from query results using LLM
    """
    preview_rows = resultado.get("dados", [])[:10]
    preview_cols = resultado.get("colunas", [])
    preview_text = f"Colunas: {preview_cols}\nAmostra (até 10 linhas): {preview_rows}"

    system = (
        "Você é um analista de BI. Explique resultados em linguagem de negócio, "
        "conectando com o contexto fornecido, sem jargões técnicos desnecessários. "
        "Seja objetivo."
    )
    user = (
        f"{biz_context}\n\n"
        f"Pergunta do usuário: {pergunta}\n\n"
        f"Prévia dos dados (tabela):\n{preview_text}\n\n"
        "Escreva uma síntese de até 8 linhas com o que é mais relevante, "
        "seguida de 3 pontos de atenção / próximos passos."
    )

    if settings.DISABLE_AZURE_LLM:
        return "Insights desativados em ambiente de teste (DISABLE_AZURE_LLM=1)."

    payload = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "temperature": 0.2,
        "max_tokens": 500,
        "top_p": 0.9
    }
    headers = {
        "Content-Type": "application/json",
        "api-key": settings.AZURE_OPENAI_API_KEY
    }
    url = (
        f"{settings.AZURE_OPENAI_ENDPOINT}/openai/deployments/"
        f"{settings.AZURE_OPENAI_DEPLOYMENT}/chat/completions?"
        f"api-version={settings.AZURE_OPENAI_API_VERSION}"
    )

    try:
        with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            r = client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"(Não foi possível gerar insights agora: {e})"
