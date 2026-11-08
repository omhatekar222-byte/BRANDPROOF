import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import ROLE_LABELS, ROLE_PERMISSIONS, CurrentUser, get_context, get_current_user
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.db.session import get_db
from app.models import Membership, Organisation, User
from app.schemas import (
    ChangePasswordRequest, ForgotPasswordRequest, LoginRequest, ProfileUpdate,
    ResetPasswordRequest, RoleEntryRequest, SignUpRequest,
)
from app.services.serializers import org_out, user_brief

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _slug(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "workspace"
    return base[:70]


def _unique_slug(db: Session, name: str) -> str:
    base = _slug(name)
    slug, i = base, 2
    while db.scalars(select(Organisation).where(Organisation.slug == slug)).first():
        slug = f"{base}-{i}"
        i += 1
    return slug


def _session_payload(db: Session, user: User, active_org: Organisation | None = None) -> dict:
    memberships = db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
    organisations = []
    for membership in memberships:
        org = db.get(Organisation, membership.organisation_id)
        if org:
            organisations.append(org_out(org, membership.role))
    active_id = active_org.id if active_org else (organisations[0]["id"] if organisations else None)
    role = next((o["role"] for o in organisations if o["id"] == active_id), None)
    return {
        "access_token": create_token(user.id),
        "token_type": "bearer",
        "user": user_brief(user),
        "organisations": organisations,
        "active_organisation_id": active_id,
        "permissions": sorted(ROLE_PERMISSIONS.get(role or "", set())),
        "role": role,
        "role_label": ROLE_LABELS.get(role or "", role),
    }


@router.post("/signup", status_code=201)
def signup(payload: SignUpRequest, db: Session = Depends(get_db)):
    if db.scalars(select(User).where(User.email == payload.email.lower())).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    user = User(
        email=payload.email.lower(), full_name=payload.full_name,
        hashed_password=hash_password(payload.password), title="Administrator",
        avatar_color="#2F6BFF", preferences={"theme": "light"},
    )
    db.add(user)
    db.flush()
    org_name = payload.organisation_name or f"{payload.full_name.split()[0]}'s workspace"
    org = Organisation(
        name=org_name, slug=_unique_slug(db, org_name), industry="", is_demo=False, brand_colors=[],
        settings={"require_approval": True},
    )
    db.add(org)
    db.flush()
    db.add(Membership(user_id=user.id, organisation_id=org.id, role="admin"))
    db.commit()
    db.refresh(user)
    return _session_payload(db, user, org)


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalars(select(User).where(User.email == payload.email.lower())).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been deactivated.")
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return _session_payload(db, user)


@router.post("/entry")
def role_entry(payload: RoleEntryRequest, db: Session = Depends(get_db)):
    """Passwordless role entry for the demo workspace.

    This is deliberately not general authentication: it maps the two product
    roles onto the seeded NovaTech demonstration identities. Real accounts still
    use the password endpoints above.
    """
    email = "admin@novatech.demo" if payload.role == "administrator" else "creator@novatech.demo"
    user = db.scalars(select(User).where(User.email == email)).first()
    org = db.scalars(select(Organisation).where(Organisation.slug == "novatech")).first()
    if not user or not org:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The demonstration workspace is not available. Start the backend with demo seeding enabled.",
        )
    membership = db.scalars(
        select(Membership).where(
            Membership.user_id == user.id, Membership.organisation_id == org.id
        )
    ).first()
    if not membership:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This demo identity is not a workspace member.")
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    payload_out = _session_payload(db, user, org)
    payload_out["entry_role"] = payload.role
    return payload_out


@router.get("/me")
def me(ctx: CurrentUser = Depends(get_context), db: Session = Depends(get_db)):
    memberships = db.scalars(select(Membership).where(Membership.user_id == ctx.user.id)).all()
    organisations = []
    for membership in memberships:
        org = db.get(Organisation, membership.organisation_id)
        if org:
            organisations.append(org_out(org, membership.role))
    return {
        "user": user_brief(ctx.user),
        "organisations": organisations,
        "active_organisation_id": ctx.org_id,
        "role": ctx.role,
        "role_label": ROLE_LABELS.get(ctx.role, ctx.role),
        "permissions": sorted(ctx.permissions),
    }


@router.patch("/profile")
def update_profile(payload: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.title is not None:
        user.title = payload.title
    if payload.avatar_color is not None:
        user.avatar_color = payload.avatar_color
    if payload.preferences is not None:
        prefs = dict(user.preferences or {})
        prefs.update(payload.preferences)
        user.preferences = prefs
    db.commit()
    db.refresh(user)
    return user_brief(user) | {"preferences": user.preferences}


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect.")
    user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return {"message": "Password updated."}


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.scalars(select(User).where(User.email == payload.email.lower())).first()
    response = {
        "message": "If an account exists for that email, a reset link has been generated.",
    }
    if user:
        token = create_token(user.id, "reset", settings.RESET_TOKEN_EXPIRE_MINUTES)
        # In this prototype no email provider is configured. The token is returned
        # only outside production so the reset flow can be demonstrated end to end.
        if settings.ENV != "production":
            response["reset_token"] = token
            response["expires_in_minutes"] = settings.RESET_TOKEN_EXPIRE_MINUTES
    return response


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    data = decode_token(payload.token)
    if not data or data.get("type") != "reset":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This reset link is invalid or has expired.")
    user = db.get(User, data.get("sub"))
    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This reset link is invalid or has expired.")
    if len(payload.password) < 8 or not any(c.isdigit() for c in payload.password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Password must be 8+ characters and contain a number.")
    user.hashed_password = hash_password(payload.password)
    db.commit()
    return {"message": "Password reset. You can now sign in."}


@router.post("/logout", status_code=204)
def logout():
    return None


@router.get("/permissions")
def permissions(ctx: CurrentUser = Depends(get_context)):
    return {
        "role": ctx.role,
        "role_label": ROLE_LABELS.get(ctx.role, ctx.role),
        "permissions": sorted(ctx.permissions),
        "matrix": {
            role: sorted(perms) for role, perms in ROLE_PERMISSIONS.items()
        },
        "labels": ROLE_LABELS,
    }


@router.get("/demo-accounts")
def demo_accounts(db: Session = Depends(get_db)):
    """Only exposed when the seeded demo workspace exists."""
    demo = db.scalars(select(Organisation).where(Organisation.is_demo.is_(True))).first()
    if not demo:
        return {"accounts": []}
    users = db.scalars(
        select(User).where(User.email.like("%@novatech.demo"))
    ).all()
    accounts = []
    for user in users:
        membership = db.scalars(
            select(Membership).where(
                Membership.user_id == user.id, Membership.organisation_id == demo.id
            )
        ).first()
        if membership:
            accounts.append({
                "email": user.email, "full_name": user.full_name,
                "role": membership.role, "role_label": ROLE_LABELS.get(membership.role, membership.role),
            })
    accounts.sort(key=lambda a: ["admin", "reviewer", "approver", "content_creator"].index(a["role"]))
    return {"accounts": accounts, "password_hint": "BrandProof123!"}
