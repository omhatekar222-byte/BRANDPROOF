from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import ROLE_LABELS, CurrentUser, get_context, require
from app.core.security import hash_password
from app.db.session import get_db
from app.models import (
    ApprovalRecord, ApprovedClaim, ApprovedFact, AuditEvent, BrandAsset, BrandGuideline,
    Campaign, ChangeImpact, Comment, ContentFactUsage, ContentSubmission, ContentVersion,
    DocumentVersion, ExtractedClaim, GuidelineProposal, GuidelineVersion, KnowledgeDocument,
    Membership, Notification, Organisation, RecurringIssueGroup, ReviewerFeedback,
    ReviewFinding, RolePermission, TaskAssignment, User,
)
from app.routers.common import clamp_page, paginate
from app.schemas import InviteMemberRequest, MemberUpdateRequest, OrgUpdate, RolePermissionUpdate
from app.services.audit import record_audit
from app.services.seed import ensure_nova_demo, seed_demo
from app.services.serializers import audit_out, member_out, org_out

router = APIRouter(prefix="/admin", tags=["Administration"])


@router.get("/overview")
def admin_overview(ctx: CurrentUser = Depends(require("manage_org")), db: Session = Depends(get_db)):
    members = db.scalars(select(Membership).where(Membership.organisation_id == ctx.org_id)).all()
    by_role: dict[str, int] = {}
    for m in members:
        by_role[m.role] = by_role.get(m.role, 0) + 1
    return {
        "organisation": org_out(ctx.organisation, ctx.role),
        "member_count": len(members),
        "by_role": by_role,
        "roles": [{"value": k, "label": v} for k, v in ROLE_LABELS.items()],
        "ai": {"configured": settings.ai_enabled, "provider": settings.AI_PROVIDER},
        "environment": settings.ENV,
    }


@router.get("/members")
def list_members(
    ctx: CurrentUser = Depends(require("manage_users")),
    db: Session = Depends(get_db),
    role: str | None = None,
    page: int = 1, page_size: int = 50,
):
    page, page_size = clamp_page(page, page_size)
    filters = [Membership.organisation_id == ctx.org_id]
    if role:
        filters.append(Membership.role == role)
    total = db.scalar(select(func.count()).select_from(Membership).where(*filters)) or 0
    rows = db.scalars(
        select(Membership).where(*filters).order_by(Membership.created_at)
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return paginate([member_out(m) for m in rows], total, page, page_size)


@router.post("/members", status_code=201)
def invite_member(
    payload: InviteMemberRequest,
    ctx: CurrentUser = Depends(require("manage_users")),
    db: Session = Depends(get_db),
):
    email = payload.email.lower()
    user = db.scalars(select(User).where(User.email == email)).first()
    if user is None:
        user = User(
            email=email, full_name=payload.full_name, title=payload.title or "Team member",
            hashed_password=hash_password("BrandProof123!"), avatar_color="#2F6BFF",
            preferences={"theme": "light"},
        )
        db.add(user)
        db.flush()
    existing = db.scalars(
        select(Membership).where(
            Membership.user_id == user.id, Membership.organisation_id == ctx.org_id
        )
    ).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "This user is already a member of the workspace.")
    membership = Membership(user_id=user.id, organisation_id=ctx.org_id, role=payload.role)
    db.add(membership)
    record_audit(
        db, ctx.org_id, ctx.user.id, "org.member_invited", "membership", membership.id,
        f"{user.full_name} ({email})", updated_value=payload.role,
        meta={"email": email, "role": payload.role},
    )
    db.commit()
    db.refresh(membership)
    return member_out(membership) | {"temporary_password_hint": "BrandProof123! (seed password for demo invites)"}


@router.patch("/members/{membership_id}")
def update_member(
    membership_id: str,
    payload: MemberUpdateRequest,
    ctx: CurrentUser = Depends(require("manage_users")),
    db: Session = Depends(get_db),
):
    membership = db.get(Membership, membership_id)
    if not membership or membership.organisation_id != ctx.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    if membership.user_id == ctx.user.id and payload.role != "admin":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot remove your own administrator role.")
    previous = membership.role
    membership.role = payload.role
    if payload.title is not None:
        membership.user.title = payload.title
    record_audit(
        db, ctx.org_id, ctx.user.id, "org.member_role_changed", "membership", membership.id,
        membership.user.full_name, previous_value=previous, updated_value=payload.role,
    )
    db.commit()
    db.refresh(membership)
    return member_out(membership)


@router.delete("/members/{membership_id}")
def remove_member(
    membership_id: str,
    ctx: CurrentUser = Depends(require("manage_users")),
    db: Session = Depends(get_db),
):
    membership = db.get(Membership, membership_id)
    if not membership or membership.organisation_id != ctx.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    if membership.user_id == ctx.user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot remove yourself.")
    record_audit(
        db, ctx.org_id, ctx.user.id, "org.member_removed", "membership", membership.id,
        membership.user.full_name, previous_value=membership.role,
    )
    db.delete(membership)
    db.commit()
    return {"message": "Member removed from the workspace."}


@router.get("/roles")
def role_matrix(ctx: CurrentUser = Depends(get_context), db: Session = Depends(get_db)):
    from app.core.deps import ROLE_PERMISSIONS
    return {
        "role": ctx.role,
        "roles": [
            {
                "value": role, "label": ROLE_LABELS.get(role, role),
                "permissions": sorted(perms),
            }
            for role, perms in ROLE_PERMISSIONS.items()
        ],
    }


