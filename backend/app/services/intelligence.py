"""Guideline Intelligence.

This groups structured reviewer feedback by similarity and category and derives
candidate root causes with transparent, rule-based reasoning. It is not model
training, and it never edits a guideline by itself.
"""
import re
from collections import Counter
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    BrandGuideline, ContentSubmission, GuidelineProposal, RecurringIssueGroup, ReviewerFeedback,
)

VAGUE_TERMS = ["appropriate", "reasonable", "as needed", "generally", "where possible", "avoid excessive", "good", "proper"]

ROOT_CAUSE_LABELS = {
    "unclear_guideline": "Unclear guideline",
    "missing_information": "Missing information",
    "outdated_information": "Outdated information",
    "conflicting_guidelines": "Conflicting guidelines",
    "repeated_individual_mistake": "Repeated individual mistakes",
    "context_specific_exception": "Context-specific exception",
}

SUGGESTIONS = {
    "tone": (
        "Clarify which promotional expressions are permitted. List banned absolute terms "
        "(for example \"revolutionary\", \"unbeatable\", \"guaranteed\") and require measurable, "
        "approved evidence for any comparative claim."
    ),
    "product_accuracy": (
        "Make the product specification table the single source of truth, and require creators to "
        "link claims to an approved specification record before publishing."
    ),
    "unsupported_claim": (
        "State explicitly which claims require approved evidence, where that evidence lives, and "
        "what a creator must do when evidence is missing."
    ),
    "restricted_language": (
        "Publish an unambiguous permitted/blocked wording list and add examples of acceptable "
        "alternatives for each blocked phrase."
    ),
    "terminology": (
        "Add a terminology table with the approved term, rejected variants and a one-line rationale "
        "so writers do not have to infer the rule."
    ),
    "missing_statement": (
        "List required statements by content type and make them part of the submission checklist."
    ),
    "outdated_information": (
        "Set review dates for every specification and assign an owner responsible for refreshing them."
    ),
    "accessibility": (
        "Add a short accessibility checklist (alt text, capitals, readable contrast) to the creative brief."
    ),
    "brand_colour": (
        "Distribute the approved colour palette with hex values and examples of correct usage."
    ),
}


def _normalise_title(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "untitled").strip().lower())


