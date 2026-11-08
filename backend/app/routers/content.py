from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_context, require
from app.db.session import get_db
from app.models import (
    ApprovalRecord, ApprovedFact, Comment, ContentFactUsage, ContentSubmission, ContentVersion,
    ExtractedClaim, ReviewFinding,
)
from app.routers.common import clamp_page, paginate, save_upload
from app.schemas import (
    AnalysisRequest, ApplyCorrectionsRequest, ApprovalDecision, CommentCreate, StatusTransition,
    SubmissionCreate, SubmissionUpdate,
)
from app.services.analysis import run_analysis
from app.services.audit import notify, record_audit
from app.services.extract import ExtractionError, extract_text as extract_document_text
from app.services.serializers import (
    approval_out, comment_out, extracted_claim_out, finding_out, submission_out,
)

router = APIRouter(prefix="/content", tags=["Content"])

TRANSITIONS = {
    "draft": {"submitted"},
    "submitted": {"under_review", "draft", "changes_requested", "rejected", "approved", "cleared_by_policy"},
    "under_review": {"changes_requested", "approved", "rejected", "cleared_by_policy"},
    "changes_requested": {"submitted", "draft"},
    "approved": {"draft"},
    "rejected": {"draft"},
    "cleared_by_policy": {"draft", "submitted", "under_review"},
}

STATUS_PERMISSION = {
    "draft": "upload_content",
    "submitted": "upload_content",
    "under_review": "review_content",
    "changes_requested": "review_content",
    "approved": "approve_content",
    "rejected": "approve_content",
    "cleared_by_policy": "review_content",
}

DECISION_STATUS = {"approved": "approved", "rejected": "rejected", "changes_requested": "changes_requested"}


def _submission_or_404(db: Session, org_id: str, submission_id: str, ctx: CurrentUser | None = None) -> ContentSubmission:
    submission = db.get(ContentSubmission, submission_id)
    if not submission or submission.organisation_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content submission not found")
    # Creators only ever see their own submissions.
    if ctx is not None and ctx.role == "content_creator" and submission.submitted_by != ctx.user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content submission not found")
    return submission


def _add_version(db: Session, submission: ContentSubmission, note: str, actor_id: str) -> ContentVersion:
    version = ContentVersion(
        submission_id=submission.id,
        version=submission.current_version,
        text=submission.raw_text,
        note=note[:300],
        created_by=actor_id,
    )
    db.add(version)
    return version


def _record_approval(
    db: Session, ctx: CurrentUser, submission: ContentSubmission, decision: str,
    previous: str, notes: str,
) -> ApprovalRecord:
    new_status = DECISION_STATUS[decision]
    record = ApprovalRecord(
        organisation_id=ctx.org_id,
        entity_type="content",
        entity_id=submission.id,
        decision=decision,
        notes=notes,
        previous_status=previous,
        new_status=new_status,
        actor_id=ctx.user.id,
    )
    db.add(record)
    return record


def _notify_owner(db: Session, ctx: CurrentUser, submission: ContentSubmission, title: str, message: str, type_: str) -> None:
    if submission.submitted_by and submission.submitted_by != ctx.user.id:
        notify(
            db, ctx.org_id, title=title, message=message, type=type_,
            link=f"/content/{submission.id}", user_id=submission.submitted_by,
        )


# --------------------------------------------------------------------------- listing


