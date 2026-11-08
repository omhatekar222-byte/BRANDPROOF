from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_context
from app.db.session import get_db
from app.models import ChangeImpact, ContentSubmission
from app.routers.common import clamp_page, paginate
from app.schemas import ImpactAnalyzeRequest, ImpactResolve
from app.services.audit import record_audit
from app.services.impact import create_impacts
from app.services.serializers import impact_out

router = APIRouter(prefix="/impact", tags=["Change impact"])


def _impact_or_404(db: Session, org_id: str, impact_id: str) -> ChangeImpact:
    impact = db.get(ChangeImpact, impact_id)
    if not impact or impact.organisation_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Impact record not found")
    return impact


def _submit_out(db: Session, submission: ContentSubmission | None):
    if not submission:
        return None
    return {
        "id": submission.id, "title": submission.title, "status": submission.status,
        "content_type": submission.content_type, "campaign": submission.campaign,
        "created_at": submission.created_at.isoformat() if submission.created_at else None,
        "excerpt": (submission.raw_text or "")[:280],
    }


@router.get("")
def list_impacts(
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = None,
    page: int = 1, page_size: int = 50,
):
    page, page_size = clamp_page(page, page_size)
    filters = [ChangeImpact.organisation_id == ctx.org_id]
    if status_filter:
        filters.append(ChangeImpact.status == status_filter)
    if q:
        like = f"%{q.strip()}%"
        filters.append(ChangeImpact.entity_label.ilike(like))
    total = db.scalar(select(func.count()).select_from(ChangeImpact).where(*filters)) or 0
    rows = db.scalars(
        select(ChangeImpact).where(*filters).order_by(ChangeImpact.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    submissions = {
        s.id: s for s in db.scalars(
            select(ContentSubmission).where(
                ContentSubmission.id.in_([r.affected_submission_id for r in rows if r.affected_submission_id] or [""])
            )
        ).all()
    }
    items = []
    for row in rows:
        item = impact_out(row)
        item["submission"] = _submit_out(db, submissions.get(row.affected_submission_id))
        items.append(item)
    return paginate(items, total, page, page_size)


@router.get("/summary")
def impact_summary(ctx: CurrentUser = Depends(get_context), db: Session = Depends(get_db)):
    rows = db.scalars(select(ChangeImpact).where(ChangeImpact.organisation_id == ctx.org_id)).all()
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    affected_ids = {r.affected_submission_id for r in rows if r.affected_submission_id and r.status != "resolved"}
    return {
        "total": len(rows),
        "by_status": by_status,
        "open": by_status.get("open", 0),
        "recheck_requested": by_status.get("recheck_requested", 0),
        "resolved": by_status.get("resolved", 0),
        "affected_content": len(affected_ids),
        "note": "Only content registered in this workspace is searched.",
    }


@router.post("/analyze")
def analyze_change(
    payload: ImpactAnalyzeRequest,
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
):
    label = payload.label or "Approved fact"
    impacts = create_impacts(
        db, ctx.org_id, payload.fact_id, payload.previous_value, payload.updated_value, label, ctx.user.id,
    )
    record_audit(
        db, ctx.org_id, ctx.user.id, "impact.analyzed", "change_impact", "",
        label, previous_value=payload.previous_value, updated_value=payload.updated_value,
        meta={"affected": len(impacts)},
    )
    db.commit()
    submissions = {
        s.id: s for s in db.scalars(
            select(ContentSubmission).where(
                ContentSubmission.id.in_([i.affected_submission_id for i in impacts if i.affected_submission_id] or [""])
            )
        ).all()
    }
    return {
        "affected_total": len(impacts),
        "impacts": [impact_out(i) | {"submission": _submit_out(db, submissions.get(i.affected_submission_id))} for i in impacts],
        "note": "Only content registered in this workspace is searched. Nothing is changed automatically.",
    }


@router.get("/{impact_id}")
def get_impact(
    impact_id: str,
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
):
    impact = _impact_or_404(db, ctx.org_id, impact_id)
    submission = db.get(ContentSubmission, impact.affected_submission_id) if impact.affected_submission_id else None
    data = impact_out(impact)
    data["submission"] = _submit_out(db, submission)
    history = db.scalars(
        select(ChangeImpact).where(
            ChangeImpact.organisation_id == ctx.org_id,
            ChangeImpact.entity_label == impact.entity_label,
        ).order_by(ChangeImpact.created_at)
    ).all()
    data["history"] = [impact_out(h) for h in history]
    return data


@router.post("/{impact_id}/resolve")
def resolve_impact(
    impact_id: str,
    payload: ImpactResolve,
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
):
    impact = _impact_or_404(db, ctx.org_id, impact_id)
    previous = impact.status
    if payload.action == "recheck":
        impact.status = "recheck_requested"
        updated = "recheck requested"
    elif payload.action == "new_review":
        impact.status = "recheck_requested"
        submission = db.get(ContentSubmission, impact.affected_submission_id) if impact.affected_submission_id else None
        if submission and submission.status not in {"approved"}:
            submission.status = "under_review"
        updated = "new review started"
    else:
        impact.status = "resolved"
        impact.resolved_by = ctx.user.id
        from datetime import datetime
        impact.resolved_at = datetime.utcnow()
        updated = "resolved"
    record_audit(
        db, ctx.org_id, ctx.user.id, "impact.resolved", "change_impact", impact.id,
        impact.entity_label, previous_value=previous, updated_value=updated,
        meta={"notes": payload.notes, "action": payload.action},
    )
    db.commit()
    db.refresh(impact)
    submission = db.get(ContentSubmission, impact.affected_submission_id) if impact.affected_submission_id else None
    return impact_out(impact) | {"submission": _submit_out(db, submission), "message": updated}
