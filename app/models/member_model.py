"""
Member models - MVC2 Pattern
MODEL = Entidade + Lógica de Acesso a Dados
"""
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship, Session, select


class OrgMember(SQLModel, table=True):
    """
    MODEL em MVC2 - OrgMember

    Junction table: User <-> Organization
    Define o papel de um usuário dentro de uma organização.

    Responsabilidades:
    - Estrutura da tabela
    - Lógica de acesso a dados (CRUD)
    """
    __tablename__ = "org_members"

    user_id: str = Field(foreign_key="users.id", primary_key=True)
    org_id: str = Field(foreign_key="orgs.id", primary_key=True)
    role_in_org: str = Field(default="member")  # 'admin' | 'member'

    # Relationships
    user: Optional["User"] = Relationship(back_populates="org_links")
    organization: Optional["Organization"] = Relationship(back_populates="members")

    # ============================================================
    # MÉTODOS DE ACESSO A DADOS (parte do Model em MVC2)
    # ============================================================

    @classmethod
    def get_member(cls, db: Session, user_id: str, org_id: str) -> Optional["OrgMember"]:
        """Buscar membro específico"""
        return db.exec(
            select(cls).where(
                cls.user_id == user_id,
                cls.org_id == org_id
            )
        ).first()

    @classmethod
    def create(cls, db: Session, user_id: str, org_id: str, role_in_org: str = "member") -> "OrgMember":
        """Adicionar membro à organização"""
        db_member = cls(
            user_id=user_id,
            org_id=org_id,
            role_in_org=role_in_org
        )
        db.add(db_member)
        db.commit()
        db.refresh(db_member)
        return db_member

    def update_role(self, db: Session, role_in_org: str) -> "OrgMember":
        """Atualizar papel do membro"""
        self.role_in_org = role_in_org
        db.add(self)
        db.commit()
        db.refresh(self)
        return self

    def delete(self, db: Session) -> bool:
        """Remover membro da organização"""
        db.delete(self)
        db.commit()
        return True

    @classmethod
    def list_by_org(cls, db: Session, org_id: str, skip: int = 0, limit: int = 100) -> List["OrgMember"]:
        """Listar membros de uma organização"""
        return db.exec(
            select(cls)
            .where(cls.org_id == org_id)
            .offset(skip)
            .limit(limit)
        ).all()

    @classmethod
    def list_by_user(cls, db: Session, user_id: str) -> List["OrgMember"]:
        """Listar organizações de um usuário"""
        return db.exec(
            select(cls).where(cls.user_id == user_id)
        ).all()


# ============================================================
# DTOs (Request/Response)
# ============================================================

class MemberCreate(SQLModel):
    """DTO para adicionar membro à organização"""
    email: str
    name: str
    role_in_org: str = "member"


class MemberUpdate(SQLModel):
    """DTO para atualizar papel do membro"""
    role_in_org: str


class MemberResponse(SQLModel):
    """DTO para resposta de membro"""
    user_id: str
    org_id: str
    role_in_org: str
