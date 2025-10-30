"""
Member management endpoints (admin only) - MVC2 Pattern
"""
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.database import get_db
from app.core.security import generate_invite_token
from app.core.auth import get_current_user, require_org_admin_access, require_org_access
from app.models import User, Organization, OrgMember
from app.schemas import (
    AuthedUser,
    InviteMemberRequest,
    InviteMemberResponse,
    ListMembersResponse,
    MemberInfo,
    UpdateMemberRoleRequest,
    UpdateMemberRoleResponse,
    RemoveMemberResponse,
)

router = APIRouter(prefix="/members", tags=["Members"])


@router.post("/invite", response_model=InviteMemberResponse)
def invite_member(
    p: InviteMemberRequest,
    current_user: AuthedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Convidar novo membro para a organização (somente admin).

    Fluxo:
    1. Admin envia email + nome do novo membro
    2. Sistema cria usuário com status='invited'
    3. Sistema gera invite_token válido por 7 dias
    4. Admin envia token para o membro (por email, por exemplo)
    5. Membro usa /auth/accept-invite para ativar conta

    Restrições:
    - Somente org_admin pode convidar
    - Email não pode já estar cadastrado
    """
    # Verificar se é admin da organização
    require_org_admin_access(p.org_id, current_user, db)

    # Verificar se email já existe
    existing_user = db.exec(
        select(User).where(User.email == p.email)
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail=f"Email '{p.email}' já cadastrado no sistema"
        )

    # Verificar se organização existe
    org = db.get(Organization, p.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada")

    # Gerar invite token
    invite_token = generate_invite_token()
    invite_expires = datetime.utcnow() + timedelta(days=7)

    # Criar usuário com status='invited'
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        name=p.name,
        email=p.email,
        status="invited",
        role="user",  # Campo legado
        invite_token=invite_token,
        invite_expires=invite_expires,
        password_hash=None  # Será definido ao aceitar convite
    )
    db.add(user)

    # CONTROLLER chama MODEL
    org_member = OrgMember.create(
        db=db,
        user_id=user_id,
        org_id=p.org_id,
        role_in_org="member"
    )

    db.commit()
    db.refresh(user)

    return InviteMemberResponse(
        user_id=user_id,
        email=user.email,
        name=user.name,
        status=user.status,
        invite_token=invite_token,
        invite_expires=invite_expires.isoformat(),
        message=f"Membro convidado com sucesso. Envie o token para {p.email}"
    )


@router.get("/{org_id}", response_model=ListMembersResponse)
def list_members(
    org_id: str,
    current_user: AuthedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Listar todos os membros de uma organização.

    Retorna:
    - Lista de membros com role, status, email, etc.

    Restrições:
    - Usuário deve ter acesso à organização (admin ou member)
    """
    # Verificar acesso à organização
    require_org_access(org_id, current_user, db)

    # Buscar organização
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada")

    # CONTROLLER chama MODEL
    org_members = OrgMember.list_by_org(db=db, org_id=org_id)

    members_info = []
    for om in org_members:
        user = db.get(User, om.user_id)
        if user:
            members_info.append(
                MemberInfo(
                    user_id=user.id,
                    name=user.name,
                    email=user.email,
                    role_in_org=om.role_in_org,
                    status=user.status
                )
            )

    return ListMembersResponse(
        org_id=org_id,
        org_name=org.name,
        members=members_info
    )


@router.put("/{org_id}/{user_id}", response_model=UpdateMemberRoleResponse)
def update_member_role(
    org_id: str,
    user_id: str,
    p: UpdateMemberRoleRequest,
    current_user: AuthedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Atualizar role de um membro (somente admin).

    Permite:
    - Promover member → org_admin
    - Rebaixar org_admin → member

    Restrições:
    - Somente org_admin pode atualizar roles
    - Não pode remover o próprio admin se for o último
    """
    # Verificar se é admin da organização
    require_org_admin_access(org_id, current_user, db)

    # Validar role
    if p.role_in_org not in ("org_admin", "member"):
        raise HTTPException(
            status_code=400,
            detail="Role inválida. Use 'org_admin' ou 'member'"
        )

    # CONTROLLER chama MODEL
    org_member = OrgMember.get_member(db=db, user_id=user_id, org_id=org_id)

    if not org_member:
        raise HTTPException(
            status_code=404,
            detail="Membro não encontrado nesta organização"
        )

    # Verificar se está tentando rebaixar o último admin
    if org_member.role_in_org == "org_admin" and p.role_in_org == "member":
        admin_count = db.exec(
            select(OrgMember).where(
                OrgMember.org_id == org_id,
                OrgMember.role_in_org == "org_admin"
            )
        ).all()

        if len(admin_count) == 1:
            raise HTTPException(
                status_code=400,
                detail="Não é possível rebaixar o último administrador da organização"
            )

    # CONTROLLER chama MODEL
    org_member.update_role(db=db, role_in_org=p.role_in_org)

    user = db.get(User, user_id)

    return UpdateMemberRoleResponse(
        user_id=user_id,
        email=user.email,
        role_in_org=p.role_in_org,
        message=f"Role atualizada para '{p.role_in_org}' com sucesso"
    )


@router.delete("/{org_id}/{user_id}", response_model=RemoveMemberResponse)
def remove_member(
    org_id: str,
    user_id: str,
    current_user: AuthedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Remover membro de uma organização (somente admin).

    Comportamento:
    - Remove vínculo OrgMember
    - Usuário continua existindo (pode ser convidado para outra org)
    - Se usuário não tiver mais organizações, pode ser marcado como inativo

    Restrições:
    - Somente org_admin pode remover
    - Não pode remover o último admin
    - Não pode remover a si mesmo se for o último admin
    """
    # Verificar se é admin da organização
    require_org_admin_access(org_id, current_user, db)

    # CONTROLLER chama MODEL
    org_member = OrgMember.get_member(db=db, user_id=user_id, org_id=org_id)

    if not org_member:
        raise HTTPException(
            status_code=404,
            detail="Membro não encontrado nesta organização"
        )

    # Verificar se está tentando remover o último admin
    if org_member.role_in_org == "org_admin":
        admin_count = db.exec(
            select(OrgMember).where(
                OrgMember.org_id == org_id,
                OrgMember.role_in_org == "org_admin"
            )
        ).all()

        if len(admin_count) == 1:
            raise HTTPException(
                status_code=400,
                detail="Não é possível remover o último administrador da organização"
            )

    user = db.get(User, user_id)

    # CONTROLLER chama MODEL
    org_member.delete(db=db)

    return RemoveMemberResponse(
        user_id=user_id,
        email=user.email,
        message=f"Membro '{user.email}' removido da organização com sucesso"
    )