@router.get("/submissions")
def list_submissions(
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
    q: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    content_type: str | None = None,
    campaign: str | None = None,
    mine: bool = False,
    page: int = 1,
    page_size: int = 20,
):
    page, page_size = clamp_page(page, page_size)
    if ctx.role == "content_creator":
        mine = True
    filters = [ContentSubmission.organisation_id == ctx.org_id]
    if q:
        like = f"%{q.strip()}%"
        filters.append(or_(
            ContentSubmission.title.ilike(like),
            ContentSubmission.raw_text.ilike(like),
            ContentSubmission.campaign.ilike(like),
            ContentSubmission.product.ilike(like),
        ))
    if status_filter:
        filters.append(ContentSubmission.status == status_filter)
    if content_type:
        filters.append(ContentSubmission.content_type == content_type)
    if campaign:
        filters.append(ContentSubmission.campaign == campaign)
    if mine:
        filters.append(ContentSubmission.submitted_by == ctx.user.id)

    total = db.scalar(select(func.count()).select_from(ContentSubmission).where(*filters)) or 0
    submissions = db.scalars(
        select(ContentSubmission).where(*filters)
        .order_by(ContentSubmission.updated_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()

    open_counts = dict(
        db.execute(
            select(ReviewFinding.submission_id, func.count(ReviewFinding.id))
            .where(
                ReviewFinding.organisation_id == ctx.org_id,
                ReviewFinding.status.in_(["open", "accepted", "modified"]),
                ReviewFinding.submission_id.in_([s.id for s in submissions] or [""]),
            )
            .group_by(ReviewFinding.submission_id)
        ).all()
    )
    items = []
    for submission in submissions:
        item = submission_out(submission)
        item["open_findings"] = open_counts.get(submission.id, 0)
        items.append(item)
    return paginate(items, total, page, page_size)


@router.get("/campaigns")
def list_campaigns(ctx: CurrentUser = Depends(get_context), db: Session = Depends(get_db)):
    rows = db.execute(
        select(ContentSubmission.campaign, func.count(ContentSubmission.id))
        .where(ContentSubmission.organisation_id == ctx.org_id, ContentSubmission.campaign != "")
        .group_by(ContentSubmission.campaign)
        .order_by(func.count(ContentSubmission.id).desc())
    ).all()
    products = db.scalars(
        select(ContentSubmission.product)
        .where(ContentSubmission.organisation_id == ctx.org_id, ContentSubmission.product != "")
        .distinct()
    ).all()
    return {
        "campaigns": [{"name": name, "count": count} for name, count in rows],
        "products": sorted(products),
    }


# --------------------------------------------------------------------------- create


@router.post("/submissions", status_code=201)
def create_submission(
    payload: SubmissionCreate,
    ctx: CurrentUser = Depends(require("upload_content")),
    db: Session = Depends(get_db),
):
    submission = ContentSubmission(
        organisation_id=ctx.org_id,
        title=payload.title,
        content_type=payload.content_type,
        campaign=payload.campaign,
        product=payload.product,
        source_type="text",
        raw_text=payload.text,
        status="submitted" if payload.submit_now else "draft",
        submitted_by=ctx.user.id,
        current_version=1,
    )
    db.add(submission)
    db.flush()
    _add_version(db, submission, "Initial submission", ctx.user.id)
    record_audit(
        db, ctx.org_id, ctx.user.id, "content.created", "content", submission.id, submission.title,
        updated_value=f"{submission.content_type} · {submission.status}",
        content_version=submission.current_version,
    )
    if submission.status == "submitted":
        notify(
            db, ctx.org_id,
            title="New content submitted for review",
            message=f"\"{submission.title}\" was submitted by {ctx.user.full_name}.",
            type="review", link=f"/content/{submission.id}",
        )
    db.commit()
    db.refresh(submission)

    analysis = None
    if payload.analyze_now:
        analysis = run_analysis(db, submission, ctx.user.id)
        db.refresh(submission)
    return submission_out(submission, include_text=True) | {"analysis": analysis}


@router.post("/submissions/upload", status_code=201)
def upload_submission(
    file: UploadFile = File(...),
    title: str = Form(...),
    content_type: str = Form("document"),
    campaign: str = Form(""),
    product: str = Form(""),
    submit_now: bool = Form(True),
    analyze_now: bool = Form(True),
    ctx: CurrentUser = Depends(require("upload_content")),
    db: Session = Depends(get_db),
):
    data = file.file.read()
    suffix = Path(file.filename or "").suffix.lower()
    try:
        text = extract_document_text(file.filename or "", data)
    except ExtractionError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    if len(text.strip()) < 10:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "No usable text was found in this file.")

    stored_name, stored_path = save_upload(file, data, prefix="content")
    submission = ContentSubmission(
        organisation_id=ctx.org_id,
        title=title.strip(),
        content_type=content_type,
        campaign=campaign,
        product=product,
        source_type=(
            "pdf" if suffix == ".pdf"
            else "image" if suffix in {".png", ".jpg", ".jpeg", ".webp"}
            else "document" if suffix == ".docx"
            else "text"
        ),
        raw_text=text.strip(),
        file_name=file.filename or stored_name,
        file_path=stored_path,
        status="submitted" if submit_now else "draft",
        submitted_by=ctx.user.id,
        current_version=1,
    )
    db.add(submission)
    db.flush()
    _add_version(db, submission, f"Uploaded {file.filename or stored_name}", ctx.user.id)
    record_audit(
        db, ctx.org_id, ctx.user.id, "content.uploaded", "content", submission.id, submission.title,
        updated_value=file.filename or stored_name, content_version=submission.current_version,
        meta={"chars": len(text), "source": submission.source_type},
    )
    db.commit()
    db.refresh(submission)

    analysis = run_analysis(db, submission, ctx.user.id) if analyze_now else None
    db.refresh(submission)
    return submission_out(submission, include_text=True) | {"analysis": analysis}


# --------------------------------------------------------------------------- detail


@router.get("/submissions/{submission_id}")
def get_submission(
    submission_id: str,
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
):
    submission = _submission_or_404(db, ctx.org_id, submission_id, ctx)
    versions = db.scalars(
        select(ContentVersion).where(ContentVersion.submission_id == submission.id)
        .order_by(ContentVersion.version.desc(), ContentVersion.created_at.desc())
    ).all()
    claims = db.scalars(
        select(ExtractedClaim).where(ExtractedClaim.submission_id == submission.id)
        .order_by(ExtractedClaim.created_at)
    ).all()
    findings = db.scalars(
        select(ReviewFinding).where(ReviewFinding.submission_id == submission.id)
        .order_by(ReviewFinding.created_at)
    ).all()
    comments = db.scalars(
        select(Comment).where(Comment.submission_id == submission.id).order_by(Comment.created_at)
    ).all()
    approvals = db.scalars(
        select(ApprovalRecord).where(
            ApprovalRecord.entity_type == "content", ApprovalRecord.entity_id == submission.id
        ).order_by(ApprovalRecord.created_at.desc())
    ).all()

    usage_rows = db.execute(
        select(ContentFactUsage, ApprovedFact)
        .join(ApprovedFact, ApprovedFact.id == ContentFactUsage.fact_id)
        .where(ContentFactUsage.submission_id == submission.id)
    ).all()

    data = submission_out(submission, include_text=True)
    data["versions"] = [
        {
            "id": v.id,
            "version": v.version,
            "note": v.note,
            "created_by": v.created_by,
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "char_count": len(v.text or ""),
        }
        for v in versions
    ]
    data["claims"] = [extracted_claim_out(c) for c in claims]
    data["findings"] = [finding_out(f) for f in findings]
    data["comments"] = [comment_out(c) for c in comments]
    data["approvals"] = [approval_out(a) for a in approvals]
    data["fact_usage"] = [
        {
            "fact_id": fact.id, "key": fact.key, "value": fact.value,
            "product": fact.product, "status": fact.status,
            "matched_text": usage.matched_text,
        }
        for usage, fact in usage_rows
    ]
    data["counts"] = {
        "claims": len(claims),
        "supported": len([c for c in claims if c.status == "supported"]),
        "contradicted": len([c for c in claims if c.status == "contradicted"]),
        "unsupported": len([c for c in claims if c.status == "unsupported"]),
        "inconclusive": len([c for c in claims if c.status == "inconclusive"]),
        "findings_open": len([f for f in findings if f.status == "open"]),
        "findings_resolved": len([f for f in findings if f.status == "resolved"]),
    }
    return data


@router.patch("/submissions/{submission_id}")
def update_submission(
    submission_id: str,
    payload: SubmissionUpdate,
    ctx: CurrentUser = Depends(require("upload_content")),
    db: Session = Depends(get_db),
):
    submission = _submission_or_404(db, ctx.org_id, submission_id, ctx)
    if submission.status in {"under_review", "approved", "rejected"}:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Content in '{submission.status}' state cannot be edited. Reopen it as a draft first.",
        )
    text_changed = payload.text is not None and payload.text != submission.raw_text
    if payload.title is not None:
        submission.title = payload.title
    if payload.campaign is not None:
        submission.campaign = payload.campaign
    if payload.product is not None:
        submission.product = payload.product
    if payload.content_type is not None:
        submission.content_type = payload.content_type
    if text_changed:
        submission.raw_text = payload.text
        submission.current_version += 1
        _add_version(db, submission, payload.note or "Content edited", ctx.user.id)
    record_audit(
        db, ctx.org_id, ctx.user.id, "content.updated", "content", submission.id, submission.title,
        previous_value=f"v{submission.current_version - 1}" if text_changed else "",
        updated_value=f"v{submission.current_version}", content_version=submission.current_version,
        meta={"text_changed": text_changed},
    )
    db.commit()
    db.refresh(submission)
    return submission_out(submission, include_text=True)


