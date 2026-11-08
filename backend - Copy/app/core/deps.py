from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models import Membership, Organisation, User

bearer = HTTPBearer(auto_error=False)

ROLE_LABELS = {
    "admin": "Administrator",
    "content_creator": "Content Creator",
    "reviewer": "Reviewer",
    "approver": "Approver",
}

ROLE_PERMISSIONS = {
    "admin": {
        "manage_org", "manage_users", "manage_roles", "upload_knowledge", "approve_knowledge",
        "approve_guidelines", "upload_content", "review_content", "approve_content",
        "view_analytics", "view_audit", "manage_settings", "apply_corrections",
    },
    "content_creator": {"upload_content", "apply_corrections", "view_analytics"},
    "reviewer": {"review_content", "view_analytics"},
    "approver": {"approve_content", "approve_guidelines", "approve_knowledge", "view_analytics", "view_audit"},
}


@dataclass
class CurrentUser:
    user: User
    membership: Membership
    organisation: Organisation

    @property
    def org_id(self) -> str:
        return self.organisation.id

    @property
    def role(self) -> str:
        return self.membership.role

    @property
    def permissions(self) -> set[str]:
        return ROLE_PERMISSIONS.get(self.role, set())

    def can(self, permission: str) -> bool:
        return permission in self.permissions


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session")
    user = db.get(User, payload.get("sub"))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account is inactive")
    return user


def get_context(
    user: User = Depends(get_current_user),
    x_organisation_id: str | None = Header(default=None, alias="X-Organisation-Id"),
    db: Session = Depends(get_db),
) -> CurrentUser:
    memberships = db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
    if not memberships:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not belong to an organisation")
    membership = None
    if x_organisation_id:
        membership = next((m for m in memberships if m.organisation_id == x_organisation_id), None)
        if not membership:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this workspace")
    else:
        membership = memberships[0]
    org = db.get(Organisation, membership.organisation_id)
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organisation not found")
    return CurrentUser(user=user, membership=membership, organisation=org)


def require(*permissions: str):
    def dependency(ctx: CurrentUser = Depends(get_context)) -> CurrentUser:
        missing = [p for p in permissions if not ctx.can(p)]
        if missing:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Your role ({ROLE_LABELS.get(ctx.role, ctx.role)}) cannot perform this action.",
            )
        return ctx
    return dependency


def require_any(*permissions: str):
    def dependency(ctx: CurrentUser = Depends(get_context)) -> CurrentUser:
        if not any(ctx.can(p) for p in permissions):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Your role ({ROLE_LABELS.get(ctx.role, ctx.role)}) cannot perform this action.",
            )
        return ctx
    return dependency
