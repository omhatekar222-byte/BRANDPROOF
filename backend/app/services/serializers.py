from datetime import date, datetime


def dt(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def user_brief(user) -> dict | None:
    if not user:
        return None
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "title": user.title,
        "avatar_color": user.avatar_color,
    }


def member_out(membership) -> dict:
    return {
        "id": membership.id,
        "user_id": membership.user_id,
        "role": membership.role,
        "title": membership.user.title,
        **{k: v for k, v in user_brief(membership.user).items() if k != "title"},
        "joined_at": dt(membership.created_at),
        "is_active": membership.user.is_active,
    }


def org_out(org, role: str | None = None) -> dict:
    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "industry": org.industry,
        "brand_colors": org.brand_colors or [],
        "is_demo": org.is_demo,
        "settings": org.settings or {},
        "role": role,
        "created_at": dt(org.created_at),
    }


def document_out(doc, include_text: bool = False) -> dict:
    data = {
        "id": doc.id,
        "title": doc.title,
        "doc_type": doc.doc_type,
        "category": doc.category,
        "status": doc.status,
        "version": doc.version,
        "owner": user_brief(getattr(doc, "owner", None)),
        "approved_by": doc.approved_by,
        "effective_date": dt(doc.effective_date),
        "review_date": dt(doc.review_date),
        "file_name": doc.file_name,
        "mime_type": doc.mime_type,
        "tags": doc.tags or [],
        "page_count": len(doc.page_map or []),
        "char_count": len(doc.extracted_text or ""),
        "created_at": dt(doc.created_at),
        "updated_at": dt(doc.updated_at),
    }
    if include_text:
        data["extracted_text"] = doc.extracted_text
        data["page_map"] = doc.page_map or []
    return data


def fact_out(fact) -> dict:
    return {
        "id": fact.id,
        "key": fact.key,
        "value": fact.value,
        "product": fact.product,
        "category": fact.category,
        "status": fact.status,
        "document_id": fact.document_id,
        "document_title": fact.document.title if fact.document else None,
        "source_locator": fact.source_locator,
        "effective_date": dt(fact.effective_date),
        "review_date": dt(fact.review_date),
        "approved_by": fact.approved_by,
        "created_at": dt(fact.created_at),
        "updated_at": dt(fact.updated_at),
    }


def approved_claim_out(claim) -> dict:
    return {
        "id": claim.id,
        "claim_text": claim.claim_text,
        "category": claim.category,
        "status": claim.status,
        "evidence_document_id": claim.evidence_document_id,
        "review_date": dt(claim.review_date),
        "expiry_date": dt(claim.expiry_date),
        "created_at": dt(claim.created_at),
    }


def guideline_out(g) -> dict:
    return {
        "id": g.id,
        "title": g.title,
        "category": g.category,
        "content": g.content,
        "summary": g.summary,
        "status": g.status,
        "version": g.version,
        "owner": user_brief(getattr(g, "owner", None)),
        "effective_date": dt(g.effective_date),
        "review_date": dt(g.review_date),
        "created_at": dt(g.created_at),
        "updated_at": dt(g.updated_at),
    }


def asset_out(a) -> dict:
    from pathlib import Path
    file_url = f"/uploads/{Path(a.file_path).name}" if a.file_path else None
    return {
        "id": a.id,
        "name": a.name,
        "asset_type": a.asset_type,
        "file_path": a.file_path,
        "file_url": file_url,
        "color_hex": a.color_hex,
        "is_approved": a.is_approved,
        "notes": a.notes,
        "created_at": dt(a.created_at),
    }


def submission_out(s, include_text: bool = False) -> dict:
    data = {
        "id": s.id,
        "title": s.title,
        "content_type": s.content_type,
        "campaign": s.campaign,
        "product": s.product,
        "source_type": s.source_type,
        "file_name": s.file_name,
        "status": s.status,
        "current_version": s.current_version,
        "submitted_by": user_brief(getattr(s, "submitter", None)),
        "analysis_mode": s.analysis_mode,
        "analysis_error": s.analysis_error,
        "proof_score": s.proof_score or {},
        "approved_by": s.approved_by,
        "approved_at": dt(s.approved_at),
        "created_at": dt(s.created_at),
        "updated_at": dt(s.updated_at),
        "word_count": len((s.raw_text or "").split()),
        "excerpt": (s.raw_text or "")[:280],
    }
    if include_text:
        data["raw_text"] = s.raw_text
    return data