@router.post("/roles/permissions")
def set_role_permission(
    payload: RolePermissionUpdate,
    ctx: CurrentUser = Depends(require("manage_roles")),
    db: Session = Depends(get_db),
):
    row = db.scalars(
        select(RolePermission).where(
            RolePermission.organisation_id == ctx.org_id,
            RolePermission.role == payload.role,
            RolePermission.permission == payload.permission,
        )
    ).first()
    if row:
        row.enabled = payload.enabled
    else:
        db.add(RolePermission(
            organisation_id=ctx.org_id, role=payload.role,
            permission=payload.permission, enabled=payload.enabled,
        ))
    record_audit(
        db, ctx.org_id, ctx.user.id, "org.role_permission_changed", "role_permission", "",
        f"{payload.role}: {payload.permission}", updated_value=str(payload.enabled),
    )
    db.commit()
    return {"role": payload.role, "permission": payload.permission, "enabled": payload.enabled}


@router.patch("/organisation")
def update_organisation(
    payload: OrgUpdate,
    ctx: CurrentUser = Depends(require("manage_org")),
    db: Session = Depends(get_db),
):
    org = ctx.organisation
    if payload.name is not None:
        org.name = payload.name
    if payload.industry is not None:
        org.industry = payload.industry
    if payload.brand_colors is not None:
        org.brand_colors = payload.brand_colors
    if payload.settings is not None:
        merged = dict(org.settings or {})
        merged.update(payload.settings)
        org.settings = merged
    record_audit(
        db, ctx.org_id, ctx.user.id, "org.updated", "organisation", org.id, org.name,
        updated_value=org.industry,
    )
    db.commit()
    db.refresh(org)
    return org_out(org, ctx.role)


@router.post("/demo/reset")
def reset_demo_workspace(
    ctx: CurrentUser = Depends(require("manage_org")),
    db: Session = Depends(get_db),
):
    """Rebuild the seeded demonstration workspaces from scratch.

    Only organisations flagged as demo are removed; real workspaces and accounts
    are untouched. This is an explicit, confirmed action in the UI.
    """
    demo_orgs = db.scalars(select(Organisation).where(Organisation.is_demo.is_(True))).all()
    if not demo_orgs:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No demonstration workspace exists to reset.")
    for org in demo_orgs:
        org_id = org.id
        submission_ids = [
            row[0] for row in db.query(ContentSubmission.id)
            .filter(ContentSubmission.organisation_id == org_id).all()
        ]
        document_ids = [
            row[0] for row in db.query(KnowledgeDocument.id)
            .filter(KnowledgeDocument.organisation_id == org_id).all()
        ]
        guideline_ids = [
            row[0] for row in db.query(BrandGuideline.id)
            .filter(BrandGuideline.organisation_id == org_id).all()
        ]
        # Child tables without an org column are removed through their parents.
        if submission_ids:
            db.query(ContentFactUsage).filter(
                ContentFactUsage.submission_id.in_(submission_ids)
            ).delete(synchronize_session=False)
            db.query(ContentVersion).filter(
                ContentVersion.submission_id.in_(submission_ids)
            ).delete(synchronize_session=False)
        if document_ids:
            db.query(DocumentVersion).filter(
                DocumentVersion.document_id.in_(document_ids)
            ).delete(synchronize_session=False)
        if guideline_ids:
            db.query(GuidelineVersion).filter(
                GuidelineVersion.guideline_id.in_(guideline_ids)
            ).delete(synchronize_session=False)
        # Delete org-scoped rows in dependency order (children before parents).
        for model in (
            ReviewerFeedback, ReviewFinding, ExtractedClaim, Comment, ApprovalRecord,
            ChangeImpact, TaskAssignment, Notification, AuditEvent, ContentSubmission,
            Campaign, GuidelineProposal, RecurringIssueGroup, BrandGuideline, ApprovedFact,
            ApprovedClaim, BrandAsset, KnowledgeDocument, Membership, RolePermission,
        ):
            db.query(model).filter(model.organisation_id == org_id).delete(synchronize_session=False)
        db.delete(org)
    db.commit()

    seed_demo(db)
    ensure_nova_demo(db)
    return {"message": "Demonstration workspace rebuilt from the original seed data."}


@router.get("/audit")
def audit_trail(
    ctx: CurrentUser = Depends(require("view_audit")),
    db: Session = Depends(get_db),
    q: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    page: int = 1, page_size: int = 50,
):
    page, page_size = clamp_page(page, page_size)
    filters = [AuditEvent.organisation_id == ctx.org_id]
    if q:
        like = f"%{q.strip()}%"
        filters.append(
            (AuditEvent.action.ilike(like) | AuditEvent.entity_label.ilike(like))
        )
    if action:
        filters.append(AuditEvent.action == action)
    if entity_type:
        filters.append(AuditEvent.entity_type == entity_type)
    total = db.scalar(select(func.count()).select_from(AuditEvent).where(*filters)) or 0
    rows = db.scalars(
        select(AuditEvent).where(*filters).order_by(AuditEvent.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    actions = db.scalars(
        select(AuditEvent.action).where(AuditEvent.organisation_id == ctx.org_id).distinct()
    ).all()
    return paginate([audit_out(e) for e in rows], total, page, page_size) | {"actions": sorted(actions)}


@router.get("/audit/entity/{entity_id}")
def audit_for_entity(
    entity_id: str,
    ctx: CurrentUser = Depends(require("view_audit")),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(AuditEvent).where(
            AuditEvent.organisation_id == ctx.org_id, AuditEvent.entity_id == entity_id
        ).order_by(AuditEvent.created_at)
    ).all()
    return {"items": [audit_out(e) for e in rows], "total": len(rows)}
