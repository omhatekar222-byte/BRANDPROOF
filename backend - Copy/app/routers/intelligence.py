import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_context, require
from app.db.session import get_db
from app.models import (
    BrandGuideline, ContentSubmission, ExtractedClaim, GuidelineProposal, GuidelineVersion,
    RecurringIssueGroup,
)
from app.routers.common import clamp_page, paginate
from app.schemas import (
    AnalyzeFeedbackRequest, ProposalCreate, ProposalDecision, WhatIfRequest,
)
from app.services.audit import notify, record_audit
from app.services.intelligence import (
    ROOT_CAUSE_LABELS, analyse_feedback, create_proposal,
)
from app.services.serializers import group_out, proposal_out

def _deny_creators(ctx: CurrentUser = Depends(get_context)) -> None:
    """Guideline intelligence is a manager workspace; creators see only their
    own finding-level feedback."""
    if ctx.role == "content_creator":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Your role cannot access guideline intelligence.",
        )


router = APIRouter(prefix="/intelligence", tags=["Guideline intelligence"], dependencies=[Depends(_deny_creators)])

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "must", "should", "shall", "will",
    "have", "has", "are", "was", "were", "not", "any", "all", "their", "which", "when",
    "where", "how", "into", "your", "our", "can", "may", "use", "used", "using", "content",
}


def _tokens(text: str) -> set[str]:
    return {
        t for t in re.findall(r"[a-z][a-z\-]{3,}", (text or "").lower())
        if t not in STOPWORDS
    }


def _group_or_404(db: Session, org_id: str, group_id: str) -> RecurringIssueGroup:
    group = db.get(RecurringIssueGroup, group_id)
    if not group or group.organisation_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recurring issue group not found")
    return group


def _proposal_or_404(db: Session, org_id: str, proposal_id: str) -> GuidelineProposal:
    proposal = db.get(GuidelineProposal, proposal_id)
    if not proposal or proposal.organisation_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")
    return proposal


