from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_context, require
from app.db.session import get_db
from app.models import (
    ApprovedClaim, ApprovedFact, BrandAsset, BrandGuideline, DocumentVersion, GuidelineVersion,
    KnowledgeDocument, Membership, User,
)
from app.routers.common import clamp_page, paginate, save_upload
from app.schemas import (
    AssetCreate, ClaimCreate, DocumentCreate, DocumentUpdate, FactCreate, FactUpdate,
    GuidelineCreate, GuidelineUpdate,
)
from app.services.audit import record_audit
from app.services.impact import create_impacts
from app.services.knowledge_index import build_index, search
from app.services.extract import ExtractionError, extract_text as extract_document_text
from app.services.serializers import (
    approved_claim_out, asset_out, document_out, fact_out, guideline_out, user_brief,
)

def _deny_creators(ctx: CurrentUser = Depends(get_context)) -> None:
    """Creators never read the raw private vault directly; evidence is surfaced
    through the AI review of their own submissions instead."""
    if ctx.role == "content_creator":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Your role cannot access the private knowledge vault. Ask your manager "
            "to add the information to your campaign brief instead.",
        )


router = APIRouter(prefix="/knowledge", tags=["Knowledge vault"], dependencies=[Depends(_deny_creators)])


def _document_or_404(db: Session, org_id: str, document_id: str) -> KnowledgeDocument:
    doc = db.get(KnowledgeDocument, document_id)
    if not doc or doc.organisation_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return doc


def _fact_or_404(db: Session, org_id: str, fact_id: str) -> ApprovedFact:
    fact = db.get(ApprovedFact, fact_id)
    if not fact or fact.organisation_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Approved fact not found")
    return fact


def _claim_or_404(db: Session, org_id: str, claim_id: str) -> ApprovedClaim:
    claim = db.get(ApprovedClaim, claim_id)
    if not claim or claim.organisation_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Claim not found")
    return claim


def _guideline_or_404(db: Session, org_id: str, guideline_id: str) -> BrandGuideline:
    guideline = db.get(BrandGuideline, guideline_id)
    if not guideline or guideline.organisation_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Guideline not found")
    return guideline


def _ensure_approval_rights(ctx: CurrentUser, requested_status: str, current_status: str | None = None) -> None:
    if requested_status == "approved" and current_status != "approved" and not ctx.can("approve_knowledge"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only an approver or administrator can approve knowledge records.",
        )


# --------------------------------------------------------------------------- documents


