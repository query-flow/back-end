from pydantic import BaseModel
from typing import Optional


class PerguntaOrg(BaseModel):
    pergunta: str
    max_linhas: int = 10
    enrich: bool = True

    # For clarification flow
    clarification_id: Optional[str] = None
    clarifications: Optional[dict] = None

    # For conversation flow
    conversation_id: Optional[str] = None


class PerguntaDireta(BaseModel):
    database_url: str
    pergunta: str
    max_linhas: int = 10