@router.get("/groups")
def list_groups(
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status"),
    category: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    page, page_size = clamp_page(page, page_size)
    filters = [RecurringIssueGroup.organisation_id == ctx.org_id]
    if status_filter:
        filters.append(RecurringIssueGroup.status == status_filter)
    if category:
        filters.append(RecurringIssueGroup.category == category)
    total = db.scalar(select(func.count()).select_from(RecurringIssueGroup).where(*filters)) or 0
    groups = db.scalars(
        select(RecurringIssueGroup).where(*filters)
        .order_by(RecurringIssueGroup.finding_count.desc(), RecurringIssueGroup.last_seen.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = []
    for group in groups:
        item = group_out(group)
        item["root_cause_label"] = ROOT_CAUSE_LABELS.get(group.possible_root_cause, group.possible_root_cause)
        item["affected_count"] = len(group.affected_submission_ids or [])
        items.append(item)
    return paginate(items, total, page, page_size)


@router.post("/analyze")
def analyze_feedback(
    payload: AnalyzeFeedbackRequest | None = None,
    ctx: CurrentUser = Depends(require("review_content")),
    db: Session = Depends(get_db),
):
    groups = analyse_feedback(db, ctx.org_id)
    db.commit()
    record_audit(
        db, ctx.org_id, ctx.user.id, "intelligence.feedback_analyzed", "recurring_group", "",
        "Feedback pattern analysis", updated_value=f"{len(groups)} recurring group(s)",
        meta={"rebuilt": payload.rebuild if payload else True},
    )
    db.commit()
    return {
        "groups": [group_out(g) | {
            "root_cause_label": ROOT_CAUSE_LABELS.get(g.possible_root_cause, g.possible_root_cause),
        } for g in groups],
        "total": len(groups),
        "method": (
            "Structured reviewer feedback grouped by category and issue-title similarity. "
            "Root causes are rule-based hypotheses, not model training."
        ),
    }


@router.get("/groups/{group_id}")
def get_group(
    group_id: str,
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
):
    group = _group_or_404(db, ctx.org_id, group_id)
    proposals = db.scalars(
        select(GuidelineProposal).where(GuidelineProposal.group_id == group.id)
        .order_by(GuidelineProposal.created_at.desc())
    ).all()
    submissions = db.scalars(
        select(ContentSubmission).where(
            ContentSubmission.id.in_(group.affected_submission_ids or [""])
        )
    ).all()
    guideline = None
    if group.possible_root_cause and proposals and proposals[0].guideline_id:
        guideline = db.get(BrandGuideline, proposals[0].guideline_id)
    data = group_out(group)
    data["root_cause_label"] = ROOT_CAUSE_LABELS.get(group.possible_root_cause, group.possible_root_cause)
    data["affected_content"] = [
        {
            "id": s.id, "title": s.title, "status": s.status,
            "content_type": s.content_type, "campaign": s.campaign,
        }
        for s in submissions
    ]
    data["proposals"] = [proposal_out(p) for p in proposals]
    data["guideline"] = {
        "id": guideline.id, "title": guideline.title, "category": guideline.category,
        "content": guideline.content, "version": guideline.version, "status": guideline.status,
    } if guideline else None
    return data


@router.post("/groups/{group_id}/proposal", status_code=201)
def propose_from_group(
    group_id: str,
    ctx: CurrentUser = Depends(require("approve_guidelines")),
    db: Session = Depends(get_db),
):
    group = _group_or_404(db, ctx.org_id, group_id)
    existing = db.scalars(
        select(GuidelineProposal).where(
            GuidelineProposal.group_id == group.id, GuidelineProposal.status == "pending"
        )
    ).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "A pending proposal already exists for this group.")
    proposal = create_proposal(db, ctx.org_id, group, ctx.user.id)
    record_audit(
        db, ctx.org_id, ctx.user.id, "intelligence.proposal_created", "guideline_proposal",
        proposal.id, proposal.title, updated_value="pending",
        meta={"group_id": group.id, "root_cause": proposal.root_cause},
    )
    notify(
        db, ctx.org_id,
        title="Guideline clarification proposed",
        message=f"\"{proposal.title}\" is awaiting a decision.",
        type="approval", link="/guideline-intelligence",
    )
    db.commit()
    db.refresh(proposal)
    return proposal_out(proposal)


@router.post("/proposals", status_code=201)
def create_custom_proposal(
    payload: ProposalCreate,
    ctx: CurrentUser = Depends(require("approve_guidelines")),
    db: Session = Depends(get_db),
):
    group = _group_or_404(db, ctx.org_id, payload.group_id) if payload.group_id else None
    guideline = None
    if payload.guideline_id:
        guideline = db.get(BrandGuideline, payload.guideline_id)
        if not guideline or guideline.organisation_id != ctx.org_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Guideline not found")
    proposal = GuidelineProposal(
        organisation_id=ctx.org_id,
        group_id=group.id if group else None,
        guideline_id=guideline.id if guideline else None,
        title=payload.title,
        current_rule=payload.current_rule or (guideline.content if guideline else ""),
        proposed_rule=payload.proposed_rule,
        rationale=payload.rationale,
        root_cause=payload.root_cause,
        evidence=group.example_corrections if group else [],
        created_by=ctx.user.id,
        status="pending",
    )
    db.add(proposal)
    record_audit(
        db, ctx.org_id, ctx.user.id, "intelligence.proposal_created", "guideline_proposal",
        proposal.id, proposal.title, updated_value="pending",
    )
    db.commit()
    db.refresh(proposal)
    return proposal_out(proposal)


@router.get("/proposals")
def list_proposals(
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = 1,
    page_size: int = 50,
):
    page, page_size = clamp_page(page, page_size)
    filters = [GuidelineProposal.organisation_id == ctx.org_id]
    if status_filter:
        filters.append(GuidelineProposal.status == status_filter)
    total = db.scalar(select(func.count()).select_from(GuidelineProposal).where(*filters)) or 0
    proposals = db.scalars(
        select(GuidelineProposal).where(*filters).order_by(GuidelineProposal.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return paginate([proposal_out(p) for p in proposals], total, page, page_size)


@router.get("/proposals/{proposal_id}")
def get_proposal(
    proposal_id: str,
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
):
    proposal = _proposal_or_404(db, ctx.org_id, proposal_id)
    guideline = db.get(BrandGuideline, proposal.guideline_id) if proposal.guideline_id else None
    data = proposal_out(proposal)
    data["root_cause_label"] = ROOT_CAUSE_LABELS.get(proposal.root_cause, proposal.root_cause)
    data["guideline"] = {
        "id": guideline.id, "title": guideline.title, "category": guideline.category,
        "content": guideline.content, "version": guideline.version,
    } if guideline else None
    return data


@router.post("/proposals/{proposal_id}/decision")
def decide_proposal(
    proposal_id: str,
    payload: ProposalDecision,
    ctx: CurrentUser = Depends(require("approve_guidelines")),
    db: Session = Depends(get_db),
):
    proposal = _proposal_or_404(db, ctx.org_id, proposal_id)
    if proposal.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "This proposal has already been decided.")

    proposal.status = payload.decision
    proposal.decided_by = ctx.user.id
    proposal.decided_at = datetime.utcnow()
    guideline_version = None
    applied_to = None

    if payload.decision == "approved":
        guideline = db.get(BrandGuideline, proposal.guideline_id) if proposal.guideline_id else None
        if guideline is None:
            guideline = BrandGuideline(
                organisation_id=ctx.org_id,
                title=proposal.title.replace("Clarify guideline:", "").strip() or proposal.title,
                category="messaging",
                content=proposal.proposed_rule,
                summary="Created from an approved reviewer-feedback proposal.",
                status="approved",
                version=1,
                owner_id=ctx.user.id,
            )
            db.add(guideline)
            db.flush()
            proposal.guideline_id = guideline.id
        else:
            guideline.content = proposal.proposed_rule
            guideline.version += 1
            guideline.status = "approved"
        guideline_version = guideline.version
        db.add(GuidelineVersion(
            guideline_id=guideline.id,
            version=guideline.version,
            content=guideline.content,
            change_summary=f"Approved clarification from proposal: {proposal.title}",
            status="approved",
            created_by=ctx.user.id,
            approved_by=ctx.user.id,
        ))
        applied_to = {"guideline_id": guideline.id, "title": guideline.title, "version": guideline.version}
        if proposal.group_id:
            group = db.get(RecurringIssueGroup, proposal.group_id)
            if group:
                group.status = "dismissed"

    record_audit(
        db, ctx.org_id, ctx.user.id, "intelligence.proposal_decided", "guideline_proposal",
        proposal.id, proposal.title, updated_value=payload.decision, decision=payload.decision,
        guideline_version=guideline_version, meta={"notes": payload.notes},
    )
    if proposal.created_by and proposal.created_by != ctx.user.id:
        notify(
            db, ctx.org_id,
            title=f"Guideline proposal {payload.decision.replace('_', ' ')}",
            message=f"\"{proposal.title}\" was {payload.decision.replace('_', ' ')}.",
            type="success" if payload.decision == "approved" else "warning",
            link="/guideline-intelligence", user_id=proposal.created_by,
        )
    db.commit()
    db.refresh(proposal)
    return proposal_out(proposal) | {"applied_to": applied_to}


@router.post("/what-if")
def what_if(
    payload: WhatIfRequest,
    ctx: CurrentUser = Depends(require("approve_guidelines")),
    db: Session = Depends(get_db),
):
    """Estimate which registered content a rule change could affect.

    This is a transparent keyword-overlap estimate over records already stored in
    this workspace. It never modifies content or claims compliance.
    """
    current = _tokens(payload.current_rule)
    proposed = _tokens(payload.proposed_rule)
    added = proposed - current
    submissions = db.scalars(
        select(ContentSubmission).where(ContentSubmission.organisation_id == ctx.org_id)
    ).all()
    claims = db.scalars(
        select(ExtractedClaim).where(ExtractedClaim.organisation_id == ctx.org_id)
    ).all()

    affected = []
    for submission in submissions:
        text = (submission.raw_text or "").lower()
        rule_hits = sorted({t for t in added if re.search(rf"\b{re.escape(t)}\b", text)})
        related_claims = [c for c in claims if c.submission_id == submission.id and c.status != "supported"]
        if rule_hits or (related_claims and added):
            affected.append({
                "id": submission.id,
                "title": submission.title,
                "status": submission.status,
                "content_type": submission.content_type,
                "campaign": submission.campaign,
                "reason": (
                    f"Contains wording introduced by the proposed rule: {', '.join(rule_hits[:5])}."
                    if rule_hits else
                    f"Has {len(related_claims)} flagged claim(s) in this issue area."
                ),
                "flagged_claims": len(related_claims),
                "matched_terms": rule_hits,
            })

    return {
        "current_terms": len(current),
        "proposed_terms": len(proposed),
        "new_terms": sorted(added)[:25],
        "affected_total": len(affected),
        "affected": affected[:60],
        "registered_total": len(submissions),
        "disclaimer": (
            "Estimate only, based on keyword overlap with content registered in this workspace. "
            "Nothing is changed automatically."
        ),
    }
