"""
User Model - MVC Pattern
MODEL = Entidade + Lógica de Acesso a Dados
"""
from typing import List, Optional
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship, Session, select


class User(SQLModel, table=True):
    """
    MODEL em MVC

    Responsabilidades:
    - Estrutura da tabela (atributos)
    - Lógica de acesso a dados (métodos CRUD)
    - Validações de negócio
    """
    __tablename__ = "users"

    id: Optional[str] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    email: str = Field(unique=True, index=True)

    # JWT Authentication
    password_hash: Optional[str] = None
    status: str = Field(default="active")  # 'active' | 'inactive' | 'invited'
    password_changed_at: Optional[datetime] = None

    # Invitation system
    invite_token: Optional[str] = Field(default=None, unique=True, index=True)
    invite_expires: Optional[datetime] = None

    # Legacy (will be removed in future migration)
    api_key_sha: Optional[str] = Field(default=None, unique=True)

    # Relationships
    org_links: List["OrgMember"] = Relationship(back_populates="user")

    # ============================================================
    # MÉTODOS DE ACESSO A DADOS (parte do Model em MVC)
    # ============================================================

    @classmethod
    def get_by_email(cls, db: Session, email: str) -> Optional["User"]:
        """Buscar usuário por email"""
        return db.exec(select(cls).where(cls.email == email)).first()

    @classmethod
    def get_by_id(cls, db: Session, user_id: str) -> Optional["User"]:
        """Buscar usuário por ID"""
        return db.get(cls, user_id)

    @classmethod
    def create(cls, db: Session, **user_data) -> "User":
        """Criar novo usuário"""
        db_user = cls(**user_data)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

    def update(self, db: Session, **kwargs) -> "User":
        """Atualizar usuário"""
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        db.add(self)
        db.commit()
        db.refresh(self)
        return self

    def delete(self, db: Session) -> bool:
        """Deletar usuário"""
        db.delete(self)
        db.commit()
        return True

    @classmethod
    def list_all(cls, db: Session, skip: int = 0, limit: int = 100) -> List["User"]:
        """Listar todos os usuários"""
        return db.exec(select(cls).offset(skip).limit(limit)).all()


# ============================================================
# DTOs (Request/Response) - Mesmo arquivo, menos código!
# ============================================================

class UserCreate(SQLModel):
    """DTO para criar usuário"""
    email: str
    name: str
    password: str


class UserUpdate(SQLModel):
    """DTO para atualizar usuário"""
    name: Optional[str] = None
    email: Optional[str] = None


class UserResponse(SQLModel):
    """DTO para resposta de usuário"""
    id: str
    name: str
    email: str
    status: str
