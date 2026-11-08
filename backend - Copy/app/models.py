import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def uid() -> str:
    return uuid.uuid4().hex


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.isoformat() if dt else None


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(120), default="Team member")
    avatar_color: Mapped[str] = mapped_column(String(20), default="#4f6ef7")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    memberships = relationship("Membership", back_populates="user", cascade="all, delete-orphan")


class Organisation(Base):
    __tablename__ = "organisations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    industry: Mapped[str] = mapped_column(String(120), default="Technology")
    brand_colors: Mapped[list] = mapped_column(JSON, default=list)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    memberships = relationship("Membership", back_populates="organisation", cascade="all, delete-orphan")


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "organisation_id", name="uq_membership_user_org"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(30), default="content_creator")  # admin|content_creator|reviewer|approver
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    user = relationship("User", back_populates="memberships")
    organisation = relationship("Organisation", back_populates="memberships")


class RolePermission(Base):
    __tablename__ = "role_permissions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    permission: Mapped[str] = mapped_column(String(80), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class BrandGuideline(Base):
    __tablename__ = "brand_guidelines"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(60), default="messaging")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(String(400), default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|approved|archived
    version: Mapped[int] = mapped_column(Integer, default=1)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    effective_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    review_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    versions = relationship("GuidelineVersion", back_populates="guideline", cascade="all, delete-orphan")
    owner = relationship("User", foreign_keys=[owner_id])


class GuidelineVersion(Base):
    __tablename__ = "guideline_versions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    guideline_id: Mapped[str] = mapped_column(ForeignKey("brand_guidelines.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    change_summary: Mapped[str] = mapped_column(String(400), default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    guideline = relationship("BrandGuideline", back_populates="versions")


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(50), default="guideline")  # guideline|product_spec|company_info|approved_claim|terminology|asset|warranty_pricing|restricted_language
    category: Mapped[str] = mapped_column(String(80), default="General")
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|approved|archived|outdated
    version: Mapped[int] = mapped_column(Integer, default=1)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    effective_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    review_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    page_map: Mapped[list] = mapped_column(JSON, default=list)  # [{page: 1, text: "..."}]
    tags: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan")
    facts = relationship("ApprovedFact", back_populates="document")
    owner = relationship("User", foreign_keys=[owner_id])


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")
    change_summary: Mapped[str] = mapped_column(String(400), default="")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    document = relationship("KnowledgeDocument", back_populates="versions")


class ApprovedFact(Base):
    __tablename__ = "approved_facts"
    __table_args__ = (Index("ix_fact_org_key", "organisation_id", "key"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="SET NULL"), nullable=True)
    key: Mapped[str] = mapped_column(String(160), nullable=False)  # e.g. "NovaTech X1 battery capacity"
    value: Mapped[str] = mapped_column(String(300), nullable=False)  # e.g. "5000 mAh"
    product: Mapped[str] = mapped_column(String(120), default="")
    category: Mapped[str] = mapped_column(String(60), default="product")
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|approved|retired
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    effective_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    review_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    source_locator: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    document = relationship("KnowledgeDocument", back_populates="facts")


class ApprovedClaim(Base):
    __tablename__ = "approved_claims"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(60), default="promotional")
    status: Mapped[str] = mapped_column(String(20), default="approved")  # approved|prohibited|draft
    evidence_document_id: Mapped[str | None] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="SET NULL"), nullable=True)
    review_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class BrandAsset(Base):
    __tablename__ = "brand_assets"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(40), default="logo")  # logo|colour|font|image
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    color_hex: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class ContentSubmission(Base):
    __tablename__ = "content_submissions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), default="advertisement")
    campaign: Mapped[str] = mapped_column(String(120), default="")
    product: Mapped[str] = mapped_column(String(120), default="")
    source_type: Mapped[str] = mapped_column(String(20), default="text")  # text|pdf
    raw_text: Mapped[str] = mapped_column(Text, default="")
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    submitted_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    analysis_mode: Mapped[str] = mapped_column(String(20), default="not_analyzed")  # demo|ai|not_analyzed
    analysis_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    proof_score: Mapped[dict] = mapped_column(JSON, default=dict)
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    versions = relationship("ContentVersion", back_populates="submission", cascade="all, delete-orphan")
    claims = relationship("ExtractedClaim", back_populates="submission", cascade="all, delete-orphan")
    findings = relationship("ReviewFinding", back_populates="submission", cascade="all, delete-orphan")
    submitter = relationship("User", foreign_keys=[submitted_by])


class ContentVersion(Base):
    __tablename__ = "content_versions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    submission_id: Mapped[str] = mapped_column(ForeignKey("content_submissions.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(String(300), default="")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    submission = relationship("ContentSubmission", back_populates="versions")


