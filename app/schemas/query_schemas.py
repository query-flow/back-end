from pydantic import BaseModel


class PerguntaOrg(BaseModel):
    org_id: str
    pergunta: str
    max_linhas: int = 100
    enrich: bool = True


class PerguntaDireta(BaseModel):
    database_url: str
    pergunta: str
    max_linhas: int = 100