@router.delete("/submissions/{submission_id}")
def delete_submission(
    submission_id: str,
    ctx: CurrentUser = Depends(require("manage_org")),
    db: Session = Depends(get_db),
):
    submission = _submission_or_404(db, ctx.org_id, submission_id, ctx)
    record_audit(
        db, ctx.org_id, ctx.user.id, "content.deleted", "content", submission.id, submission.title,
        previous_value=submission.status,
    )
    db.delete(submission)
    db.commit()
    return {"message": "Content submission deleted."}


# --------------------------------------------------------------------------- analysis and corrections


@router.post("/submissions/{submission_id}/analyze")
def analyze_submission(
    submission_id: str,
    payload: AnalysisRequest | None = None,
    ctx: CurrentUser = Depends(require("upload_content")),
    db: Session = Depends(get_db),
):
    submission = _submission_or_404(db, ctx.org_id, submission_id, ctx)
    result = run_analysis(db, submission, ctx.user.id)
    db.refresh(submission)
    return result | {"submission": submission_out(submission)}


@router.post("/submissions/{submission_id}/apply-corrections")
def apply_corrections(
    submission_id: str,
    payload: ApplyCorrectionsRequest,
    ctx: CurrentUser = Depends(require("apply_corrections")),
    db: Session = Depends(get_db),
):
    submission = _submission_or_404(db, ctx.org_id, submission_id, ctx)
    if submission.status == "approved":
        raise HTTPException(status.HTTP_409_CONFLICT, "Approved content cannot be modified in place.")

    query = select(ReviewFinding).where(
        ReviewFinding.submission_id == submission.id,
        ReviewFinding.status.in_(["accepted", "modified", "open"]),
    )
    if payload.finding_ids:
        query = query.where(ReviewFinding.id.in_(payload.finding_ids))
    findings = db.scalars(query.order_by(ReviewFinding.created_at)).all()
    applicable = [f for f in findings if f.suggested_correction and f.original_text]

    if not applicable:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "There are no findings with an actionable correction. Accept a suggestion first.",
        )

    updated_text = submission.raw_text or ""
    applied, skipped = [], []
    for finding in applicable:
        if finding.original_text in updated_text:
            updated_text = updated_text.replace(finding.original_text, finding.suggested_correction, 1)
            applied.append(finding)
        else:
            skipped.append(finding)

    if not applied:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The original wording no longer appears in this version, so the corrections do not apply.",
        )

    submission.raw_text = updated_text
    submission.current_version += 1
    _add_version(
        db, submission,
        payload.note or f"Applied {len(applied)} reviewer correction(s)",
        ctx.user.id,
    )
    for finding in applied:
        finding.status = "resolved"
        finding.resolved_by = ctx.user.id
        finding.resolved_at = datetime.utcnow()
    for finding in skipped:
        finding.status = "rejected"

    record_audit(
        db, ctx.org_id, ctx.user.id, "content.corrections_applied", "content", submission.id,
        submission.title, updated_value=f"{len(applied)} correction(s)",
        content_version=submission.current_version,
        meta={"skipped": len(skipped), "finding_ids": [f.id for f in applied]},
    )
    db.commit()
    db.refresh(submission)
    result = run_analysis(db, submission, ctx.user.id)
    db.refresh(submission)
    return {
        "submission": submission_out(submission, include_text=True),
        "applied": len(applied),
        "skipped": len(skipped),
        "analysis": result,
    }


