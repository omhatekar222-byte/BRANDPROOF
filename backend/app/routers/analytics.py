from collections import Counter
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_context
from app.db.session import get_db
from app.models import (
    ApprovedClaim, ApprovedFact, BrandGuideline, ChangeImpact, ContentSubmission, ExtractedClaim,
    GuidelineProposal, KnowledgeDocument, RecurringIssueGroup, ReviewFinding,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def _days(n: int) -> datetime:
    return datetime.utcnow() - timedelta(days=n)


@router.get("/health")
def brand_health(ctx: CurrentUser = Depends(get_context), db: Session = Depends(get_db)):
    """Transparent brand-health categories from measurable records only.

    No AI-generated score: each category is a simple, published formula over
    stored claims, findings, facts and feedback. The overall score is the
    unweighted mean of the five categories. The measurement period is the
    last 90 days.
    """
    org_id = ctx.org_id
    since = datetime.utcnow() - timedelta(days=90)
    claims = [c for c in db.scalars(select(ExtractedClaim).where(ExtractedClaim.organisation_id == org_id)).all()
              if c.created_at and c.created_at >= since]
    findings = [f for f in db.scalars(select(ReviewFinding).where(ReviewFinding.organisation_id == org_id)).all()
                if f.created_at and f.created_at >= since]
    facts = db.scalars(select(ApprovedFact).where(ApprovedFact.organisation_id == org_id)).all()
    groups = db.scalars(select(RecurringIssueGroup).where(RecurringIssueGroup.organisation_id == org_id)).all()
    today = date.today()

    supported = len([c for c in claims if c.status == "supported"])
    claim_accuracy = supported / len(claims) if claims else None
    resolved = len([f for f in findings if f.status == "resolved"])
    compliance = resolved / len(findings) if findings else None
    repeated_total = len(groups)
    recurring = 1.0 - min(repeated_total / 10.0, 1.0)
    overdue = [f for f in facts if f.status == "approved" and f.review_date and f.review_date < today]
    outdated = 1.0 - (len(overdue) / max(len(facts), 1))
    resolution = resolved / len(findings) if findings else None

    categories = [
        {"key": "claim_accuracy", "label": "Claim accuracy",
         "value": round(claim_accuracy, 3) if claim_accuracy is not None else None,
         "detail": f"{supported} of {len(claims)} claims supported in the last 90 days" if claims else "No claims analysed in the period",
         "formula": "supported claims / all extracted claims"},
        {"key": "guideline_compliance", "label": "Guideline compliance",
         "value": round(compliance, 3) if compliance is not None else None,
         "detail": f"{resolved} of {len(findings)} findings resolved in the last 90 days" if findings else "No findings in the period",
         "formula": "resolved findings / all findings"},
        {"key": "recurring_issue_frequency", "label": "Recurring issue frequency",
         "value": round(recurring, 3),
         "detail": f"{repeated_total} recurring issue groups active",
         "formula": "1 − (active recurring groups / 10, capped at 0)"},
        {"key": "outdated_information", "label": "Outdated information",
         "value": round(outdated, 3),
         "detail": f"{len(overdue)} of {len(facts)} approved facts past their review date",
         "formula": "1 − (overdue approved facts / all approved facts)"},
        {"key": "review_resolution", "label": "Review resolution",
         "value": round(resolution, 3) if resolution is not None else None,
         "detail": f"{resolved} of {len(findings)} findings resolved in the last 90 days" if findings else "No findings in the period",
         "formula": "resolved findings / all findings"},
    ]
    scored = [c["value"] for c in categories if c["value"] is not None]
    overall = round(sum(scored) / len(scored), 3) if scored else None
    return {
        "overall": overall,
        "overall_label": "Brand health (mean of available categories)",
        "period": "Last 90 days",
        "categories": categories,
        "note": (
            "Derived from measurable application records only. No AI-generated score. "
            "Internal management indicator — not a certified compliance score."
        ),
    }


@router.get("/network")
def knowledge_network(ctx: CurrentUser = Depends(get_context), db: Session = Depends(get_db)):
    """Brand Knowledge Network: nodes and edges from real database relationships."""
    org_id = ctx.org_id
    nodes: list[dict] = []
    edges: list[dict] = []

    docs = db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.organisation_id == org_id)).all()
    facts = db.scalars(select(ApprovedFact).where(ApprovedFact.organisation_id == org_id)).all()
    guidelines = db.scalars(select(BrandGuideline).where(BrandGuideline.organisation_id == org_id)).all()
    claims_reg = db.scalars(select(ApprovedClaim).where(ApprovedClaim.organisation_id == org_id)).all()
    submissions = db.scalars(select(ContentSubmission).where(ContentSubmission.organisation_id == org_id)).all()
    findings = db.scalars(select(ReviewFinding).where(ReviewFinding.organisation_id == org_id)).all()
    feedback = db.scalars(select(__import__("app.models", fromlist=["ReviewerFeedback"]).ReviewerFeedback)
                          .where(__import__("app.models", fromlist=["ReviewerFeedback"]).ReviewerFeedback.organisation_id == org_id)).all()
    groups = db.scalars(select(RecurringIssueGroup).where(RecurringIssueGroup.organisation_id == org_id)).all()

    for d in docs:
        nodes.append({"id": f"doc:{d.id}", "kind": "document", "label": d.title[:42], "status": d.status})
    for f in facts:
        nodes.append({"id": f"fact:{f.id}", "kind": "fact", "label": f"{f.key} = {f.value}", "status": f.status})
        if f.document_id:
            edges.append({"from": f"fact:{f.id}", "to": f"doc:{f.document_id}", "kind": "sourced_from"})
    for g in guidelines:
        nodes.append({"id": f"guideline:{g.id}", "kind": "guideline", "label": g.title[:42], "status": g.status})
    for c in claims_reg:
        nodes.append({"id": f"regclaim:{c.id}", "kind": "approved_claim", "label": c.claim_text[:42], "status": c.status})
        if c.evidence_document_id:
            edges.append({"from": f"regclaim:{c.id}", "to": f"doc:{c.evidence_document_id}", "kind": "evidenced_by"})
    for s in submissions:
        nodes.append({"id": f"content:{s.id}", "kind": "content", "label": s.title[:42], "status": s.status})
    for f in findings:
        nodes.append({"id": f"finding:{f.id}", "kind": "finding", "label": f.title[:42], "status": f.status})
        edges.append({"from": f"content:{f.submission_id}", "to": f"finding:{f.id}", "kind": "flagged_in"})
        if f.source_document_id:
            edges.append({"from": f"finding:{f.id}", "to": f"doc:{f.source_document_id}", "kind": "checked_against"})
        if f.guideline_id:
            edges.append({"from": f"finding:{f.id}", "to": f"guideline:{f.guideline_id}", "kind": "governed_by"})
    for g in groups:
        nodes.append({"id": f"group:{g.id}", "kind": "recurring_issue", "label": g.title[:42], "status": g.status})
        for sid in (g.affected_submission_ids or [])[:6]:
            edges.append({"from": f"group:{g.id}", "to": f"content:{sid}", "kind": "recurs_in"})
    for fb in feedback:
        if fb.finding_id and fb.guideline_id:
            edges.append({"from": f"finding:{fb.finding_id}", "to": f"guideline:{fb.guideline_id}", "kind": "reviewed_under"})

    return {
        "nodes": nodes[:160],
        "edges": edges[:300],
        "counts": {
            "nodes": len(nodes), "edges": len(edges),
            "documents": len(docs), "facts": len(facts), "guidelines": len(guidelines),
            "content": len(submissions), "findings": len(findings), "recurring_groups": len(groups),
        },
        "note": "Every node and edge originates from a real database relationship. No connections are invented.",
    }


