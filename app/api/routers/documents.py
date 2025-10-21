from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import require_admin
from app.models import Org, BizDocument
from app.schemas import AdminDocManualCreate, AuthedUser
from app.services.document_service import extract_text_from_upload, summarize_business_metadata

router = APIRouter(prefix="/admin/orgs/{org_id}/documents", tags=["Documents"])


@router.post("", response_model=dict)
def add_document(
    org_id: str,
    payload: AdminDocManualCreate,
    _u: AuthedUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Add a business document with manual metadata
    """
    org = db.get(Org, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="org não encontrada.")

    doc = BizDocument(
        org_id=org_id,
        title=payload.title,
        metadata_json=payload.metadata_json or {}
    )
    db.add(doc)
    db.commit()

    return {"ok": True, "doc_id": doc.id, "org_id": org_id}


@router.get("", response_model=dict)
def list_documents(
    org_id: str,
    _u: AuthedUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    List all business documents for an organization
    """
    org = db.get(Org, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="org não encontrada.")

    docs = db.query(BizDocument).filter_by(org_id=org_id).all()
    return {
        "org_id": org_id,
        "documents": [
            {"id": d.id, "title": d.title, "metadata_json": d.metadata_json}
            for d in docs
        ]
    }


@router.post("/extract", response_model=dict)
def extract_document(
    org_id: str,
    title: str = Form(...),
    file: UploadFile = File(...),
    _u: AuthedUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Upload and extract metadata from a business document (PDF, DOCX, TXT)
    """
    org = db.get(Org, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="org não encontrada.")

    raw_text = extract_text_from_upload(file)
    meta = summarize_business_metadata(raw_text)

    doc = BizDocument(org_id=org_id, title=title, metadata_json=meta)
    db.add(doc)
    db.commit()

    return {
        "ok": True,
        "doc_id": doc.id,
        "org_id": org_id,
        "title": title,
        "meta_preview": meta
    }
