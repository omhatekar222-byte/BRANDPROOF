from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_context
from app.db.session import get_db
from app.models import Notification
from app.routers.common import clamp_page, paginate
from app.schemas import NotificationRead
from app.services.serializers import notification_out

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _visible(db: Session, ctx: CurrentUser):
    return [
        Notification.organisation_id == ctx.org_id,
        or_(Notification.user_id.is_(None), Notification.user_id == ctx.user.id),
    ]


@router.get("")
def list_notifications(
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
    unread_only: bool = False,
    page: int = 1, page_size: int = 30,
):
    page, page_size = clamp_page(page, page_size)
    filters = _visible(db, ctx)
    if unread_only:
        filters.append(Notification.is_read.is_(False))
    total = db.scalar(select(func.count()).select_from(Notification).where(*filters)) or 0
    rows = db.scalars(
        select(Notification).where(*filters).order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return paginate([notification_out(n) for n in rows], total, page, page_size)


@router.get("/unread-count")
def unread_count(ctx: CurrentUser = Depends(get_context), db: Session = Depends(get_db)):
    filters = _visible(db, ctx) + [Notification.is_read.is_(False)]
    count = db.scalar(select(func.count()).select_from(Notification).where(*filters)) or 0
    return {"unread_count": count}


@router.post("/mark-read")
def mark_read(
    payload: NotificationRead,
    ctx: CurrentUser = Depends(get_context),
    db: Session = Depends(get_db),
):
    filters = _visible(db, ctx) + [Notification.is_read.is_(False)]
    if payload.all:
        rows = db.scalars(select(Notification).where(*filters)).all()
    elif payload.ids:
        rows = db.scalars(
            select(Notification).where(*filters, Notification.id.in_(payload.ids))
        ).all()
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Provide notification ids or set all=true.")
    for row in rows:
        row.is_read = True
    db.commit()
    return {"marked_read": len(rows)}