def _signature(category: str, title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", _normalise_title(title)).strip("-")[:80]
    return f"{category or 'general'}::{slug}"


def _root_cause(feedback: list[ReviewerFeedback], guideline: BrandGuideline | None, submissions: set[str]) -> tuple[str, str]:
    if not guideline:
        return "missing_information", "Reviewers corrected this issue repeatedly but no approved guideline is linked to it."
    text = (guideline.content or "").lower()
    if any(term in text for term in VAGUE_TERMS):
        return "unclear_guideline", (
            f"The linked guideline (\"{guideline.title}\") uses subjective wording "
            f"({', '.join(t for t in VAGUE_TERMS if t in text)}), so reviewers interpret it differently."
        )
    if guideline.review_date and guideline.review_date.isoformat() < __import__("datetime").date.today().isoformat():
        return "outdated_information", f"The linked guideline (\"{guideline.title}\") is past its review date."
    if len(text) < 220:
        return "unclear_guideline", "The linked guideline is brief and does not give worked examples."
    if len(submissions) >= 3:
        return "unclear_guideline", (
            f"The same correction appears in {len(submissions)} different submissions, which points to the "
            "guideline rather than one individual."
        )
    return "repeated_individual_mistake", "Corrections are concentrated in a small number of submissions."


def analyse_feedback(db: Session, org_id: str) -> list[RecurringIssueGroup]:
    feedback = db.scalars(
        select(ReviewerFeedback).where(ReviewerFeedback.organisation_id == org_id)
    ).all()
    if not feedback:
        return []

    # Similarity grouping: merge near-identical issue titles within a category.
    buckets: list[dict] = []
    for item in feedback:
        title = _normalise_title(item.issue_title)
        placed = False
        for bucket in buckets:
            if bucket["category"] != item.issue_category:
                continue
            if SequenceMatcher(None, bucket["title"], title).ratio() >= 0.82:
                bucket["items"].append(item)
                placed = True
                break
        if not placed:
            buckets.append({"category": item.issue_category, "title": title, "items": [item]})

    existing = db.scalars(
        select(RecurringIssueGroup).where(RecurringIssueGroup.organisation_id == org_id)
    ).all()
    by_signature = {g.signature: g for g in existing}
    seen_signatures = set()

    for bucket in buckets:
        items: list[ReviewerFeedback] = bucket["items"]
        display_title = Counter([i.issue_title for i in items]).most_common(1)[0][0]
        signature = _signature(bucket["category"], bucket["title"])
        seen_signatures.add(signature)

        guideline_ids = [i.guideline_id for i in items if i.guideline_id]
        guideline = db.get(BrandGuideline, Counter(guideline_ids).most_common(1)[0][0]) if guideline_ids else None
        if guideline is None:
            candidates = db.scalars(
                select(BrandGuideline).where(
                    BrandGuideline.organisation_id == org_id, BrandGuideline.status == "approved"
                )
            ).all()
            guideline = next(
                (g for g in candidates if bucket["category"] in (g.category + " " + g.title).lower()), None
            )

        submission_ids = {i.submission_id for i in items if i.submission_id}
        root_cause, note = _root_cause(items, guideline, submission_ids)
        related_count = len({g.id for g in db.scalars(
            select(BrandGuideline).where(
                BrandGuideline.organisation_id == org_id,
                BrandGuideline.category == (guideline.category if guideline else ""),
                BrandGuideline.status == "approved",
            )
        ).all()})
        if related_count > 1:
            root_cause, note = "conflicting_guidelines", (
                f"{related_count} approved guidelines cover the same category; reviewers may be applying different ones."
            )

        submissions = db.scalars(
            select(ContentSubmission).where(ContentSubmission.id.in_(submission_ids))
        ).all() if submission_ids else []
        examples = []
        for item in items[:4]:
            submission = next((s for s in submissions if s.id == item.submission_id), None)
            examples.append({
                "submission_id": item.submission_id,
                "submission_title": submission.title if submission else "Untitled content",
                "reviewer_decision": item.decision,
                "original": item.original_content[:240],
                "suggestion": item.original_suggestion[:240],
                "final": item.final_correction[:240],
                "reason": item.feedback_reason[:240],
                "date": item.created_at.isoformat(),
            })

        group = by_signature.get(signature)
        if not group:
            group = RecurringIssueGroup(organisation_id=org_id, signature=signature, title=display_title)
            db.add(group)
            by_signature[signature] = group
        group.title = display_title
        group.category = bucket["category"]
        group.possible_root_cause = root_cause
        group.root_cause_note = note
        group.suggested_improvement = SUGGESTIONS.get(bucket["category"], SUGGESTIONS["unsupported_claim"])
        group.finding_count = len(items)
        group.affected_submission_ids = sorted(submission_ids)
        group.example_corrections = examples
        group.root_cause_note += f" Guideline reference: {guideline.title}." if guideline else ""
        if group.status not in {"proposal_created", "dismissed"} and len(items) >= 2:
            group.status = "open"
        if group.first_seen is None:
            group.first_seen = min(i.created_at for i in items)
        group.last_seen = max(i.created_at for i in items)

    db.flush()
    return [g for g in db.scalars(
        select(RecurringIssueGroup).where(RecurringIssueGroup.organisation_id == org_id)
    ).all() if g.signature in seen_signatures]


def create_proposal(db: Session, org_id: str, group: RecurringIssueGroup, actor_id: str | None) -> GuidelineProposal:
    candidates = db.scalars(
        select(BrandGuideline).where(
            BrandGuideline.organisation_id == org_id, BrandGuideline.status == "approved"
        )
    ).all()
    guideline = next(
        (g for g in candidates if group.category in (g.category + " " + g.title).lower()), None
    ) or (candidates[0] if candidates else None)

    proposed = (
        f"{group.suggested_improvement}\n\n"
        f"Rule: Wording in this category must be specific and evidence-based. "
        f"The following corrections were reviewed {group.finding_count} times across "
        f"{len(group.affected_submission_ids or [])} pieces of content. "
        f"Creators must not use absolute claims unless an approved source is attached in BrandProof."
    )
    proposal = GuidelineProposal(
        organisation_id=org_id,
        group_id=group.id,
        guideline_id=guideline.id if guideline else None,
        title=f"Clarify guideline: {group.title}",
        current_rule=guideline.content if guideline else "No approved rule exists for this issue category.",
        proposed_rule=proposed,
        rationale=(
            f"{group.finding_count} structured reviewer corrections support this change. "
            f"Candidate root cause: {ROOT_CAUSE_LABELS.get(group.possible_root_cause, group.possible_root_cause)}. "
            "This is a proposal derived from reviewer feedback; it is not automatically applied."
        ),
        root_cause=group.possible_root_cause,
        evidence=group.example_corrections or [],
        created_by=actor_id,
        status="pending",
    )
    db.add(proposal)
    group.status = "proposal_created"
    db.flush()
    return proposal
