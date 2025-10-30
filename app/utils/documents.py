import re
import json
import httpx
from typing import Dict, Any
from io import BytesIO
from fastapi import UploadFile

from app.core.config import settings


def extract_text_from_upload(file: UploadFile) -> str:
    """
    Extract text content from uploaded file (txt, pdf, docx)
    """
    content = file.file.read()
    name = (file.filename or "").lower()
    ctype = (file.content_type or "").lower()
    text = ""

    def safe_decode(b: bytes) -> str:
        for enc in ("utf-8", "latin-1", "utf-16"):
            try:
                return b.decode(enc)
            except:
                continue
        return ""

    if name.endswith(".txt") or ctype.startswith("text/"):
        text = safe_decode(content)

    elif name.endswith(".pdf") or "pdf" in ctype:
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(BytesIO(content))
            pages = []
            for p in reader.pages:
                pages.append(p.extract_text() or "")
            text = "\n".join(pages)
        except Exception:
            text = safe_decode(content)

    elif name.endswith(".docx") or "officedocument.wordprocessingml.document" in ctype:
        try:
            import docx
            doc = docx.Document(BytesIO(content))
            text = "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            text = safe_decode(content)

    else:
        # Fallback to raw text
        text = safe_decode(content)

    return (text or "").strip()


def summarize_business_metadata(raw_text: str) -> Dict[str, Any]:
    """
    Generate structured metadata from document text using LLM or heuristics
    """
    base_meta = {
        "summary": "",
        "kpis": [],
        "goals": [],
        "timeframe": "",
        "notes": "",
        "source_kind": "uploaded_document"
    }

    if not raw_text:
        base_meta["summary"] = "Documento vazio ou ilegível."
        return base_meta

    if (
        settings.DISABLE_AZURE_LLM
        or not settings.AZURE_OPENAI_API_KEY
        or not settings.AZURE_OPENAI_DEPLOYMENT
        or not settings.AZURE_OPENAI_ENDPOINT
    ):
        # Simple heuristics
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
        base_meta["summary"] = " ".join(lines[:5])[:600]

        nums = re.findall(r"\b\d+(?:[.,]\d+)?\b", raw_text)
        if nums:
            base_meta["kpis"] = [{
                "name": "valores_numericos_detectados",
                "values_sample": nums[:10]
            }]

        goals = []
        for m in re.findall(r"(meta|objetivo|target)[:\- ]+(.{0,120})", raw_text, flags=re.I):
            goals.append(m[1].strip())
        base_meta["goals"] = goals[:8]

        return base_meta

    # Use LLM for extraction
    system = (
        "Você extrai metadados de documentos de contexto de negócio, devolvendo JSON com as chaves: "
        "summary (string curta), kpis (lista de {name, formula?, current?, target?, unit?}), "
        "goals (lista de strings), timeframe (string), notes (string). Responda somente JSON."
    )
    user = f"Documento (texto puro):\n{raw_text[:12000]}"

    payload = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "temperature": 0.1,
        "max_tokens": 900,
        "top_p": 0.95
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

    content = ""
    try:
        with httpx.Client(timeout=httpx.Timeout(40.0, connect=10.0)) as client:
            r = client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()

        content = data["choices"][0]["message"]["content"]

        # Limpar markdown se houver (```json ... ```)
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # Se conteúdo está vazio, usar heurísticas
        if not content:
            lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
            base_meta["summary"] = " ".join(lines[:5])[:600]
            return base_meta

        meta = json.loads(content)

        if isinstance(meta, dict):
            meta["source_kind"] = "uploaded_document"
            return meta

        base_meta["summary"] = str(meta)[:800]
        return base_meta

    except json.JSONDecodeError as e:
        # LLM retornou texto não-JSON, usar como resumo
        if content and len(content) > 0:
            base_meta["summary"] = content[:800]
        else:
            lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
            base_meta["summary"] = " ".join(lines[:5])[:600]
        return base_meta

    except Exception as e:
        base_meta["summary"] = f"Falha ao usar LLM: {e}"
        return base_meta
