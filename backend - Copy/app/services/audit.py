from sqlalchemy.orm import Session

from app.models import AuditEvent, Notification


def record_audit(
    db: Session,
    org_id: str,
    actor_id: str | None,
    action: str,
    entity_type: str = "",
    entity_id: str = "",
    entity_label: str = "",
    previous_value: str = "",
    updated_value: str = "",
    content_version: int | None = None,
    guideline_version: int | None = None,
    decision: str = "",
    meta: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        organisation_id=org_id,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_label=entity_label[:250],
        previous_value=str(previous_value or "")[:4000],
        updated_value=str(updated_value or "")[:4000],
        content_version=content_version,
        guideline_version=guideline_version,
        decision=decision,
        meta=meta or {},
    )
    db.add(event)
    return event


def notify(
    db: Session,
    org_id: str,
    title: str,
    message: str,
    type: str = "info",
    link: str = "",
    user_id: str | None = None,
) -> Notification:
    notification = Notification(
        organisation_id=org_id, user_id=user_id, title=title, message=message, type=type, link=link
    )
    db.add(notification)
    return notification
