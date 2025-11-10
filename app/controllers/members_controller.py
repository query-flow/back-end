"""
Member management endpoints (admin only) - MVC2 Pattern
"""
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.database import get_db
from app.core.security import generate_invite_token
from app.core.auth import get_current_user, get_user_org_id
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
    - Somente admin pode convidar
    - Email não pode já estar cadastrado
    """
    # Get user's org_id and check if user is admin
    org_id = get_user_org_id(current_user)

    # Verificar se é admin da organização
    org_member_admin = db.exec(
        select(OrgMember).where(
            OrgMember.user_id == current_user.id,
            OrgMember.org_id == org_id,
            OrgMember.role_in_org == "admin"
        )
    ).first()

    if not org_member_admin:
        raise HTTPException(
            status_code=403,
            detail="Acesso restrito a administradores desta organização"
        )

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
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada")

    # Validar role_in_org
    role = p.role_in_org or "member"
    if role not in ("admin", "member"):
        raise HTTPException(
            status_code=400,
            detail="Role inválida. Use 'admin' ou 'member'"
        )

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
        invite_token=invite_token,
        invite_expires=invite_expires,
        password_hash=None  # Será definido ao aceitar convite
    )
    db.add(user)

    # CONTROLLER chama MODEL com role especificada
    org_member = OrgMember.create(
        db=db,
        user_id=user_id,
        org_id=org_id,
        role_in_org=role
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


@router.get("", response_model=ListMembersResponse)
def list_members(
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
    # Get user's org_id
    org_id = get_user_org_id(current_user)

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


@router.put("/{user_id}", response_model=UpdateMemberRoleResponse)
def update_member_role(
    user_id: str,
    p: UpdateMemberRoleRequest,
    current_user: AuthedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Atualizar role de um membro (somente admin).

    Permite:
    - Promover member → admin
    - Rebaixar admin → member

    Restrições:
    - Somente admin pode atualizar roles
    - Não pode remover o próprio admin se for o último
    """
    # Get user's org_id and check if user is admin
    org_id = get_user_org_id(current_user)

    # Verificar se é admin da organização
    org_member_admin = db.exec(
        select(OrgMember).where(
            OrgMember.user_id == current_user.id,
            OrgMember.org_id == org_id,
            OrgMember.role_in_org == "admin"
        )
    ).first()

    if not org_member_admin:
        raise HTTPException(
            status_code=403,
            detail="Acesso restrito a administradores desta organização"
        )

    # Validar role
    if p.role_in_org not in ("admin", "member"):
        raise HTTPException(
            status_code=400,
            detail="Role inválida. Use 'admin' ou 'member'"
        )

    # CONTROLLER chama MODEL
    org_member = OrgMember.get_member(db=db, user_id=user_id, org_id=org_id)

    if not org_member:
        raise HTTPException(
            status_code=404,
            detail="Membro não encontrado nesta organização"
        )

    # Verificar se está tentando rebaixar o último admin
    if org_member.role_in_org == "admin" and p.role_in_org == "member":
        admin_count = db.exec(
            select(OrgMember).where(
                OrgMember.org_id == org_id,
                OrgMember.role_in_org == "admin"
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


@router.delete("/{user_id}", response_model=RemoveMemberResponse)
def remove_member(
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
    - Somente admin pode remover
    - Não pode remover o último admin
    - Não pode remover a si mesmo se for o último admin
    """
    # Get user's org_id and check if user is admin
    org_id = get_user_org_id(current_user)

    # Verificar se é admin da organização
    org_member_admin = db.exec(
        select(OrgMember).where(
            OrgMember.user_id == current_user.id,
            OrgMember.org_id == org_id,
            OrgMember.role_in_org == "admin"
        )
    ).first()

    if not org_member_admin:
        raise HTTPException(
            status_code=403,
            detail="Acesso restrito a administradores desta organização"
        )

    # CONTROLLER chama MODEL
    org_member = OrgMember.get_member(db=db, user_id=user_id, org_id=org_id)

    if not org_member:
        raise HTTPException(
            status_code=404,
            detail="Membro não encontrado nesta organização"
        )

    # Verificar se está tentando remover o último admin
    if org_member.role_in_org == "admin":
        admin_count = db.exec(
            select(OrgMember).where(
                OrgMember.org_id == org_id,
                OrgMember.role_in_org == "admin"
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