def extracted_claim_out(c) -> dict:
    evidence = c.evidence_snapshot or {}
    return {
        "id": c.id,
        "submission_id": c.submission_id,
        "claim_text": c.claim_text,
        "normalized_key": c.normalized_key,
        "category": c.category,
        "risk_level": c.risk_level,
        "status": c.status,
        "confidence": round(c.confidence, 2),
        "explanation": c.explanation,
        "suggested_action": c.suggested_action,
        "correction": c.correction,
        "evidence_document_id": c.evidence_document_id,
        "evidence_source_label": c.evidence_source_label,
        "evidence_passage": c.evidence_passage,
        "evidence_locator": c.evidence_locator,
        "evidence": evidence,
        "extractor": c.extractor,
        "created_at": dt(c.created_at),
    }


def finding_out(f) -> dict:
    return {
        "id": f.id,
        "submission_id": f.submission_id,
        "claim_id": f.claim_id,
        "title": f.title,
        "category": f.category,
        "severity": f.severity,
        "original_text": f.original_text,
        "explanation": f.explanation,
        "guideline_ref": f.guideline_ref,
        "guideline_id": f.guideline_id,
        "source_document_id": f.source_document_id,
        "source_passage": f.source_passage,
        "source_locator": f.source_locator,
        "suggested_correction": f.suggested_correction,
        "confidence": round(f.confidence, 2),
        "detector": f.detector,
        "status": f.status,
        "resolved_at": dt(f.resolved_at),
        "created_at": dt(f.created_at),
    }


def feedback_out(f) -> dict:
    return {
        "id": f.id,
        "finding_id": f.finding_id,
        "submission_id": f.submission_id,
        "reviewer": user_brief(getattr(f, "reviewer", None)),
        "original_content": f.original_content,
        "issue_category": f.issue_category,
        "issue_title": f.issue_title,
        "original_suggestion": f.original_suggestion,
        "final_correction": f.final_correction,
        "decision": f.decision,
        "feedback_reason": f.feedback_reason,
        "guideline_id": f.guideline_id,
        "created_at": dt(f.created_at),
    }


def group_out(g) -> dict:
    return {
        "id": g.id,
        "signature": g.signature,
        "title": g.title,
        "category": g.category,
        "possible_root_cause": g.possible_root_cause,
        "root_cause_note": g.root_cause_note,
        "suggested_improvement": g.suggested_improvement,
        "finding_count": g.finding_count,
        "affected_submission_ids": g.affected_submission_ids or [],
        "example_corrections": g.example_corrections or [],
        "status": g.status,
        "first_seen": dt(g.first_seen),
        "last_seen": dt(g.last_seen),
    }


def proposal_out(p) -> dict:
    return {
        "id": p.id,
        "group_id": p.group_id,
        "guideline_id": p.guideline_id,
        "title": p.title,
        "current_rule": p.current_rule,
        "proposed_rule": p.proposed_rule,
        "rationale": p.rationale,
        "root_cause": p.root_cause,
        "evidence": p.evidence or [],
        "status": p.status,
        "created_by": p.created_by,
        "decided_by": p.decided_by,
        "decided_at": dt(p.decided_at),
        "created_at": dt(p.created_at),
    }


def impact_out(i) -> dict:
    return {
        "id": i.id,
        "change_type": i.change_type,
        "entity_label": i.entity_label,
        "previous_value": i.previous_value,
        "updated_value": i.updated_value,
        "affected_submission_id": i.affected_submission_id,
        "reason": i.reason,
        "status": i.status,
        "resolved_at": dt(i.resolved_at),
        "created_at": dt(i.created_at),
    }


def audit_out(e) -> dict:
    return {
        "id": e.id,
        "action": e.action,
        "entity_type": e.entity_type,
        "entity_id": e.entity_id,
        "entity_label": e.entity_label,
        "previous_value": e.previous_value,
        "updated_value": e.updated_value,
        "content_version": e.content_version,
        "guideline_version": e.guideline_version,
        "decision": e.decision,
        "meta": e.meta or {},
        "actor": user_brief(getattr(e, "actor", None)),
        "created_at": dt(e.created_at),
    }


def notification_out(n) -> dict:
    return {
        "id": n.id,
        "title": n.title,
        "message": n.message,
        "type": n.type,
        "link": n.link,
        "is_read": n.is_read,
        "created_at": dt(n.created_at),
    }


def comment_out(c) -> dict:
    return {
        "id": c.id,
        "submission_id": c.submission_id,
        "author": user_brief(getattr(c, "author", None)),
        "body": c.body,
        "created_at": dt(c.created_at),
    }


def approval_out(a) -> dict:
    return {
        "id": a.id,
        "entity_type": a.entity_type,
        "entity_id": a.entity_id,
        "decision": a.decision,
        "notes": a.notes,
        "previous_status": a.previous_status,
        "new_status": a.new_status,
        "actor": user_brief(getattr(a, "actor", None)),
        "created_at": dt(a.created_at),
    }
