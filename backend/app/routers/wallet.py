"""Read-only approved Knowledge Wallet and grounded Q&A.

This router exposes ONLY approved, authoritative knowledge to any authenticated
workspace member. It never exposes draft/unapproved private vault records to
content creators. All evidence comes from the same central repository/index
used by verification (approved documents, facts, claims, guidelines).
"""
from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_context
from app.db.session import get_db
from app.models import (
    ApprovedClaim, ApprovedFact, BrandAsset, BrandGuideline, KnowledgeDocument,
)
from app.routers.common import clamp_page, paginate
from app.services import ai
from app.services.knowledge_index import build_index, search
from app.services.serializers import (
    approved_claim_out, asset_out, fact_out, guideline_out,
)

router = APIRouter(prefix="/wallet", tags=["Knowledge wallet"])


def _doc_wallet_out(doc: KnowledgeDocument, include_text: bool = False) -> dict:
    # Read-only, approved-only view. Never expose internal owner/approval actor IDs
    # beyond what the existing serializer pattern already surfaces for admin views;
    # keep it minimal and safe.
    data = {
        "id": doc.id,
        "title": doc.title,
        "doc_type": doc.doc_type,
        "category": doc.category,
        "status": doc.status,
        "version": doc.version,
        "effective_date": doc.effective_date.isoformat() if doc.effective_date else None,
        "review_date": doc.review_date.isoformat() if doc.review_date else None,
        "file_name": doc.file_name,
        "mime_type": doc.mime_type,
        "tags": doc.tags or [],
        "char_count": len(doc.extracted_text or ""),
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "processing_status": "processed" if (doc.extracted_text or "").strip() else "uploaded",
    }
    if include_text:
        data["extracted_text"] = doc.extracted_text or ""
        data["page_map"] = doc.page_map or []
    return data


@router.get("/overview")
def wallet_overview(ctx: CurrentUser = Depends(get_context), db: Session = Depends(get_db)):
    org_id = ctx.org_id
    approved_docs = db.scalars(
        select(KnowledgeDocument).where(
            KnowledgeDocument.organisation_id == org_id,
            KnowledgeDocument.status == "approved",
        )
    ).all()
    approved_facts = db.scalars(
        select(ApprovedFact).where(
            ApprovedFact.organisation_id == org_id, ApprovedFact.status == "approved"
        )
    ).all()
    claims = db.scalars(
        select(ApprovedClaim).where(ApprovedClaim.organisation_id == org_id)
    ).all()
    guidelines = db.scalars(
        select(BrandGuideline).where(
            BrandGuideline.organisation_id == org_id, BrandGuideline.status == "approved"
        )
    ).all()
    assets = db.scalars(
        select(BrandAsset).where(
            BrandAsset.organisation_id == org_id, BrandAsset.is_approved.is_(True)
        )
    ).all()
    last_updates = [dt for dt in (
        max((d.updated_at for d in approved_docs), default=None),
        max((f.updated_at for f in approved_facts), default=None),
        max((c.updated_at for c in claims), default=None),
        max((g.updated_at for g in guidelines), default=None),
    ) if dt]
    return {
        "last_updated_at": max(last_updates).isoformat() if last_updates else None,
        "counts": {
            "approved_documents": len(approved_docs),
            "approved_facts": len(approved_facts),
            "approved_claims": len([c for c in claims if c.status == "approved"]),
            "prohibited_claims": len([c for c in claims if c.status == "prohibited"]),
            "approved_guidelines": len(guidelines),
            "approved_assets": len(assets),
        },
        "by_category": {
            "brand_identity": len([g for g in guidelines if g.category in {"messaging", "tone", "brand"}]),
            "brand_guidelines": len(guidelines),
            "visual_identity": len([a for a in assets if a.asset_type in {"logo", "colour", "font", "image"}]),
            "products_services": len([f for f in approved_facts if f.category in {"product", "pricing", "warranty"}]),
            "marketing_campaign": len([c for c in claims if c.status in {"approved", "prohibited"}]),
        },
    }


