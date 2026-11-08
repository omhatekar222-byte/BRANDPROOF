"""Builds a searchable evidence index from APPROVED company knowledge only.

Every chunk carries the database id of its source record, so citations shown to
users can always be traced back to a real, approved record. Chunks never
contain generated text — only verbatim excerpts.
"""
import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ApprovedClaim, ApprovedFact, BrandGuideline, KnowledgeDocument
from app.services.embeddings import cosine, embed

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _chunk(text: str, max_chars: int = 420) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n|\n(?=[A-Z][A-Za-z ]{2,40}:)", text) if p.strip()]
    chunks: list[str] = []
    for para in paragraphs:
        if len(para) <= max_chars:
            chunks.append(para)
            continue
        sentences = SENTENCE_SPLIT_RE.split(para)
        current = ""
        for sentence in sentences:
            if len(current) + len(sentence) + 1 > max_chars and current:
                chunks.append(current.strip())
                current = sentence
            else:
                current = f"{current} {sentence}".strip()
        if current:
            chunks.append(current.strip())
    return chunks or ([text.strip()] if text.strip() else [])


def _is_stale(review_date) -> bool:
    return bool(review_date and review_date < date.today())


def build_index(db: Session, org_id: str) -> list[dict]:
    sources: list[dict] = []

    documents = db.scalars(
        select(KnowledgeDocument).where(
            KnowledgeDocument.organisation_id == org_id,
            KnowledgeDocument.status == "approved",
        )
    ).all()
    for doc in documents:
        page_map = doc.page_map or []
        if page_map:
            for page in page_map:
                for i, chunk in enumerate(_chunk(page.get("text", ""))):
                    sources.append({
                        "kind": "document_chunk",
                        "document_id": doc.id,
                        "document_title": doc.title,
                        "doc_type": doc.doc_type,
                        "locator": f"Page {page.get('page')}" + (f", part {i + 1}" if i else ""),
                        "text": chunk,
                        "status": doc.status,
                        "stale": _is_stale(doc.review_date),
                        "effective_date": doc.effective_date,
                        "review_date": doc.review_date,
                    })
        else:
            for i, chunk in enumerate(_chunk(doc.extracted_text or "")):
                sources.append({
                    "kind": "document_chunk",
                    "document_id": doc.id,
                    "document_title": doc.title,
                    "doc_type": doc.doc_type,
                    "locator": f"Section {i + 1}",
                    "text": chunk,
                    "status": doc.status,
                    "stale": _is_stale(doc.review_date),
                    "effective_date": doc.effective_date,
                    "review_date": doc.review_date,
                })

    facts = db.scalars(
        select(ApprovedFact).where(
            ApprovedFact.organisation_id == org_id, ApprovedFact.status == "approved"
        )
    ).all()
    for fact in facts:
        label = fact.document.title if fact.document else "Approved fact record"
        locator = fact.source_locator or ("Approved fact record" if not fact.document else "")
        sources.append({
            "kind": "fact",
            "document_id": fact.document_id,
            "document_title": label,
            "fact_id": fact.id,
            "locator": locator,
            "text": f"{fact.key}: {fact.value}",
            "status": fact.status,
            "stale": _is_stale(fact.review_date),
            "effective_date": fact.effective_date,
            "review_date": fact.review_date,
            "fact_key": fact.key,
            "fact_value": fact.value,
            "product": fact.product,
        })

    claims = db.scalars(
        select(ApprovedClaim).where(
            ApprovedClaim.organisation_id == org_id, ApprovedClaim.status == "approved"
        )
    ).all()
    for claim in claims:
        sources.append({
            "kind": "approved_claim",
            "document_id": claim.evidence_document_id,
            "document_title": "Approved marketing claim",
            "claim_id": claim.id,
            "locator": "Approved claim register",
            "text": claim.claim_text,
            "status": "approved",
            "stale": _is_stale(claim.review_date) or bool(claim.expiry_date and claim.expiry_date < date.today()),
            "effective_date": None,
            "review_date": claim.review_date,
        })

    guidelines = db.scalars(
        select(BrandGuideline).where(
            BrandGuideline.organisation_id == org_id, BrandGuideline.status == "approved"
        )
    ).all()
    for guideline in guidelines:
        for i, chunk in enumerate(_chunk(guideline.content)):
            sources.append({
                "kind": "guideline",
                "document_id": None,
                "document_title": guideline.title,
                "guideline_id": guideline.id,
                "locator": f"Guideline v{guideline.version}, clause {i + 1}",
                "text": chunk,
                "status": guideline.status,
                "stale": _is_stale(guideline.review_date),
                "effective_date": guideline.effective_date,
                "review_date": guideline.review_date,
            })

    for source in sources:
        source["embedding"] = embed(source["text"])
    return sources


def search(index: list[dict], query: str, top_k: int = 5, kinds: tuple[str, ...] | None = None) -> list[dict]:
    q = embed(query)
    scored = []
    for source in index:
        if kinds and source["kind"] not in kinds:
            continue
        score = cosine(q, source["embedding"])
        if score > 0:
            item = dict(source)
            item["score"] = round(score, 4)
            item.pop("embedding", None)
            scored.append(item)
    scored.sort(key=lambda s: s["score"], reverse=True)
    return scored[:top_k]