# --------------------------------------------------------------------------- status and approvals


@router.post("/submissions/{submission_id}/status")
def transition_status(
    submission_id: str,
    payload: StatusTransition,
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
):
    submission = _submission_or_404(db, ctx.org_id, submission_id, ctx)
    if payload.status == submission.status:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Content is already in that state.")
    if payload.status not in TRANSITIONS.get(submission.status, set()):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot move content from '{submission.status}' to '{payload.status}'.",
        )
    permission = STATUS_PERMISSION[payload.status]
    if not ctx.can(permission):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Your role cannot perform this workflow action. Approvals require an approver or administrator.",
        )
    if payload.status in {"submitted", "draft"} and submission.submitted_by != ctx.user.id and not ctx.can("manage_org"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the submitter can reopen or resubmit this content.")

    previous = submission.status
    submission.status = payload.status
    if payload.status == "approved":
        submission.approved_by = ctx.user.id
        submission.approved_at = datetime.utcnow()
    record_audit(
        db, ctx.org_id, ctx.user.id, "content.status_changed", "content", submission.id,
        submission.title, previous_value=previous, updated_value=payload.status,
        content_version=submission.current_version,
        decision=payload.status if payload.status in {"approved", "rejected"} else "",
        meta={"notes": payload.notes},
    )
    record = ApprovalRecord(
        organisation_id=ctx.org_id, entity_type="content", entity_id=submission.id,
        decision=payload.status if payload.status in {"approved", "rejected", "changes_requested"} else "status_change",
        notes=payload.notes, previous_status=previous, new_status=payload.status, actor_id=ctx.user.id,
    )
    db.add(record)
    if payload.status in {"approved", "rejected", "changes_requested"}:
        _notify_owner(
            db, ctx, submission,
            title=f"Content {payload.status.replace('_', ' ')}",
            message=f"\"{submission.title}\" moved to {payload.status.replace('_', ' ')}.",
            type_="success" if payload.status == "approved" else "warning",
        )
    db.commit()
    db.refresh(submission)
    return submission_out(submission) | {"approval": approval_out(record)}


@router.post("/submissions/{submission_id}/decision")
def decide_submission(
    submission_id: str,
    payload: ApprovalDecision,
    ctx: CurrentUser = Depends(require("approve_content")),
    db: Session = Depends(get_db),
):
    submission = _submission_or_404(db, ctx.org_id, submission_id, ctx)
    if submission.status not in {"submitted", "under_review"}:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Only submitted or under-review content can receive a final decision.",
        )
    previous = submission.status
    new_status = DECISION_STATUS[payload.decision]
    submission.status = new_status
    if payload.decision == "approved":
        submission.approved_by = ctx.user.id
        submission.approved_at = datetime.utcnow()

    approval = _record_approval(db, ctx, submission, payload.decision, previous, payload.notes)
    record_audit(
        db, ctx.org_id, ctx.user.id, "content.decided", "content", submission.id, submission.title,
        previous_value=previous, updated_value=new_status, decision=payload.decision,
        content_version=submission.current_version, meta={"notes": payload.notes},
    )
    _notify_owner(
        db, ctx, submission,
        title=f"Content {new_status.replace('_', ' ')}",
        message=f"\"{submission.title}\" was {new_status.replace('_', ' ')} by {ctx.user.full_name}.",
        type_="success" if new_status == "approved" else "warning",
    )
    db.commit()
    db.refresh(submission)
    return submission_out(submission) | {"approval": approval_out(approval)}