@router.get("/documents")
def wallet_documents(
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
    q: str | None = None,
    doc_type: str | None = None,
    category: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    page, page_size = clamp_page(page, page_size)
    filters = [
        KnowledgeDocument.organisation_id == ctx.org_id,
        KnowledgeDocument.status == "approved",
    ]
    if q:
        like = f"%{q.strip()}%"
        filters.append(or_(KnowledgeDocument.title.ilike(like), KnowledgeDocument.category.ilike(like)))
    if doc_type:
        filters.append(KnowledgeDocument.doc_type == doc_type)
    if category:
        filters.append(KnowledgeDocument.category == category)
    total = db.scalar(select(func.count()).select_from(KnowledgeDocument).where(*filters)) or 0
    docs = db.scalars(
        select(KnowledgeDocument).where(*filters).order_by(KnowledgeDocument.updated_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return paginate([_doc_wallet_out(d) for d in docs], total, page, page_size)


@router.get("/documents/{document_id}")
def wallet_document(
    document_id: str,
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
):
    doc = db.get(KnowledgeDocument, document_id)
    if not doc or doc.organisation_id != ctx.org_id or doc.status != "approved":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Approved document not found")
    return _doc_wallet_out(doc, include_text=True)


@router.get("/facts")
def wallet_facts(
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
    q: str | None = None,
    category: str | None = None,
    page: int = 1,
    page_size: int = 100,
):
    page, page_size = clamp_page(page, page_size)
    filters = [ApprovedFact.organisation_id == ctx.org_id, ApprovedFact.status == "approved"]
    if q:
        like = f"%{q.strip()}%"
        filters.append(or_(ApprovedFact.key.ilike(like), ApprovedFact.value.ilike(like), ApprovedFact.product.ilike(like)))
    if category:
        filters.append(ApprovedFact.category == category)
    total = db.scalar(select(func.count()).select_from(ApprovedFact).where(*filters)) or 0
    facts = db.scalars(
        select(ApprovedFact).where(*filters).order_by(ApprovedFact.updated_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return paginate([fact_out(f) for f in facts], total, page, page_size)


@router.get("/claims")
def wallet_claims(
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = 1,
    page_size: int = 100,
):
    page, page_size = clamp_page(page, page_size)
    # Creators need approved + prohibited guidance (restricted claims) as read-only info.
    filters = [ApprovedClaim.organisation_id == ctx.org_id]
    if status_filter:
        filters.append(ApprovedClaim.status == status_filter)
    else:
        filters.append(ApprovedClaim.status.in_(["approved", "prohibited"]))
    total = db.scalar(select(func.count()).select_from(ApprovedClaim).where(*filters)) or 0
    claims = db.scalars(
        select(ApprovedClaim).where(*filters).order_by(ApprovedClaim.status, ApprovedClaim.updated_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    today = date.today()
    items = []
    for c in claims:
        item = approved_claim_out(c)
        item["expired"] = bool(c.expiry_date and c.expiry_date < today)
        items.append(item)
    return paginate(items, total, page, page_size)


@router.get("/guidelines")
def wallet_guidelines(
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
    q: str | None = None,
    category: str | None = None,
):
    filters = [BrandGuideline.organisation_id == ctx.org_id, BrandGuideline.status == "approved"]
    if q:
        like = f"%{q.strip()}%"
        filters.append(or_(BrandGuideline.title.ilike(like), BrandGuideline.content.ilike(like), BrandGuideline.summary.ilike(like)))
    if category:
        filters.append(BrandGuideline.category == category)
    guidelines = db.scalars(select(BrandGuideline).where(*filters).order_by(BrandGuideline.category, BrandGuideline.title)).all()
    return {"items": [guideline_out(g) for g in guidelines], "total": len(guidelines)}


@router.get("/assets")
def wallet_assets(
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
    asset_type: str | None = None,
):
    filters = [BrandAsset.organisation_id == ctx.org_id, BrandAsset.is_approved.is_(True)]
    if asset_type:
        filters.append(BrandAsset.asset_type == asset_type)
    assets = db.scalars(select(BrandAsset).where(*filters).order_by(BrandAsset.asset_type, BrandAsset.name)).all()
    return {"items": [asset_out(a) for a in assets], "total": len(assets)}


@router.get("/search")
def wallet_search(
    q: str = Query(min_length=2),
    limit: int = Query(default=8, ge=1, le=20),
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
):
    index = build_index(db, ctx.org_id)  # approved-only index
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
                "review_date": r.get("review_date").isoformat() if r.get("review_date") else None,
            }
            for r in results
        ],
        "sources_indexed": len(index),
    }


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    top_k: int = Field(default=6, ge=1, le=12)


@router.post("/ask")
def wallet_ask(payload: AskRequest, ctx: CurrentUser = Depends(get_context), db: Session = Depends(get_db)):
    question = payload.question.strip()
    index = build_index(db, ctx.org_id)
    hits = search(index, question, top_k=payload.top_k)
    sources = []
    for h in hits:
        sources.append({
            "title": h.get("document_title") or "Approved knowledge",
            "kind": h.get("kind"),
            "locator": h.get("locator") or "",
            "document_id": h.get("document_id"),
            "text": (h.get("text") or "")[:1200],
            "stale": bool(h.get("stale")),
        })

    not_found = (
        "This information is not available in the approved knowledge base. "
        "Ask an administrator to add and approve the relevant source before relying on it."
    )

    if not sources or all((s.get("score") if False else 0) == 0 for s in sources):
        # search() only returns score>0; empty means no match
        if not sources:
            return {
                "question": question,
                "answer": not_found,
                "sources": [],
                "grounded": True,
                "mode": "deterministic",
                "ai_error": None,
            }

    ai_status = ai.status()
    evidence_block = "\n\n".join(
        f"[{i+1}] {s['title']} ({s.get('locator') or s.get('kind') or 'source'})\n{s['text']}"
        for i, s in enumerate(sources)
    )

    if ai_status.get("configured"):
        try:
            data = ai.chat_json(
                "You are BrandProof's Knowledge Assistant. Answer ONLY using the provided approved evidence excerpts. "
                "Never invent brand rules, fonts, specifications, statistics, or claims. "
                "For every factual point, cite sources by their bracket number like [1]. "
                "If the evidence does not contain the answer, say clearly that the information is not available in the approved knowledge base. "
                "Return JSON with keys: answer (string), missing_information (boolean), cited_source_indexes (array of integers).",
                f"Question: {question}\n\nApproved evidence excerpts:\n{evidence_block}",
            )
            answer = str(data.get("answer") or "").strip() or not_found
            cited = data.get("cited_source_indexes") or []
            cited_sources = []
            if isinstance(cited, list):
                for idx in cited:
                    if isinstance(idx, int) and 1 <= idx <= len(sources):
                        cited_sources.append(sources[idx - 1])
            if not cited_sources:
                cited_sources = sources[:3]
            return {
                "question": question,
                "answer": answer,
                "sources": cited_sources,
                "grounded": True,
                "mode": "ai",
                "ai_error": None,
            }
        except Exception as exc:  # noqa: BLE001
            # Fall through to deterministic, grounded response
            ai_error = f"{type(exc).__name__}: {exc}"
    else:
        ai_error = None

    # Deterministic, extractive grounded answer (no invention)
    lines = [f"Based on approved knowledge sources (no external AI configured):"]
    for i, s in enumerate(sources[:4], start=1):
        loc = f" — {s['locator']}" if s.get("locator") else ""
        lines.append(f"{i}. {s['title']}{loc}: {s['text'][:320].strip()}")
    lines.append("")
    if not sources:
        lines = [not_found]
    else:
        lines.append("If this does not fully answer your question, the specific detail may not be present in the approved knowledge base.")
    return {
        "question": question,
        "answer": "\n".join(lines) if sources else not_found,
        "sources": sources[:4],
        "grounded": True,
        "mode": "deterministic",
        "ai_error": ai_error if 'ai_error' in locals() else None,
    }
