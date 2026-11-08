"""Campaigns & Task Assignments — two-workspace brand governance router.

Manager workspace  → create campaigns, assign tasks, approve/reject submissions
Creator workspace  → view own tasks, read campaign brief, submit content
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_context, require, require_any
from app.db.session import get_db
from app.models import Campaign, ContentSubmission, Membership, TaskAssignment, User

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


# ─── Pydantic schemas ─────────────────────────────────────────────────────────

class CampaignCreate(BaseModel):
    name: str
    product: str = ""
    objective: str = ""
    target_audience: str = ""
    platform: str = ""
    content_type: str = "advertisement"
    description: str = ""
    approved_claims_text: str = ""
    prohibited_claims_text: str = ""
    mandatory_messages: str = ""
    tone_of_voice: str = ""
    cta: str = ""
    deadline: datetime | None = None
    priority: str = "medium"
    knowledge_document_ids: list[str] = []
    deliverables: list[dict] = []


class CampaignUpdate(BaseModel):
    name: str | None = None
    product: str | None = None
    objective: str | None = None
    target_audience: str | None = None
    platform: str | None = None
    content_type: str | None = None
    description: str | None = None
    approved_claims_text: str | None = None
    prohibited_claims_text: str | None = None
    mandatory_messages: str | None = None
    tone_of_voice: str | None = None
    cta: str | None = None
    deadline: datetime | None = None
    priority: str | None = None
    status: str | None = None
    knowledge_document_ids: list[str] | None = None
    deliverables: list[dict] | None = None


class TaskCreate(BaseModel):
    creator_id: str
    title: str
    instructions: str = ""
    priority: str = "medium"
    deadline: datetime | None = None


class TaskStatusUpdate(BaseModel):
    status: str
    notes: str = ""
    submission_id: str | None = None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _campaign_to_dict(c: Campaign, include_internal: bool = True) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": c.id,
        "name": c.name,
        "product": c.product,
        "objective": c.objective,
        "target_audience": c.target_audience,
        "platform": c.platform,
        "content_type": c.content_type,
        "description": c.description,
        "approved_claims_text": c.approved_claims_text,
        "prohibited_claims_text": c.prohibited_claims_text,
        "mandatory_messages": c.mandatory_messages,
        "tone_of_voice": c.tone_of_voice,
        "cta": c.cta,
        "deadline": c.deadline.isoformat() if c.deadline else None,
        "priority": c.priority,
        "status": c.status,
        "deliverables": c.deliverables or [],
        "task_count": len(c.task_assignments) if c.task_assignments is not None else 0,
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat(),
        "created_by_name": c.creator.full_name if c.creator else None,
    }
    if include_internal:
        base["knowledge_document_ids"] = c.knowledge_document_ids or []
        base["assigned_creator_ids"] = c.assigned_creator_ids or []
    return base


def _task_to_dict(t: TaskAssignment, include_brief: bool = False) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": t.id,
        "campaign_id": t.campaign_id,
        "campaign_name": t.campaign.name if t.campaign else "",
        "title": t.title,
        "instructions": t.instructions,
        "status": t.status,
        "priority": t.priority,
        "deadline": t.deadline.isoformat() if t.deadline else None,
        "creator_name": t.creator.full_name if t.creator else "",
        "creator_email": t.creator.email if t.creator else "",
        "manager_name": t.manager.full_name if t.manager else "",
        "submission_id": t.submission_id,
        "manager_notes": t.manager_notes,
        "creator_notes": t.creator_notes,
        "created_at": t.created_at.isoformat(),
        "updated_at": t.updated_at.isoformat(),
    }
    if include_brief and t.campaign:
        c = t.campaign
        d["brief"] = {
            "campaign_name": c.name,
            "product": c.product,
            "objective": c.objective,
            "target_audience": c.target_audience,
            "platform": c.platform,
            "content_type": c.content_type,
            "approved_claims": c.approved_claims_text,
            "prohibited_claims": c.prohibited_claims_text,
            "mandatory_messages": c.mandatory_messages,
            "tone_of_voice": c.tone_of_voice,
            "cta": c.cta,
            "deadline": c.deadline.isoformat() if c.deadline else None,
            "deliverables": c.deliverables or [],
        }
    return d


# ─── Campaign endpoints ───────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
def create_campaign(
    body: CampaignCreate,
    ctx: CurrentUser = Depends(require("manage_org")),
    db: Session = Depends(get_db),
) -> dict:
    campaign = Campaign(
        organisation_id=ctx.org_id,
        created_by=ctx.user.id,
        **body.model_dump(),
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return _campaign_to_dict(campaign)


@router.get("")
def list_campaigns(
    status_filter: str | None = None,
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
) -> dict:
    q = select(Campaign).where(Campaign.organisation_id == ctx.org_id)

    # Creators only see campaigns they're assigned to
    if ctx.role == "content_creator":
        # Get campaign IDs where this creator has a task
        task_rows = db.scalars(
            select(TaskAssignment.campaign_id).where(
                TaskAssignment.organisation_id == ctx.org_id,
                TaskAssignment.creator_id == ctx.user.id,
            )
        ).all()
        q = q.where(Campaign.id.in_(task_rows))

    if status_filter:
        q = q.where(Campaign.status == status_filter)

    q = q.order_by(Campaign.created_at.desc())
    campaigns = db.scalars(q).all()
    is_manager = ctx.role in ("admin", "approver", "reviewer")
    return {"items": [_campaign_to_dict(c, include_internal=is_manager) for c in campaigns]}


@router.get("/{campaign_id}")
def get_campaign(
    campaign_id: str,
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
) -> dict:
    campaign = db.get(Campaign, campaign_id)
    if not campaign or campaign.organisation_id != ctx.org_id:
        raise HTTPException(404, "Campaign not found")

    # Creators must have an assignment for this campaign
    if ctx.role == "content_creator":
        task = db.scalars(
            select(TaskAssignment).where(
                TaskAssignment.campaign_id == campaign_id,
                TaskAssignment.creator_id == ctx.user.id,
            )
        ).first()
        if not task:
            raise HTTPException(403, "You are not assigned to this campaign")

    is_manager = ctx.role in ("admin", "approver", "reviewer")
    return _campaign_to_dict(campaign, include_internal=is_manager)


@router.get("/{campaign_id}/brief")
def get_campaign_brief(
    campaign_id: str,
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
) -> dict:
    """Creator-safe campaign brief — never exposes raw knowledge document text."""
    campaign = db.get(Campaign, campaign_id)
    if not campaign or campaign.organisation_id != ctx.org_id:
        raise HTTPException(404, "Campaign not found")

    # Verify creator has an assignment for this campaign
    task = db.scalars(
        select(TaskAssignment).where(
            TaskAssignment.campaign_id == campaign_id,
            TaskAssignment.creator_id == ctx.user.id,
        )
    ).first()
    if not task and ctx.role == "content_creator":
        raise HTTPException(403, "You are not assigned to this campaign")

    return {
        "campaign_id": campaign.id,
        "campaign_name": campaign.name,
        "product": campaign.product,
        "objective": campaign.objective,
        "target_audience": campaign.target_audience,
        "platform": campaign.platform,
        "content_type": campaign.content_type,
        "approved_claims": campaign.approved_claims_text,
        "prohibited_claims": campaign.prohibited_claims_text,
        "mandatory_messages": campaign.mandatory_messages,
        "tone_of_voice": campaign.tone_of_voice,
        "cta": campaign.cta,
        "deadline": campaign.deadline.isoformat() if campaign.deadline else None,
        "deliverables": campaign.deliverables or [],
        "task_id": task.id if task else None,
        "task_instructions": task.instructions if task else "",
        "task_status": task.status if task else None,
    }


@router.patch("/{campaign_id}")
def update_campaign(
    campaign_id: str,
    body: CampaignUpdate,
    ctx: CurrentUser = Depends(require("manage_org")),
    db: Session = Depends(get_db),
) -> dict:
    campaign = db.get(Campaign, campaign_id)
    if not campaign or campaign.organisation_id != ctx.org_id:
        raise HTTPException(404, "Campaign not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(campaign, field, value)
    campaign.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(campaign)
    return _campaign_to_dict(campaign)


# ─── Task Assignment endpoints ────────────────────────────────────────────────

@router.post("/{campaign_id}/tasks", status_code=status.HTTP_201_CREATED)
def assign_task(
    campaign_id: str,
    body: TaskCreate,
    ctx: CurrentUser = Depends(require("manage_org")),
    db: Session = Depends(get_db),
) -> dict:
    campaign = db.get(Campaign, campaign_id)
    if not campaign or campaign.organisation_id != ctx.org_id:
        raise HTTPException(404, "Campaign not found")

    # Verify creator is in same org
    creator_membership = db.scalars(
        select(Membership).where(
            Membership.user_id == body.creator_id,
            Membership.organisation_id == ctx.org_id,
            Membership.role == "content_creator",
        )
    ).first()
    if not creator_membership:
        raise HTTPException(400, "Creator not found in this organisation")

    task = TaskAssignment(
        organisation_id=ctx.org_id,
        campaign_id=campaign_id,
        creator_id=body.creator_id,
        manager_id=ctx.user.id,
        title=body.title,
        instructions=body.instructions,
        priority=body.priority,
        deadline=body.deadline,
        status="assigned",
    )
    db.add(task)

    # Update campaign's assigned_creator_ids
    ids = list(campaign.assigned_creator_ids or [])
    if body.creator_id not in ids:
        ids.append(body.creator_id)
        campaign.assigned_creator_ids = ids

    db.commit()
    db.refresh(task)
    return _task_to_dict(task, include_brief=True)


@router.get("/{campaign_id}/tasks")
def list_campaign_tasks(
    campaign_id: str,
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
) -> dict:
    campaign = db.get(Campaign, campaign_id)
    if not campaign or campaign.organisation_id != ctx.org_id:
        raise HTTPException(404, "Campaign not found")

    q = select(TaskAssignment).where(TaskAssignment.campaign_id == campaign_id)
    if ctx.role == "content_creator":
        q = q.where(TaskAssignment.creator_id == ctx.user.id)
    tasks = db.scalars(q).all()
    return {"items": [_task_to_dict(t) for t in tasks]}


# ─── My Tasks (creator-centric) ────────────────────────────────────────────────

tasks_router = APIRouter(prefix="/tasks", tags=["Tasks"])


@tasks_router.get("")
def list_my_tasks(
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
) -> dict:
    q = select(TaskAssignment).where(TaskAssignment.organisation_id == ctx.org_id)
    if ctx.role == "content_creator":
        q = q.where(TaskAssignment.creator_id == ctx.user.id)
    q = q.order_by(TaskAssignment.created_at.desc())
    tasks = db.scalars(q).all()
    return {"items": [_task_to_dict(t, include_brief=True) for t in tasks]}


@tasks_router.get("/{task_id}")
def get_task(
    task_id: str,
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
) -> dict:
    task = db.get(TaskAssignment, task_id)
    if not task or task.organisation_id != ctx.org_id:
        raise HTTPException(404, "Task not found")
    if ctx.role == "content_creator" and task.creator_id != ctx.user.id:
        raise HTTPException(403, "Access denied")
    return _task_to_dict(task, include_brief=True)


@tasks_router.patch("/{task_id}/status")
def update_task_status(
    task_id: str,
    body: TaskStatusUpdate,
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
) -> dict:
    task = db.get(TaskAssignment, task_id)
    if not task or task.organisation_id != ctx.org_id:
        raise HTTPException(404, "Task not found")

    CREATOR_ALLOWED = {"accepted", "in_progress", "submitted", "resubmitted"}
    MANAGER_ALLOWED = {"changes_requested", "awaiting_manager_approval", "approved", "rejected", "completed"}

    if ctx.role == "content_creator":
        if task.creator_id != ctx.user.id:
            raise HTTPException(403, "Access denied")
        if body.status not in CREATOR_ALLOWED:
            raise HTTPException(400, f"Creators cannot set status to '{body.status}'")
        task.creator_notes = body.notes
    else:
        if not ctx.can("manage_org") and not ctx.can("approve_content"):
            raise HTTPException(403, "Insufficient permissions")
        if body.status not in MANAGER_ALLOWED:
            raise HTTPException(400, f"Managers cannot set status to '{body.status}'")
        task.manager_notes = body.notes

    task.status = body.status
    if body.submission_id:
        task.submission_id = body.submission_id
    task.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)
    return _task_to_dict(task, include_brief=True)


@tasks_router.get("/{task_id}/brief")
def get_task_brief(
    task_id: str,
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
) -> dict:
    task = db.get(TaskAssignment, task_id)
    if not task or task.organisation_id != ctx.org_id:
        raise HTTPException(404, "Task not found")
    if ctx.role == "content_creator" and task.creator_id != ctx.user.id:
        raise HTTPException(403, "Access denied")
    return _task_to_dict(task, include_brief=True)

