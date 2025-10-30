"""
Document models - MVC2 Pattern
MODEL = Entidade + Lógica de Acesso a Dados
"""
from typing import Optional, Dict, Any, List
from sqlalchemy import JSON, Column, Integer
from sqlmodel import SQLModel, Field, Relationship, Session, select


class BizDocument(SQLModel, table=True):
    """
    MODEL em MVC2 - BizDocument

    Responsabilidades:
    - Estrutura da tabela
    - Lógica de acesso a dados (CRUD)
    """
    __tablename__ = "biz_documents"

    id: Optional[int] = Field(default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True))
    org_id: str = Field(foreign_key="orgs.id", index=True)
    title: str
    metadata_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    # Relationships
    organization: Optional["Organization"] = Relationship(back_populates="documents")

    # ============================================================
    # MÉTODOS DE ACESSO A DADOS (parte do Model em MVC2)
    # ============================================================

    @classmethod
    def get_by_id(cls, db: Session, doc_id: int) -> Optional["BizDocument"]:
        """Buscar documento por ID"""
        return db.get(cls, doc_id)

    @classmethod
    def create(cls, db: Session, org_id: str, title: str, metadata_json: dict = None) -> "BizDocument":
        """Criar novo documento"""
        db_doc = cls(
            org_id=org_id,
            title=title,
            metadata_json=metadata_json or {}
        )
        db.add(db_doc)
        db.commit()
        db.refresh(db_doc)
        return db_doc

    def update(self, db: Session, **kwargs) -> "BizDocument":
        """Atualizar documento"""
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        db.add(self)
        db.commit()
        db.refresh(self)
        return self

    def delete(self, db: Session) -> bool:
        """Deletar documento"""
        db.delete(self)
        db.commit()
        return True

    @classmethod
    def list_by_org(cls, db: Session, org_id: str, skip: int = 0, limit: int = 100) -> List["BizDocument"]:
        """Listar documentos de uma organização"""
        return db.exec(
            select(cls)
            .where(cls.org_id == org_id)
            .offset(skip)
            .limit(limit)
        ).all()


class QueryAudit(SQLModel, table=True):
    """Auditoria de queries executadas"""
    __tablename__ = "query_audit"

    id: Optional[int] = Field(default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True))
    org_id: str = Field(index=True)
    schema_used: str
    prompt_snip: str
    sql_text: str
    row_count: Optional[int] = None
    duration_ms: Optional[int] = None


# ============================================================
# DTOs (Request/Response)
# ============================================================

class DocumentCreate(SQLModel):
    """DTO para criar documento"""
    titulo: str
    conteudo: str
    tipo: str  # 'data_dictionary', 'business_rules', etc


class DocumentUpdate(SQLModel):
    """DTO para atualizar documento"""
    titulo: Optional[str] = None
    conteudo: Optional[str] = None
    tipo: Optional[str] = None


class DocumentResponse(SQLModel):
    """DTO para resposta de documento"""
    id: int
    org_id: str
    title: str
    metadata_json: Dict[str, Any]
