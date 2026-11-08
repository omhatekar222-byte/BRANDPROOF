import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChangeImpact, ContentFactUsage, ContentSubmission
from app.services.audit import notify


def _find_affected(db: Session, org_id: str, fact_id: str | None, previous_value: str, updated_value: str) -> list[ContentSubmission]:
    submissions = db.scalars(
        select(ContentSubmission).where(ContentSubmission.organisation_id == org_id)
    ).all()
    usage_ids = set()
    if fact_id:
        usage_ids = {
            u.submission_id for u in db.scalars(
                select(ContentFactUsage).where(ContentFactUsage.fact_id == fact_id)
            ).all()
        }
    prev = (previous_value or "").strip().lower()
    affected = []
    for submission in submissions:
        text = (submission.raw_text or "").lower()
        used_fact = submission.id in usage_ids
        mentions_old = bool(prev) and prev in text
        if used_fact or mentions_old:
            affected.append(submission)
    return affected


def create_impacts(
    db: Session,
    org_id: str,
    fact_id: str | None,
    previous_value: str,
    updated_value: str,
    label: str,
    actor_id: str | None,
) -> list[ChangeImpact]:
    affected = _find_affected(db, org_id, fact_id, previous_value, updated_value)
    impacts = []
    for submission in affected:
        existing = db.scalars(
            select(ChangeImpact).where(
                ChangeImpact.organisation_id == org_id,
                ChangeImpact.affected_submission_id == submission.id,
                ChangeImpact.previous_value == previous_value,
                ChangeImpact.updated_value == updated_value,
                ChangeImpact.status != "resolved",
            )
        ).first()
        if existing:
            impacts.append(existing)
            continue
        reason = (
            f"Registered content references the previous value \"{previous_value}\"."
            if previous_value.lower() in (submission.raw_text or "").lower()
            else "This content used the approved fact that has now changed."
        )
        impact = ChangeImpact(
            organisation_id=org_id,
            change_type="fact_update",
            entity_label=label,
            previous_value=previous_value,
            updated_value=updated_value,
            affected_submission_id=submission.id,
            reason=reason,
            status="open",
        )
        db.add(impact)
        impacts.append(impact)
    if impacts:
        notify(
            db, org_id,
            title="Product information changed",
            message=(
                f"\"{label}\" changed from {previous_value} to {updated_value}. "
                f"{len(impacts)} registered item(s) may need rechecking."
            ),
            type="impact",
            link="/change-impact",
        )
    db.flush()
    return impacts