@router.get("/documents")
def list_documents(
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
    q: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    doc_type: str | None = None,
    category: str | None = None,
    review: str | None = Query(default=None, description="overdue | due_soon"),
    page: int = 1,
    page_size: int = 50,
):
    page, page_size = clamp_page(page, page_size)
    filters = [KnowledgeDocument.organisation_id == ctx.org_id]
    if q:
        like = f"%{q.strip()}%"
        filters.append(or_(
            KnowledgeDocument.title.ilike(like),
            KnowledgeDocument.extracted_text.ilike(like),
            KnowledgeDocument.category.ilike(like),
        ))
    if status_filter:
        filters.append(KnowledgeDocument.status == status_filter)
    if doc_type:
        filters.append(KnowledgeDocument.doc_type == doc_type)
    if category:
        filters.append(KnowledgeDocument.category == category)
    today = date.today()
    if review == "overdue":
        filters.append(KnowledgeDocument.review_date.is_not(None))
        filters.append(KnowledgeDocument.review_date < today)
    elif review == "due_soon":
        filters.append(KnowledgeDocument.review_date.is_not(None))
        filters.append(KnowledgeDocument.review_date >= today)
        filters.append(KnowledgeDocument.review_date <= today + timedelta(days=30))

    total = db.scalar(select(func.count()).select_from(KnowledgeDocument).where(*filters)) or 0
    docs = db.scalars(
        select(KnowledgeDocument).where(*filters)
        .order_by(KnowledgeDocument.updated_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return paginate([document_out(d) for d in docs], total, page, page_size)


@router.post("/documents", status_code=201)
def create_document(
    payload: DocumentCreate,
    ctx: CurrentUser = Depends(require("upload_knowledge")),
    db: Session = Depends(get_db),
):
    _ensure_approval_rights(ctx, payload.status)
    doc = KnowledgeDocument(
        organisation_id=ctx.org_id,
        title=payload.title,
        doc_type=payload.doc_type,
        category=payload.category,
        status=payload.status,
        version=payload.version,
        owner_id=ctx.user.id,
        approved_by=ctx.user.id if payload.status == "approved" else None,
        effective_date=payload.effective_date,
        review_date=payload.review_date,
        extracted_text=payload.text,
        tags=payload.tags or [],
    )
    db.add(doc)
    db.flush()
    db.add(DocumentVersion(
        document_id=doc.id, version=doc.version, content=payload.text,
        change_summary="Initial version", created_by=ctx.user.id,
    ))
    record_audit(
        db, ctx.org_id, ctx.user.id, "knowledge.document.created", "knowledge_document", doc.id,
        doc.title, updated_value=f"v{doc.version} · {payload.doc_type}",
        meta={"status": doc.status},
    )
    db.commit()
    db.refresh(doc)
    return document_out(doc, include_text=True)


@router.post("/documents/upload", status_code=201)
def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    doc_type: str = Form("guideline"),
    category: str = Form("General"),
    doc_status: str = Form("draft", alias="status"),
    effective_date: str | None = Form(None),
    review_date: str | None = Form(None),
    ctx: CurrentUser = Depends(require("upload_knowledge")),
    db: Session = Depends(get_db),
):
    _ensure_approval_rights(ctx, doc_status)
    data = file.file.read()
    try:
        extracted_text = extract_document_text(file.filename or "", data)
    except ExtractionError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    if not extracted_text.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "No readable text was found in this file.")
    extracted = {"text": extracted_text, "pages": []}

    stored_name, stored_path = save_upload(file, data, prefix="knowledge")
    doc = KnowledgeDocument(
        organisation_id=ctx.org_id,
        title=title.strip(),
        doc_type=doc_type,
        category=category,
        status=doc_status,
        version=1,
        owner_id=ctx.user.id,
        approved_by=ctx.user.id if doc_status == "approved" else None,
        effective_date=date.fromisoformat(effective_date) if effective_date else None,
        review_date=date.fromisoformat(review_date) if review_date else None,
        file_name=file.filename,
        file_path=stored_path,
        mime_type=file.content_type,
        extracted_text=extracted["text"],
        page_map=extracted["pages"],
        tags=[],
    )
    db.add(doc)
    db.flush()
    db.add(DocumentVersion(
        document_id=doc.id, version=1, content=extracted["text"],
        change_summary=f"Uploaded {file.filename}", created_by=ctx.user.id,
    ))
    record_audit(
        db, ctx.org_id, ctx.user.id, "knowledge.document.uploaded", "knowledge_document", doc.id,
        doc.title, updated_value=file.filename or stored_name,
        meta={"pages": len(extracted["pages"]), "status": doc_status},
    )
    db.commit()
    db.refresh(doc)
    return document_out(doc, include_text=True)


@router.get("/documents/{document_id}")
def get_document(
    document_id: str,
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
):
    doc = _document_or_404(db, ctx.org_id, document_id)
    versions = db.scalars(
        select(DocumentVersion).where(DocumentVersion.document_id == doc.id)
        .order_by(DocumentVersion.version.desc())
    ).all()
    facts = db.scalars(
        select(ApprovedFact).where(ApprovedFact.document_id == doc.id).order_by(ApprovedFact.key)
    ).all()
    data = document_out(doc, include_text=True)
    data["versions"] = [
        {
            "id": v.id, "version": v.version, "change_summary": v.change_summary,
            "created_by": v.created_by, "created_at": v.created_at.isoformat() if v.created_at else None,
            "char_count": len(v.content or ""),
        }
        for v in versions
    ]
    data["facts"] = [fact_out(f) for f in facts]
    return data