class ExtractedClaim(Base):
    __tablename__ = "extracted_claims"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    submission_id: Mapped[str] = mapped_column(ForeignKey("content_submissions.id", ondelete="CASCADE"), index=True)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_key: Mapped[str] = mapped_column(String(200), default="")
    category: Mapped[str] = mapped_column(String(60), default="product")
    risk_level: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(30), default="pending")  # supported|contradicted|unsupported|inconclusive|pending
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    explanation: Mapped[str] = mapped_column(Text, default="")
    suggested_action: Mapped[str] = mapped_column(String(400), default="")
    correction: Mapped[str] = mapped_column(Text, default="")
    evidence_document_id: Mapped[str | None] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="SET NULL"), nullable=True)
    evidence_source_label: Mapped[str] = mapped_column(String(250), default="")
    evidence_passage: Mapped[str] = mapped_column(Text, default="")
    evidence_locator: Mapped[str] = mapped_column(String(120), default="")
    evidence_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    extractor: Mapped[str] = mapped_column(String(20), default="demo")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    submission = relationship("ContentSubmission", back_populates="claims")


class ContentFactUsage(Base):
    __tablename__ = "content_fact_usage"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    submission_id: Mapped[str] = mapped_column(ForeignKey("content_submissions.id", ondelete="CASCADE"), index=True)
    fact_id: Mapped[str] = mapped_column(ForeignKey("approved_facts.id", ondelete="CASCADE"), index=True)
    matched_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class ReviewFinding(Base):
    __tablename__ = "review_findings"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    submission_id: Mapped[str] = mapped_column(ForeignKey("content_submissions.id", ondelete="CASCADE"), index=True)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    claim_id: Mapped[str | None] = mapped_column(ForeignKey("extracted_claims.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="medium")  # low|medium|high|critical
    original_text: Mapped[str] = mapped_column(Text, default="")
    explanation: Mapped[str] = mapped_column(Text, default="")
    guideline_ref: Mapped[str] = mapped_column(String(250), default="")
    guideline_id: Mapped[str | None] = mapped_column(ForeignKey("brand_guidelines.id", ondelete="SET NULL"), nullable=True)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="SET NULL"), nullable=True)
    source_passage: Mapped[str] = mapped_column(Text, default="")
    source_locator: Mapped[str] = mapped_column(String(120), default="")
    suggested_correction: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.6)
    detector: Mapped[str] = mapped_column(String(20), default="rule")  # rule|ai|demo
    status: Mapped[str] = mapped_column(String(25), default="open")  # open|accepted|rejected|modified|resolved
    resolved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    submission = relationship("ContentSubmission", back_populates="findings")
    resolver = relationship("User", foreign_keys=[resolved_by])


class ReviewerFeedback(Base):
    __tablename__ = "reviewer_feedback"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    finding_id: Mapped[str | None] = mapped_column(ForeignKey("review_findings.id", ondelete="SET NULL"), nullable=True)
    submission_id: Mapped[str | None] = mapped_column(ForeignKey("content_submissions.id", ondelete="SET NULL"), nullable=True)
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    original_content: Mapped[str] = mapped_column(Text, default="")
    issue_category: Mapped[str] = mapped_column(String(60), default="")
    issue_title: Mapped[str] = mapped_column(String(240), default="")
    original_suggestion: Mapped[str] = mapped_column(Text, default="")
    final_correction: Mapped[str] = mapped_column(Text, default="")
    decision: Mapped[str] = mapped_column(String(20), default="accepted")  # accepted|rejected|modified
    feedback_reason: Mapped[str] = mapped_column(Text, default="")
    guideline_id: Mapped[str | None] = mapped_column(ForeignKey("brand_guidelines.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    reviewer = relationship("User", foreign_keys=[reviewer_id])


class RecurringIssueGroup(Base):
    __tablename__ = "recurring_issue_groups"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    signature: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    category: Mapped[str] = mapped_column(String(60), default="")
    possible_root_cause: Mapped[str] = mapped_column(String(60), default="unclear_guideline")
    root_cause_note: Mapped[str] = mapped_column(Text, default="")
    suggested_improvement: Mapped[str] = mapped_column(Text, default="")
    finding_count: Mapped[int] = mapped_column(Integer, default=0)
    affected_submission_ids: Mapped[list] = mapped_column(JSON, default=list)
    example_corrections: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(30), default="open")  # open|proposal_created|dismissed
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=now)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=now)


