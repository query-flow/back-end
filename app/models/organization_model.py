"""
Organization models - MVC2 Pattern
MODEL = Entidade + Lógica de Acesso a Dados
"""
from typing import List, Optional, Dict, Any
from sqlalchemy import JSON, Column
from sqlmodel import SQLModel, Field, Relationship, Session, select


class Organization(SQLModel, table=True):
    """
    MODEL em MVC2 - Organization

    Responsabilidades:
    - Estrutura da tabela
    - Lógica de acesso a dados (CRUD)
    """
    __tablename__ = "orgs"

    id: Optional[str] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    status: str = Field(default="active")  # 'active' | 'inactive'

    # Relationships
    connection: Optional["OrgDbConnection"] = Relationship(back_populates="organization")
    allowed_schemas: List["OrgAllowedSchema"] = Relationship(back_populates="organization")
    documents: List["BizDocument"] = Relationship(back_populates="organization")
    members: List["OrgMember"] = Relationship(back_populates="organization")

    # ============================================================
    # MÉTODOS DE ACESSO A DADOS (parte do Model em MVC2)
    # ============================================================

    @classmethod
    def get_by_id(cls, db: Session, org_id: str) -> Optional["Organization"]:
        """Buscar organização por ID"""
        return db.get(cls, org_id)

    @classmethod
    def get_by_name(cls, db: Session, name: str) -> Optional["Organization"]:
        """Buscar organização por nome"""
        return db.exec(select(cls).where(cls.name == name)).first()

    @classmethod
    def create(cls, db: Session, **org_data) -> "Organization":
        """Criar nova organização"""
        db_org = cls(**org_data)
        db.add(db_org)
        db.commit()
        db.refresh(db_org)
        return db_org

    def update(self, db: Session, **kwargs) -> "Organization":
        """Atualizar organização"""
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        db.add(self)
        db.commit()
        db.refresh(self)
        return self

    def soft_delete(self, db: Session) -> bool:
        """Deletar organização (soft delete)"""
        self.status = "inactive"
        db.add(self)
        db.commit()
        return True

    @classmethod
    def list_all(cls, db: Session, skip: int = 0, limit: int = 100) -> List["Organization"]:
        """Listar todas as organizações"""
        return db.exec(select(cls).offset(skip).limit(limit)).all()


class OrgDbConnection(SQLModel, table=True):
    """Credenciais da conexão com banco de dados da organização"""
    __tablename__ = "org_db_connections"

    org_id: str = Field(foreign_key="orgs.id", primary_key=True)
    driver: str  # 'mysql', 'postgresql', etc
    host: str
    port: int = Field(default=3306)
    username: str
    password_enc: str  # Criptografado com Fernet
    database_name: str
    options_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    # Relationships
    organization: Optional[Organization] = Relationship(back_populates="connection")


class OrgAllowedSchema(SQLModel, table=True):
    """Schemas permitidos para uma organização"""
    __tablename__ = "org_allowed_schemas"

    org_id: str = Field(foreign_key="orgs.id", primary_key=True)
    schema_name: str = Field(primary_key=True)

    # Relationships
    organization: Optional[Organization] = Relationship(back_populates="allowed_schemas")


# ============================================================
# DTOs (Request/Response)
# ============================================================

class OrganizationCreate(SQLModel):
    """DTO para criar organização"""
    nome: str
    db_type: str
    db_host: str
    db_port: int = 3306
    db_name: str
    db_user: str
    db_password: str


class OrganizationUpdate(SQLModel):
    """DTO para atualizar organização"""
    nome: Optional[str] = None
    status: Optional[str] = None


class OrganizationResponse(SQLModel):
    """DTO para resposta de organização"""
    id: str
    name: str
    status: str


class OrgDbConnectionResponse(SQLModel):
    """DTO para resposta de conexão"""
    org_id: str
    driver: str
    host: str
    port: int
    database_name: str