@router.patch("/documents/{document_id}")
def update_document(
    document_id: str,
    payload: DocumentUpdate,
    ctx: CurrentUser = Depends(require("upload_knowledge")),
    db: Session = Depends(get_db),
):
    doc = _document_or_404(db, ctx.org_id, document_id)
    _ensure_approval_rights(ctx, payload.status or "", doc.status)
    text_changed = payload.text is not None and payload.text != doc.extracted_text

    if payload.status is not None:
        doc.status = payload.status
        if payload.status == "approved":
            doc.approved_by = ctx.user.id
    if payload.title is not None:
        doc.title = payload.title
    if payload.doc_type is not None:
        doc.doc_type = payload.doc_type
    if payload.category is not None:
        doc.category = payload.category
    if payload.effective_date is not None:
        doc.effective_date = payload.effective_date
    if payload.review_date is not None:
        doc.review_date = payload.review_date
    if payload.tags is not None:
        doc.tags = payload.tags

    if text_changed:
        doc.extracted_text = payload.text
        doc.version += 1
        # An approved record that changes must be re-approved.
        if doc.status == "approved" and not ctx.can("approve_knowledge"):
            doc.status = "draft"
        db.add(DocumentVersion(
            document_id=doc.id, version=doc.version, content=payload.text,
            change_summary=payload.change_summary or "Document updated",
            created_by=ctx.user.id,
        ))

    record_audit(
        db, ctx.org_id, ctx.user.id, "knowledge.document.updated", "knowledge_document", doc.id,
        doc.title,
        previous_value=f"v{doc.version - 1}" if text_changed else "",
        updated_value=f"v{doc.version}",
        meta={"text_changed": text_changed, "status": doc.status},
    )
    db.commit()
    db.refresh(doc)
    return document_out(doc, include_text=True)


@router.post("/documents/{document_id}/archive")
def archive_document(
    document_id: str,
    ctx: CurrentUser = Depends(require("approve_knowledge")),
    db: Session = Depends(get_db),
):
    doc = _document_or_404(db, ctx.org_id, document_id)
    previous = doc.status
    doc.status = "archived"
    record_audit(
        db, ctx.org_id, ctx.user.id, "knowledge.document.archived", "knowledge_document",
        doc.id, doc.title, previous_value=previous, updated_value="archived",
    )
    db.commit()
    return {"message": "Document archived. It is no longer used as evidence.", "status": doc.status}


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: str,
    ctx: CurrentUser = Depends(require("approve_knowledge")),
    db: Session = Depends(get_db),
):
    doc = _document_or_404(db, ctx.org_id, document_id)
    record_audit(
        db, ctx.org_id, ctx.user.id, "knowledge.document.deleted", "knowledge_document",
        doc.id, doc.title, previous_value=doc.status, updated_value="deleted",
        meta={"file_name": doc.file_name},
    )
    db.delete(doc)
    db.commit()
    return {"message": "Document removed. Linked evidence references are detached where applicable."}


# --------------------------------------------------------------------------- facts