class GuidelineProposal(Base):
    __tablename__ = "guideline_proposals"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[str | None] = mapped_column(ForeignKey("recurring_issue_groups.id", ondelete="SET NULL"), nullable=True)
    guideline_id: Mapped[str | None] = mapped_column(ForeignKey("brand_guidelines.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    current_rule: Mapped[str] = mapped_column(Text, default="")
    proposed_rule: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="")
    root_cause: Mapped[str] = mapped_column(String(60), default="unclear_guideline")
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(30), default="pending")  # pending|approved|rejected|needs_evidence
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class ApprovalRecord(Base):
    __tablename__ = "approval_records"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    entity_type: Mapped[str] = mapped_column(String(40))  # content|guideline_change|knowledge_document|fact
    entity_id: Mapped[str] = mapped_column(String(32))
    decision: Mapped[str] = mapped_column(String(30))  # approved|rejected|changes_requested
    notes: Mapped[str] = mapped_column(Text, default="")
    previous_status: Mapped[str] = mapped_column(String(30), default="")
    new_status: Mapped[str] = mapped_column(String(30), default="")
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    actor = relationship("User", foreign_keys=[actor_id])


class ChangeImpact(Base):
    __tablename__ = "change_impacts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    change_type: Mapped[str] = mapped_column(String(40), default="fact_update")
    entity_label: Mapped[str] = mapped_column(String(200), default="")
    previous_value: Mapped[str] = mapped_column(Text, default="")
    updated_value: Mapped[str] = mapped_column(Text, default="")
    affected_submission_id: Mapped[str | None] = mapped_column(ForeignKey("content_submissions.id", ondelete="SET NULL"), nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="open")  # open|recheck_requested|resolved
    resolved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_org_created", "organisation_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), default="")
    entity_id: Mapped[str] = mapped_column(String(32), default="")
    entity_label: Mapped[str] = mapped_column(String(250), default="")
    previous_value: Mapped[str] = mapped_column(Text, default="")
    updated_value: Mapped[str] = mapped_column(Text, default="")
    content_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    guideline_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decision: Mapped[str] = mapped_column(String(40), default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    actor = relationship("User", foreign_keys=[actor_id])


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    message: Mapped[str] = mapped_column(Text, default="")
    type: Mapped[str] = mapped_column(String(40), default="info")
    link: Mapped[str] = mapped_column(String(250), default="")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    submission_id: Mapped[str] = mapped_column(ForeignKey("content_submissions.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    author = relationship("User", foreign_keys=[author_id])


# ─── Campaign & Task Assignment (Two-Workspace Architecture) ───────────────────

class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(220), nullable=False)
    product: Mapped[str] = mapped_column(String(120), default="")
    objective: Mapped[str] = mapped_column(Text, default="")
    target_audience: Mapped[str] = mapped_column(String(300), default="")
    platform: Mapped[str] = mapped_column(String(80), default="")       # Instagram|LinkedIn|Google Ads|etc.
    content_type: Mapped[str] = mapped_column(String(50), default="advertisement")
    description: Mapped[str] = mapped_column(Text, default="")
    # Claims guidance for creators
    approved_claims_text: Mapped[str] = mapped_column(Text, default="")   # manager-curated for creators
    prohibited_claims_text: Mapped[str] = mapped_column(Text, default="")
    mandatory_messages: Mapped[str] = mapped_column(Text, default="")
    tone_of_voice: Mapped[str] = mapped_column(String(200), default="")
    cta: Mapped[str] = mapped_column(String(200), default="")             # call-to-action
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium")   # low|medium|high|urgent
    status: Mapped[str] = mapped_column(String(30), default="draft")      # draft|active|completed|cancelled
    # JSON lists
    knowledge_document_ids: Mapped[list] = mapped_column(JSON, default=list)  # authorised doc refs
    assigned_creator_ids: Mapped[list] = mapped_column(JSON, default=list)
    deliverables: Mapped[list] = mapped_column(JSON, default=list)        # [{format, quantity, platform}]
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    creator = relationship("User", foreign_keys=[created_by])
    task_assignments = relationship("TaskAssignment", back_populates="campaign", cascade="all, delete-orphan")
    organisation = relationship("Organisation")


class TaskAssignment(Base):
    __tablename__ = "task_assignments"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    creator_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    manager_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, default="")
    # Lifecycle status
    status: Mapped[str] = mapped_column(String(40), default="assigned")
    # assigned|accepted|in_progress|submitted|ai_review_completed|
    # changes_requested|resubmitted|awaiting_manager_approval|approved|rejected|completed
    submission_id: Mapped[str | None] = mapped_column(ForeignKey("content_submissions.id", ondelete="SET NULL"), nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    manager_notes: Mapped[str] = mapped_column(Text, default="")
    creator_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    campaign = relationship("Campaign", back_populates="task_assignments")
    creator = relationship("User", foreign_keys=[creator_id])
    manager = relationship("User", foreign_keys=[manager_id])
    submission = relationship("ContentSubmission", foreign_keys=[submission_id])