@router.get("/submissions/{submission_id}/approvals")
def submission_approvals(
    submission_id: str,
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
):
    submission = _submission_or_404(db, ctx.org_id, submission_id, ctx)
    records = db.scalars(
        select(ApprovalRecord).where(
            ApprovalRecord.entity_type == "content", ApprovalRecord.entity_id == submission.id
        ).order_by(ApprovalRecord.created_at.desc())
    ).all()
    return {"items": [approval_out(r) for r in records], "total": len(records)}


# --------------------------------------------------------------------------- comments


@router.get("/submissions/{submission_id}/comments")
def list_comments(
    submission_id: str,
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
):
    submission = _submission_or_404(db, ctx.org_id, submission_id, ctx)
    comments = db.scalars(
        select(Comment).where(Comment.submission_id == submission.id).order_by(Comment.created_at)
    ).all()
    return {"items": [comment_out(c) for c in comments], "total": len(comments)}


@router.post("/submissions/{submission_id}/comments", status_code=201)
def add_comment(
    submission_id: str,
    payload: CommentCreate,
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
):
    submission = _submission_or_404(db, ctx.org_id, submission_id, ctx)
    comment = Comment(
        organisation_id=ctx.org_id, submission_id=submission.id, author_id=ctx.user.id, body=payload.body,
    )
    db.add(comment)
    _notify_owner(
        db, ctx, submission,
        title="New comment on your content",
        message=f"{ctx.user.full_name} commented on \"{submission.title}\": {payload.body[:120]}",
        type_="comment",
    )
    record_audit(
        db, ctx.org_id, ctx.user.id, "content.commented", "content", submission.id, submission.title,
        updated_value=payload.body[:200],
    )
    db.commit()
    db.refresh(comment)
    return comment_out(comment)