@router.get("/facts")
def list_facts(
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
    q: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    category: str | None = None,
    product: str | None = None,
    page: int = 1,
    page_size: int = 100,
):
    page, page_size = clamp_page(page, page_size)
    filters = [ApprovedFact.organisation_id == ctx.org_id]
    if q:
        like = f"%{q.strip()}%"
        filters.append(or_(ApprovedFact.key.ilike(like), ApprovedFact.value.ilike(like)))
    if status_filter:
        filters.append(ApprovedFact.status == status_filter)
    if category:
        filters.append(ApprovedFact.category == category)
    if product:
        filters.append(ApprovedFact.product == product)
    total = db.scalar(select(func.count()).select_from(ApprovedFact).where(*filters)) or 0
    facts = db.scalars(
        select(ApprovedFact).where(*filters).order_by(ApprovedFact.updated_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return paginate([fact_out(f) for f in facts], total, page, page_size)


@router.post("/facts", status_code=201)
def create_fact(
    payload: FactCreate,
    ctx: CurrentUser = Depends(require("upload_knowledge")),
    db: Session = Depends(get_db),
):
    _ensure_approval_rights(ctx, payload.status)
    if payload.document_id and not db.get(KnowledgeDocument, payload.document_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source document not found")
    fact = ApprovedFact(
        organisation_id=ctx.org_id,
        document_id=payload.document_id,
        key=payload.key,
        value=payload.value,
        product=payload.product,
        category=payload.category,
        status=payload.status,
        approved_by=ctx.user.id if payload.status == "approved" else None,
        effective_date=payload.effective_date,
        review_date=payload.review_date,
        source_locator=payload.source_locator,
    )
    db.add(fact)
    db.flush()
    record_audit(
        db, ctx.org_id, ctx.user.id, "knowledge.fact.created", "fact", fact.id, fact.key,
        updated_value=f"{fact.key}: {fact.value}", meta={"status": fact.status},
    )
    db.commit()
    db.refresh(fact)
    return fact_out(fact)


@router.patch("/facts/{fact_id}")
def update_fact(
    fact_id: str,
    payload: FactUpdate,
    ctx: CurrentUser = Depends(require("upload_knowledge")),
    db: Session = Depends(get_db),
):
    fact = _fact_or_404(db, ctx.org_id, fact_id)
    if payload.status and payload.status == "approved" and fact.status != "approved":
        _ensure_approval_rights(ctx, payload.status)
    previous_value = fact.value
    previous_status = fact.status
    for field in ("key", "value", "product", "category", "source_locator"):
        value = getattr(payload, field)
        if value is not None:
            setattr(fact, field, value)
    if payload.status is not None:
        fact.status = payload.status
        if payload.status == "approved":
            fact.approved_by = ctx.user.id
    if payload.effective_date is not None:
        fact.effective_date = payload.effective_date
    if payload.review_date is not None:
        fact.review_date = payload.review_date

    impacts = []
    value_changed = fact.value != previous_value
    if value_changed and (previous_status == "approved" or fact.status == "approved"):
        impacts = create_impacts(
            db, ctx.org_id, fact.id, previous_value, fact.value, fact.key, ctx.user.id,
        )
    record_audit(
        db, ctx.org_id, ctx.user.id, "knowledge.fact.updated", "fact", fact.id, fact.key,
        previous_value=f"{fact.key}: {previous_value}" if value_changed else "",
        updated_value=f"{fact.key}: {fact.value}",
        meta={"affected_submissions": len(impacts), "status": fact.status},
    )
    db.commit()
    db.refresh(fact)
    return fact_out(fact) | {
        "affected_submissions": len(impacts),
        "impact_ids": [i.id for i in impacts],
    }


@router.delete("/facts/{fact_id}")
def retire_fact(
    fact_id: str,
    ctx: CurrentUser = Depends(require("approve_knowledge")),
    db: Session = Depends(get_db),
):
    fact = _fact_or_404(db, ctx.org_id, fact_id)
    fact.status = "retired"
    record_audit(
        db, ctx.org_id, ctx.user.id, "knowledge.fact.retired", "fact", fact.id, fact.key,
        previous_value=f"{fact.key}: {fact.value}", updated_value="retired",
    )
    db.commit()
    return {"message": "Fact retired. It will no longer be used as evidence.", "status": fact.status}


# --------------------------------------------------------------------------- claims


@router.get("/claims")
def list_claims(
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
    q: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    expiring_within: int | None = Query(default=None, ge=0, le=365),
    page: int = 1,
    page_size: int = 100,
):
    page, page_size = clamp_page(page, page_size)
    filters = [ApprovedClaim.organisation_id == ctx.org_id]
    if q:
        filters.append(ApprovedClaim.claim_text.ilike(f"%{q.strip()}%"))
    if status_filter:
        filters.append(ApprovedClaim.status == status_filter)
    today = date.today()
    if expiring_within is not None:
        filters.append(ApprovedClaim.expiry_date.is_not(None))
        filters.append(ApprovedClaim.expiry_date <= today + timedelta(days=expiring_within))
        filters.append(ApprovedClaim.status == "approved")
    total = db.scalar(select(func.count()).select_from(ApprovedClaim).where(*filters)) or 0
    claims = db.scalars(
        select(ApprovedClaim).where(*filters).order_by(ApprovedClaim.expiry_date.asc().nulls_last())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = []
    for claim in claims:
        item = approved_claim_out(claim)
        item["expired"] = bool(claim.expiry_date and claim.expiry_date < today)
        item["days_to_expiry"] = (claim.expiry_date - today).days if claim.expiry_date else None
        items.append(item)
    return paginate(items, total, page, page_size)


@router.post("/claims", status_code=201)
def create_claim(
    payload: ClaimCreate,
    ctx: CurrentUser = Depends(require("approve_knowledge")),
    db: Session = Depends(get_db),
):
    if payload.evidence_document_id:
        _document_or_404(db, ctx.org_id, payload.evidence_document_id)
    claim = ApprovedClaim(
        organisation_id=ctx.org_id,
        claim_text=payload.claim_text,
        category=payload.category,
        status=payload.status,
        evidence_document_id=payload.evidence_document_id,
        review_date=payload.review_date,
        expiry_date=payload.expiry_date,
        created_by=ctx.user.id,
    )
    db.add(claim)
    db.flush()
    record_audit(
        db, ctx.org_id, ctx.user.id, "knowledge.claim.created", "claim", claim.id,
        claim.claim_text[:120], updated_value=claim.status,
    )
    db.commit()
    db.refresh(claim)
    return approved_claim_out(claim)


@router.patch("/claims/{claim_id}")
def update_claim(
    claim_id: str,
    payload: ClaimCreate,
    ctx: CurrentUser = Depends(require("approve_knowledge")),
    db: Session = Depends(get_db),
):
    claim = _claim_or_404(db, ctx.org_id, claim_id)
    claim.claim_text = payload.claim_text
    claim.category = payload.category
    claim.status = payload.status
    claim.evidence_document_id = payload.evidence_document_id
    claim.review_date = payload.review_date
    claim.expiry_date = payload.expiry_date
    record_audit(
        db, ctx.org_id, ctx.user.id, "knowledge.claim.updated", "claim", claim.id,
        claim.claim_text[:120], updated_value=claim.status,
    )
    db.commit()
    db.refresh(claim)
    return approved_claim_out(claim)


@router.delete("/claims/{claim_id}")
def delete_claim(
    claim_id: str,
    ctx: CurrentUser = Depends(require("approve_knowledge")),
    db: Session = Depends(get_db),
):
    claim = _claim_or_404(db, ctx.org_id, claim_id)
    record_audit(
        db, ctx.org_id, ctx.user.id, "knowledge.claim.deleted", "claim", claim.id,
        claim.claim_text[:120], previous_value=claim.status,
    )
    db.delete(claim)
    db.commit()
    return {"message": "Claim removed from the register."}


# --------------------------------------------------------------------------- guidelines


@router.get("/guidelines")
def list_guidelines(
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
    q: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    category: str | None = None,
):
    filters = [BrandGuideline.organisation_id == ctx.org_id]
    if q:
        like = f"%{q.strip()}%"
        filters.append(or_(BrandGuideline.title.ilike(like), BrandGuideline.content.ilike(like)))
    if status_filter:
        filters.append(BrandGuideline.status == status_filter)
    if category:
        filters.append(BrandGuideline.category == category)
    guidelines = db.scalars(
        select(BrandGuideline).where(*filters).order_by(BrandGuideline.title)
    ).all()
    return {"items": [guideline_out(g) for g in guidelines], "total": len(guidelines)}


@router.post("/guidelines", status_code=201)
def create_guideline(
    payload: GuidelineCreate,
    ctx: CurrentUser = Depends(require("upload_knowledge")),
    db: Session = Depends(get_db),
):
    if payload.status == "approved" and not ctx.can("approve_guidelines"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an approver can approve a guideline.")
    guideline = BrandGuideline(
        organisation_id=ctx.org_id,
        title=payload.title,
        category=payload.category,
        content=payload.content,
        summary=payload.summary,
        status=payload.status,
        version=1,
        owner_id=ctx.user.id,
        effective_date=payload.effective_date,
        review_date=payload.review_date,
    )
    db.add(guideline)
    db.flush()
    db.add(GuidelineVersion(
        guideline_id=guideline.id, version=1, content=payload.content,
        change_summary="Initial version", status=payload.status, created_by=ctx.user.id,
        approved_by=ctx.user.id if payload.status == "approved" else None,
    ))
    record_audit(
        db, ctx.org_id, ctx.user.id, "knowledge.guideline.created", "guideline", guideline.id,
        guideline.title, updated_value=f"v1 · {payload.status}",
    )
    db.commit()
    db.refresh(guideline)
    return guideline_out(guideline)


@router.patch("/guidelines/{guideline_id}")
def update_guideline(
    guideline_id: str,
    payload: GuidelineUpdate,
    ctx: CurrentUser = Depends(require("upload_knowledge")),
    db: Session = Depends(get_db),
):
    guideline = _guideline_or_404(db, ctx.org_id, guideline_id)
    if payload.status == "approved" and guideline.status != "approved" and not ctx.can("approve_guidelines"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an approver can approve a guideline.")
    content_changed = payload.content is not None and payload.content != guideline.content
    previous_version = guideline.version
    if payload.title is not None:
        guideline.title = payload.title
    if payload.category is not None:
        guideline.category = payload.category
    if payload.summary is not None:
        guideline.summary = payload.summary
    if payload.effective_date is not None:
        guideline.effective_date = payload.effective_date
    if payload.review_date is not None:
        guideline.review_date = payload.review_date
    if content_changed:
        guideline.content = payload.content
        guideline.version += 1
        if guideline.status == "approved" and not ctx.can("approve_guidelines"):
            guideline.status = "draft"
    if payload.status is not None:
        guideline.status = payload.status

    if content_changed or payload.status is not None:
        db.add(GuidelineVersion(
            guideline_id=guideline.id, version=guideline.version, content=guideline.content,
            change_summary=payload.change_summary or (
                "Content updated" if content_changed else f"Status set to {guideline.status}"
            ),
            status=guideline.status, created_by=ctx.user.id,
            approved_by=ctx.user.id if guideline.status == "approved" else None,
        ))
    record_audit(
        db, ctx.org_id, ctx.user.id, "knowledge.guideline.updated", "guideline", guideline.id,
        guideline.title, previous_value=f"v{previous_version}", updated_value=f"v{guideline.version}",
        guideline_version=guideline.version, meta={"status": guideline.status},
    )
    db.commit()
    db.refresh(guideline)
    return guideline_out(guideline)


@router.get("/guidelines/{guideline_id}/versions")
def guideline_versions(
    guideline_id: str,
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
):
    guideline = _guideline_or_404(db, ctx.org_id, guideline_id)
    versions = db.scalars(
        select(GuidelineVersion).where(GuidelineVersion.guideline_id == guideline.id)
        .order_by(GuidelineVersion.version.desc(), GuidelineVersion.created_at.desc())
    ).all()
    author_ids = {v.created_by for v in versions if v.created_by}
    authors = {
        u.id: user_brief(u) for u in db.scalars(select(User).where(User.id.in_(author_ids))).all()
    } if author_ids else {}
    return {
        "guideline": guideline_out(guideline),
        "items": [
            {
                "id": v.id, "version": v.version, "content": v.content,
                "change_summary": v.change_summary, "status": v.status,
                "author": authors.get(v.created_by),
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in versions
        ],
    }


@router.post("/guidelines/{guideline_id}/approve")
def approve_guideline(
    guideline_id: str,
    ctx: CurrentUser = Depends(require("approve_guidelines")),
    db: Session = Depends(get_db),
):
    guideline = _guideline_or_404(db, ctx.org_id, guideline_id)
    previous = guideline.status
    guideline.status = "approved"
    guideline.version += 1
    db.add(GuidelineVersion(
        guideline_id=guideline.id, version=guideline.version, content=guideline.content,
        change_summary="Approved for use", status="approved", created_by=ctx.user.id,
        approved_by=ctx.user.id,
    ))
    record_audit(
        db, ctx.org_id, ctx.user.id, "knowledge.guideline.approved", "guideline", guideline.id,
        guideline.title, previous_value=previous, updated_value="approved", decision="approved",
        guideline_version=guideline.version,
    )
    db.commit()
    db.refresh(guideline)
    return guideline_out(guideline)


# --------------------------------------------------------------------------- assets


@router.get("/assets")
def list_assets(
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
    asset_type: str | None = None,
):
    filters = [BrandAsset.organisation_id == ctx.org_id]
    if asset_type:
        filters.append(BrandAsset.asset_type == asset_type)
    assets = db.scalars(select(BrandAsset).where(*filters).order_by(BrandAsset.name)).all()
    return {"items": [asset_out(a) for a in assets], "total": len(assets)}


@router.post("/assets", status_code=201)
def create_asset(
    payload: AssetCreate,
    ctx: CurrentUser = Depends(require("approve_knowledge")),
    db: Session = Depends(get_db),
):
    asset = BrandAsset(
        organisation_id=ctx.org_id,
        name=payload.name,
        asset_type=payload.asset_type,
        color_hex=payload.color_hex,
        notes=payload.notes,
        is_approved=True,
    )
    db.add(asset)
    db.flush()
    record_audit(
        db, ctx.org_id, ctx.user.id, "knowledge.asset.created", "asset", asset.id, asset.name,
        updated_value=asset.color_hex or asset.asset_type,
    )
    db.commit()
    db.refresh(asset)
    return asset_out(asset)


@router.post("/assets/upload", status_code=201)
def upload_asset(
    file: UploadFile = File(...),
    name: str = Form(...),
    asset_type: str = Form("logo"),
    notes: str = Form(""),
    ctx: CurrentUser = Depends(require("approve_knowledge")),
    db: Session = Depends(get_db),
):
    data = file.file.read()
    stored_name, stored_path = save_upload(file, data, prefix="asset")
    asset = BrandAsset(
        organisation_id=ctx.org_id,
        name=name.strip() or file.filename or "Brand asset",
        asset_type=asset_type,
        file_path=stored_path,
        notes=notes,
        is_approved=True,
    )
    db.add(asset)
    db.flush()
    record_audit(
        db, ctx.org_id, ctx.user.id, "knowledge.asset.uploaded", "asset", asset.id,
        asset.name, updated_value=file.filename or stored_name,
    )
    db.commit()
    db.refresh(asset)
    return asset_out(asset)


@router.delete("/assets/{asset_id}")
def delete_asset(
    asset_id: str,
    ctx: CurrentUser = Depends(require("approve_knowledge")),
    db: Session = Depends(get_db),
):
    asset = db.get(BrandAsset, asset_id)
    if not asset or asset.organisation_id != ctx.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    record_audit(
        db, ctx.org_id, ctx.user.id, "knowledge.asset.deleted", "asset", asset.id, asset.name,
        previous_value=asset.color_hex or asset.asset_type,
    )
    db.delete(asset)
    db.commit()
    return {"message": "Asset removed."}


# --------------------------------------------------------------------------- search & overview


@router.get("/search")
def search_knowledge(
    q: str = Query(min_length=2, description="Natural-language evidence query"),
    limit: int = Query(default=8, ge=1, le=25),
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
):
    index = build_index(db, ctx.org_id)
    results = search(index, q, top_k=limit)
    return {
        "query": q,
        "items": [
            {
                "kind": r["kind"],
                "title": r["document_title"],
                "text": r["text"],
                "locator": r.get("locator", ""),
                "score": r["score"],
                "document_id": r.get("document_id"),
                "fact_id": r.get("fact_id"),
                "claim_id": r.get("claim_id"),
                "guideline_id": r.get("guideline_id"),
                "stale": r.get("stale", False),
                "effective_date": r.get("effective_date").isoformat() if r.get("effective_date") else None,
                "review_date": r.get("review_date").isoformat() if r.get("review_date") else None,
            }
            for r in results
        ],
        "index_sources": len(index),
    }


@router.get("/overview")
def knowledge_overview(
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
):
    today = date.today()
    docs = db.scalars(
        select(KnowledgeDocument).where(KnowledgeDocument.organisation_id == ctx.org_id)
    ).all()
    doc_counts: dict[str, int] = {}
    for doc in docs:
        doc_counts[doc.status] = doc_counts.get(doc.status, 0) + 1
    overdue = [d for d in docs if d.review_date and d.review_date < today]
    due_soon = [d for d in docs if d.review_date and today <= d.review_date <= today + timedelta(days=30)]
    facts = db.scalars(
        select(ApprovedFact).where(ApprovedFact.organisation_id == ctx.org_id)
    ).all()
    claims = db.scalars(
        select(ApprovedClaim).where(ApprovedClaim.organisation_id == ctx.org_id)
    ).all()
    expiring = sorted(
        [c for c in claims if c.status == "approved" and c.expiry_date and c.expiry_date <= today + timedelta(days=45)],
        key=lambda c: c.expiry_date,
    )
    guidelines = db.scalars(
        select(BrandGuideline).where(BrandGuideline.organisation_id == ctx.org_id)
    ).all()
    members = db.scalar(
        select(func.count()).select_from(Membership).where(Membership.organisation_id == ctx.org_id)
    ) or 0
    return {
        "documents": {
            "total": len(docs),
            "by_status": doc_counts,
            "approved": doc_counts.get("approved", 0),
            "overdue_review": len(overdue),
            "due_soon": len(due_soon),
            "overdue_items": [
                {"id": d.id, "title": d.title, "review_date": d.review_date.isoformat()}
                for d in sorted(overdue, key=lambda d: d.review_date)[:8]
            ],
        },
        "facts": {
            "total": len(facts),
            "approved": len([f for f in facts if f.status == "approved"]),
            "retired": len([f for f in facts if f.status == "retired"]),
        },
        "claims": {
            "total": len(claims),
            "approved": len([c for c in claims if c.status == "approved"]),
            "prohibited": len([c for c in claims if c.status == "prohibited"]),
            "expiring_45_days": len(expiring),
            "expired": len([c for c in expiring if c.expiry_date < today]),
            "items": [
                {
                    "id": c.id, "claim_text": c.claim_text, "expiry_date": c.expiry_date.isoformat(),
                    "days_to_expiry": (c.expiry_date - today).days,
                }
                for c in expiring[:8]
            ],
        },
        "guidelines": {
            "total": len(guidelines),
            "approved": len([g for g in guidelines if g.status == "approved"]),
            "draft": len([g for g in guidelines if g.status == "draft"]),
        },
        "members": members,
    }