@router.get("/dashboard")
def dashboard(ctx: CurrentUser = Depends(get_context), db: Session = Depends(get_db)):
    org_id = ctx.org_id
    submissions = db.scalars(select(ContentSubmission).where(ContentSubmission.organisation_id == org_id)).all()
    claims = db.scalars(select(ExtractedClaim).where(ExtractedClaim.organisation_id == org_id)).all()
    findings = db.scalars(select(ReviewFinding).where(ReviewFinding.organisation_id == org_id)).all()
    by_status = Counter(s.status for s in submissions)
    claim_counts = Counter(c.status for c in claims)
    finding_by_category = Counter(f.category for f in findings)
    finding_by_severity = Counter(f.severity for f in findings)

    # Activity per day (submissions + findings) over last 14 days
    activity = []
    for offset in range(13, -1, -1):
        day = (datetime.utcnow() - timedelta(days=offset)).date()
        activity.append({
            "date": day.isoformat(),
            "submissions": len([s for s in submissions if s.created_at and s.created_at.date() == day]),
            "findings": len([f for f in findings if f.created_at and f.created_at.date() == day]),
            "claims": len([c for c in claims if c.created_at and c.created_at.date() == day]),
        })

    # Brand consistency trend: supported ratio per week
    trend = []
    for weeks_back in range(7, -1, -1):
        start = _days((weeks_back + 1) * 7)
        claim_slice = [c for c in claims if c.created_at and c.created_at >= start]
        supported = len([c for c in claim_slice if c.status == "supported"])
        total = len(claim_slice)
        trend.append({
            "week": f"W-{weeks_back}" if weeks_back else "This week",
            "claims": total,
            "supported": supported,
            "supported_ratio": round(supported / total, 3) if total else None,
        })

    today = date.today()
    expiring_claims = sorted(
        [c for c in db.scalars(select(ApprovedClaim).where(ApprovedClaim.organisation_id == org_id)).all()
         if c.status == "approved" and c.expiry_date and c.expiry_date <= today + timedelta(days=45)],
        key=lambda c: c.expiry_date,
    )
    overdue_docs = sorted(
        [d for d in db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.organisation_id == org_id)).all()
         if d.review_date and d.review_date < today],
        key=lambda d: d.review_date,
    )
    stale_facts = sorted(
        [f for f in db.scalars(select(ApprovedFact).where(ApprovedFact.organisation_id == org_id)).all()
         if f.status == "approved" and f.review_date and f.review_date < today],
        key=lambda f: f.review_date,
    )
    check_date = _days(30)
    all_org_submissions = submissions
    consistency = {}
    for s in all_org_submissions:
        if s.created_at and s.created_at >= check_date:
            for f in findings:
                if f.submission_id == s.id:
                    key = (s.content_type, f.category)
                    cell = consistency.setdefault(key, {"content_type": s.content_type, "category": f.category, "count": 0, "campaigns": set(), "teams": 0})
                    cell["count"] += 1
                    if s.campaign:
                        cell["campaigns"].add(s.campaign)

    groups = db.scalars(select(RecurringIssueGroup).where(RecurringIssueGroup.organisation_id == org_id)).all()
    heatmap = []
    for (ctype, category), cell in sorted(consistency.items(), key=lambda kv: kv[1]["count"], reverse=True)[:40]:
        heatmap.append({
            "content_type": ctype, "category": category, "count": cell["count"],
            "campaigns": sorted(cell["campaigns"]),
        })
    pending_proposals = db.scalars(
        select(GuidelineProposal).where(
            GuidelineProposal.organisation_id == org_id, GuidelineProposal.status == "pending"
        )
    ).all()
    impacts = db.scalars(select(ChangeImpact).where(ChangeImpact.organisation_id == org_id)).all()
    recent = sorted(submissions, key=lambda s: s.updated_at or s.created_at, reverse=True)[:10]
    audit_recent = db.execute(
        select(func.count(func.distinct(func.date(ContentSubmission.created_at))))
        .where(ContentSubmission.organisation_id == org_id)
    ).scalar() or 0

    return {
        "totals": {
            "submissions": len(submissions),
            "pending_reviews": by_status.get("submitted", 0) + by_status.get("under_review", 0),
            "approved": by_status.get("approved", 0),
            "rejected": by_status.get("rejected", 0),
            "changes_requested": by_status.get("changes_requested", 0),
            "drafts": by_status.get("draft", 0),
            "claims_total": len(claims),
            "claims_supported": claim_counts.get("supported", 0),
            "claims_contradicted": claim_counts.get("contradicted", 0),
            "claims_unsupported": claim_counts.get("unsupported", 0),
            "claims_inconclusive": claim_counts.get("inconclusive", 0),
            "findings_open": len([f for f in findings if f.status in {"open", "accepted", "modified"}]),
            "findings_resolved": len([f for f in findings if f.status == "resolved"]),
            "proposals_pending": len(pending_proposals),
            "impacts_open": len([i for i in impacts if i.status != "resolved"]),
            "recurring_groups": len(groups),
            "active_days": int(audit_recent),
        },
        "by_status": dict(by_status),
        "by_content_type": dict(Counter(s.content_type for s in submissions)),
        "by_campaign": dict(Counter(s.campaign for s in submissions if s.campaign)),
        "claim_counts": dict(claim_counts),
        "finding_by_category": dict(finding_by_category),
        "finding_by_severity": dict(finding_by_severity),
        "activity_14d": activity,
        "consistency_trend": trend,
        "drift_radar": {
            "top_categories": [
                {"category": k, "count": v} for k, v in finding_by_category.most_common(8)
            ],
            "top_groups": [
                {"id": g.id, "title": g.title, "count": g.finding_count, "root_cause": g.possible_root_cause}
                for g in sorted(groups, key=lambda g: g.finding_count, reverse=True)[:6]
            ],
        },
        "claim_expiry_radar": [
            {
                "id": c.id, "claim_text": c.claim_text, "expiry_date": c.expiry_date.isoformat(),
                "days_to_expiry": (c.expiry_date - today).days, "expired": c.expiry_date < today,
            }
            for c in expiring_claims[:12]
        ],
        "expiry_radar": {
            "claims": [
                {
                    "id": c.id, "claim_text": c.claim_text, "expiry_date": c.expiry_date.isoformat(),
                    "days_to_expiry": (c.expiry_date - today).days, "expired": c.expiry_date < today,
                }
                for c in expiring_claims[:12]
            ],
            "documents_overdue": [
                {"id": d.id, "title": d.title, "review_date": d.review_date.isoformat()}
                for d in overdue_docs[:10]
            ],
            "facts_overdue": [
                {"id": f.id, "key": f.key, "value": f.value, "review_date": f.review_date.isoformat()}
                for f in stale_facts[:10]
            ],
        },
        "guideline_gap_detector": [
            {
                "id": g.id, "title": g.title, "category": g.category,
                "finding_count": g.finding_count, "root_cause": g.possible_root_cause,
                "root_cause_note": g.root_cause_note,
                "suggested_improvement": g.suggested_improvement,
                "examples": (g.example_corrections or [])[:2],
                "status": g.status,
                "affected_count": len(g.affected_submission_ids or []),
            }
            for g in sorted(groups, key=lambda g: g.finding_count, reverse=True)[:10]
        ],
        "consistency_heatmap": heatmap,
        "recent_activity": [
            {
                "id": s.id, "title": s.title, "status": s.status,
                "content_type": s.content_type, "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in recent
        ],
        "pending_actions": [
            *[
                {"type": "review", "label": f"Review \"{s.title}\"", "link": f"/content/{s.id}"}
                for s in submissions if s.status in {"submitted", "under_review"}
            ][:6],
            *[
                {"type": "proposal", "label": f"Decide proposal: {p.title}", "link": "/guideline-intelligence"}
                for p in pending_proposals[:4]
            ],
            *[
                {"type": "impact", "label": f"Recheck: {i.entity_label} ({i.previous_value} → {i.updated_value})", "link": "/change-impact"}
                for i in impacts if i.status != "resolved"
            ][:4],
            *[
                {"type": "expiry", "label": f"Renew claim: {c.claim_text[:60]}", "link": "/brand-knowledge-vault"}
                for c in expiring_claims if c.expiry_date < today
            ][:4],
        ],
    }
