from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_context, require
from app.db.session import get_db
from app.models import (
    ContentSubmission, ExtractedClaim, ReviewFinding, ReviewerFeedback, User,
)
from app.routers.common import clamp_page, paginate
from app.schemas import FindingDecision
from app.services.audit import notify, record_audit
from app.services.serializers import (
    feedback_out, finding_out, submission_out, user_brief,
)

router = APIRouter(prefix="/review", tags=["Review"])

OPEN_STATUSES = ["open", "accepted", "modified"]


def _finding_or_404(db: Session, org_id: str, finding_id: str) -> ReviewFinding:
    finding = db.get(ReviewFinding, finding_id)
    if not finding or finding.organisation_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Finding not found")
    return finding


@router.get("/queue")
def review_queue(
    ctx: CurrentUser = Depends(require("review_content")),
    db: Session = Depends(get_db),
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
):
    page, page_size = clamp_page(page, page_size)
    filters = [
        ContentSubmission.organisation_id == ctx.org_id,
        ContentSubmission.status.in_(["submitted", "under_review"]),
    ]
    if q:
        like = f"%{q.strip()}%"
        filters.append(or_(
            ContentSubmission.title.ilike(like),
            ContentSubmission.campaign.ilike(like),
            ContentSubmission.product.ilike(like),
        ))
    total = db.scalar(select(func.count()).select_from(ContentSubmission).where(*filters)) or 0
    submissions = db.scalars(
        select(ContentSubmission).where(*filters)
        .order_by(ContentSubmission.created_at.asc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()

    ids = [s.id for s in submissions]
    findings = db.scalars(
        select(ReviewFinding).where(ReviewFinding.submission_id.in_(ids or [""]))
    ).all()
    claims = db.scalars(
        select(ExtractedClaim).where(ExtractedClaim.submission_id.in_(ids or [""]))
    ).all()

    items = []
    for submission in submissions:
        own = [f for f in findings if f.submission_id == submission.id]
        own_claims = [c for c in claims if c.submission_id == submission.id]
        item = submission_out(submission)
        item.update({
            "open_findings": len([f for f in own if f.status in OPEN_STATUSES]),
            "critical_findings": len([f for f in own if f.severity in {"high", "critical"} and f.status in OPEN_STATUSES]),
            "claims_supported": len([c for c in own_claims if c.status == "supported"]),
            "claims_flagged": len([c for c in own_claims if c.status != "supported"]),
            "age_hours": round((datetime.utcnow() - submission.created_at).total_seconds() / 3600, 1),
        })
        items.append(item)
    return paginate(items, total, page, page_size)


@router.get("/findings")
def list_findings(
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
    q: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    severity: str | None = None,
    category: str | None = None,
    submission_id: str | None = None,
    detector: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    page, page_size = clamp_page(page, page_size)
    filters = [ReviewFinding.organisation_id == ctx.org_id]
    if ctx.role == "content_creator":
        own = db.execute(
            select(ContentSubmission.id).where(
                ContentSubmission.organisation_id == ctx.org_id,
                ContentSubmission.submitted_by == ctx.user.id,
            )
        ).scalars().all()
        filters.append(ReviewFinding.submission_id.in_(own or [""]))
    if q:
        like = f"%{q.strip()}%"
        filters.append(or_(
            ReviewFinding.title.ilike(like),
            ReviewFinding.original_text.ilike(like),
            ReviewFinding.explanation.ilike(like),
        ))
    if status_filter:
        filters.append(ReviewFinding.status == status_filter)
    if severity:
        filters.append(ReviewFinding.severity == severity)
    if category:
        filters.append(ReviewFinding.category == category)
    if submission_id:
        filters.append(ReviewFinding.submission_id == submission_id)
    if detector:
        filters.append(ReviewFinding.detector == detector)

    total = db.scalar(select(func.count()).select_from(ReviewFinding).where(*filters)) or 0
    findings = db.scalars(
        select(ReviewFinding).where(*filters).order_by(ReviewFinding.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    submissions = {
        s.id: s for s in db.scalars(
            select(ContentSubmission).where(ContentSubmission.id.in_([f.submission_id for f in findings] or [""]))
        ).all()
    }
    items = []
    for finding in findings:
        item = finding_out(finding)
        submission = submissions.get(finding.submission_id)
        item["submission_title"] = submission.title if submission else ""
        item["content_type"] = submission.content_type if submission else ""
        items.append(item)
    return paginate(items, total, page, page_size)


@router.get("/findings/{finding_id}")
def get_finding(
    finding_id: str,
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
):
    finding = _finding_or_404(db, ctx.org_id, finding_id)
    if ctx.role == "content_creator":
        _sub = db.get(ContentSubmission, finding.submission_id)
        if not _sub or _sub.submitted_by != ctx.user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Finding not found")
    submission = db.get(ContentSubmission, finding.submission_id)
    claim = db.get(ExtractedClaim, finding.claim_id) if finding.claim_id else None
    feedback = db.scalars(
        select(ReviewerFeedback).where(ReviewerFeedback.finding_id == finding.id)
        .order_by(ReviewerFeedback.created_at.desc())
    ).all()
    data = finding_out(finding)
    data["submission"] = submission_out(submission, include_text=True) if submission else None
    data["claim"] = {
        "id": claim.id, "claim_text": claim.claim_text, "status": claim.status,
        "explanation": claim.explanation, "evidence_source_label": claim.evidence_source_label,
        "evidence_passage": claim.evidence_passage, "evidence_locator": claim.evidence_locator,
        "confidence": claim.confidence,
    } if claim else None
    data["feedback"] = [feedback_out(f) for f in feedback]
    return data


@router.post("/findings/{finding_id}/decide")
def decide_finding(
    finding_id: str,
    payload: FindingDecision,
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
):
    finding = _finding_or_404(db, ctx.org_id, finding_id)
    if ctx.role == "content_creator":
        submission = db.get(ContentSubmission, finding.submission_id)
        if not submission or submission.submitted_by != ctx.user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Finding not found")
    elif not ctx.can("review_content"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Your role ({ctx.role}) cannot perform this action.",
        )
    if finding.status == "resolved":
        raise HTTPException(status.HTTP_409_CONFLICT, "This finding has already been resolved.")
    if payload.decision == "modified" and not (payload.final_correction or "").strip():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Provide the final correction when modifying a suggestion.",
        )

    previous = finding.status
    finding.status = payload.decision
    finding.resolved_by = ctx.user.id
    finding.resolved_at = datetime.utcnow()
    final_correction = (
        payload.final_correction.strip() if payload.decision == "modified"
        else ("" if payload.decision == "rejected" else finding.suggested_correction)
    )

    feedback = ReviewerFeedback(
        organisation_id=ctx.org_id,
        finding_id=finding.id,
        submission_id=finding.submission_id,
        reviewer_id=ctx.user.id,
        original_content=finding.original_text,
        issue_category=finding.category,
        issue_title=finding.title,
        original_suggestion=finding.suggested_correction,
        final_correction=final_correction,
        decision=payload.decision,
        feedback_reason=payload.reason,
        guideline_id=finding.guideline_id,
    )
    db.add(feedback)

    submission = db.get(ContentSubmission, finding.submission_id)
    record_audit(
        db, ctx.org_id, ctx.user.id, "review.finding_decided", "finding", finding.id,
        finding.title, previous_value=previous, updated_value=payload.decision,
        decision=payload.decision, content_version=submission.current_version if submission else None,
        meta={
            "category": finding.category, "severity": finding.severity,
            "reason": payload.reason[:400],
            "final_correction": final_correction[:400],
        },
    )
    if submission and submission.submitted_by and submission.submitted_by != ctx.user.id:
        notify(
            db, ctx.org_id,
            title=f"Reviewer {payload.decision} a suggestion",
            message=f"\"{finding.title}\" in \"{submission.title}\" was {payload.decision} by {ctx.user.full_name}.",
            type="review", link=f"/content/{submission.id}", user_id=submission.submitted_by,
        )
    db.commit()
    db.refresh(finding)
    db.refresh(feedback)
    return {
        "finding": finding_out(finding),
        "feedback": feedback_out(feedback),
        "message": "Feedback stored. It will inform guideline intelligence analysis.",
    }


@router.get("/feedback")
def list_feedback(
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
    decision: str | None = None,
    category: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    page, page_size = clamp_page(page, page_size)
    filters = [ReviewerFeedback.organisation_id == ctx.org_id]
    if decision:
        filters.append(ReviewerFeedback.decision == decision)
    if category:
        filters.append(ReviewerFeedback.issue_category == category)
    total = db.scalar(select(func.count()).select_from(ReviewerFeedback).where(*filters)) or 0
    rows = db.scalars(
        select(ReviewerFeedback).where(*filters).order_by(ReviewerFeedback.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return paginate([feedback_out(f) for f in rows], total, page, page_size)


@router.get("/stats")
def review_stats(ctx: CurrentUser = Depends(get_context), db: Session = Depends(get_db)):
    findings = db.scalars(
        select(ReviewFinding).where(ReviewFinding.organisation_id == ctx.org_id)
    ).all()
    feedback = db.scalars(
        select(ReviewerFeedback).where(ReviewerFeedback.organisation_id == ctx.org_id)
    ).all()
    submissions = db.scalars(
        select(ContentSubmission).where(ContentSubmission.organisation_id == ctx.org_id)
    ).all()
    week_ago = datetime.utcnow() - timedelta(days=7)

    by_severity: dict[str, int] = {}
    by_category: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for finding in findings:
        if finding.status in OPEN_STATUSES:
            by_severity[finding.severity] = by_severity.get(finding.severity, 0) + 1
            by_category[finding.category] = by_category.get(finding.category, 0) + 1
        by_status[finding.status] = by_status.get(finding.status, 0) + 1

    return {
        "findings_total": len(findings),
        "findings_open": len([f for f in findings if f.status in OPEN_STATUSES]),
        "findings_resolved": len([f for f in findings if f.status == "resolved"]),
        "by_severity": by_severity,
        "by_category": by_category,
        "by_status": by_status,
        "feedback_total": len(feedback),
        "decisions_last_7_days": len([f for f in feedback if f.created_at and f.created_at >= week_ago]),
        "queue": {
            "submitted": len([s for s in submissions if s.status == "submitted"]),
            "under_review": len([s for s in submissions if s.status == "under_review"]),
            "changes_requested": len([s for s in submissions if s.status == "changes_requested"]),
        },
        "contributors": len({f.reviewer_id for f in feedback if f.reviewer_id}),
    }


@router.get("/reviewers")
def reviewer_activity(ctx: CurrentUser = Depends(get_context), db: Session = Depends(get_db)):
    rows = db.execute(
        select(ReviewerFeedback.reviewer_id, func.count(ReviewerFeedback.id))
        .where(ReviewerFeedback.organisation_id == ctx.org_id)
        .group_by(ReviewerFeedback.reviewer_id)
    ).all()
    users = {
        u.id: user_brief(u) for u in db.scalars(
            select(User).where(User.id.in_([r[0] for r in rows if r[0]] or [""]))
        ).all()
    }
    return {
        "items": [
            {"reviewer": users.get(reviewer_id), "decisions": count}
            for reviewer_id, count in sorted(rows, key=lambda r: r[1], reverse=True)
        ]
    }
