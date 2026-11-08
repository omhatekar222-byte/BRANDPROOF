from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Role = Literal["admin", "content_creator", "reviewer", "approver"]


class BaseSchema(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


# ---------- Auth ----------
class SignUpRequest(BaseSchema):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    organisation_name: str | None = Field(default=None, max_length=160)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        return v


class LoginRequest(BaseSchema):
    email: EmailStr
    password: str


class RoleEntryRequest(BaseSchema):
    """Demo entry: a role selects a seeded workspace identity, no password."""
    role: Literal["administrator", "freelancer"]


class ForgotPasswordRequest(BaseSchema):
    email: EmailStr


class ResetPasswordRequest(BaseSchema):
    token: str
    password: str = Field(min_length=8, max_length=128)


class ProfileUpdate(BaseSchema):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    title: str | None = Field(default=None, max_length=120)
    avatar_color: str | None = Field(default=None, max_length=20)
    preferences: dict[str, Any] | None = None


class ChangePasswordRequest(BaseSchema):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


# ---------- Knowledge ----------
DOC_TYPES = Literal[
    "guideline", "product_spec", "company_info", "approved_claim", "terminology",
    "asset", "warranty_pricing", "restricted_language",
]


class DocumentCreate(BaseSchema):
    title: str = Field(min_length=2, max_length=220)
    doc_type: DOC_TYPES = "guideline"
    category: str = Field(default="General", max_length=80)
    text: str = Field(min_length=1)
    status: Literal["draft", "approved"] = "draft"
    version: int = 1
    effective_date: date | None = None
    review_date: date | None = None
    tags: list[str] = []


class DocumentUpdate(BaseSchema):
    title: str | None = Field(default=None, min_length=2, max_length=220)
    doc_type: DOC_TYPES | None = None
    category: str | None = None
    text: str | None = None
    status: Literal["draft", "approved", "archived", "outdated"] | None = None
    effective_date: date | None = None
    review_date: date | None = None
    tags: list[str] | None = None
    change_summary: str | None = Field(default=None, max_length=400)


class FactCreate(BaseSchema):
    key: str = Field(min_length=2, max_length=160)
    value: str = Field(min_length=1, max_length=300)
    product: str = Field(default="", max_length=120)
    category: str = Field(default="product", max_length=60)
    document_id: str | None = None
    status: Literal["draft", "approved"] = "draft"
    effective_date: date | None = None
    review_date: date | None = None
    source_locator: str = Field(default="", max_length=120)


class FactUpdate(BaseSchema):
    key: str | None = Field(default=None, min_length=2, max_length=160)
    value: str | None = Field(default=None, min_length=1, max_length=300)
    product: str | None = None
    category: str | None = None
    status: Literal["draft", "approved", "retired"] | None = None
    effective_date: date | None = None
    review_date: date | None = None
    source_locator: str | None = None
    change_summary: str | None = None


class ClaimCreate(BaseSchema):
    claim_text: str = Field(min_length=3)
    category: str = "promotional"
    status: Literal["approved", "prohibited", "draft"] = "approved"
    evidence_document_id: str | None = None
    review_date: date | None = None
    expiry_date: date | None = None


class AssetCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=160)
    asset_type: Literal["logo", "colour", "font", "image"] = "logo"
    color_hex: str | None = None
    notes: str = ""


class GuidelineCreate(BaseSchema):
    title: str = Field(min_length=3, max_length=200)
    category: str = "messaging"
    content: str = Field(min_length=5)
    summary: str = ""
    status: Literal["draft", "approved"] = "draft"
    effective_date: date | None = None
    review_date: date | None = None


class GuidelineUpdate(BaseSchema):
    title: str | None = None
    category: str | None = None
    content: str | None = None
    summary: str | None = None
    status: Literal["draft", "approved", "archived"] | None = None
    effective_date: date | None = None
    review_date: date | None = None
    change_summary: str | None = None


# ---------- Content ----------
CONTENT_TYPES = Literal[
    "advertisement", "social_post", "product_description", "email", "landing_page",
    "press_release", "document", "presentation",
]


class SubmissionCreate(BaseSchema):
    title: str = Field(min_length=2, max_length=220)
    content_type: CONTENT_TYPES = "advertisement"
    campaign: str = Field(default="", max_length=120)
    product: str = Field(default="", max_length=120)
    text: str = Field(min_length=10)
    submit_now: bool = True
    analyze_now: bool = True


class SubmissionUpdate(BaseSchema):
    title: str | None = Field(default=None, min_length=2, max_length=220)
    campaign: str | None = None
    product: str | None = None
    content_type: CONTENT_TYPES | None = None
    text: str | None = None
    note: str = ""


class AnalysisRequest(BaseSchema):
    force_demo: bool = False


class ApplyCorrectionsRequest(BaseSchema):
    finding_ids: list[str] | None = None
    note: str = ""


class CommentCreate(BaseSchema):
    body: str = Field(min_length=1, max_length=2000)


# ---------- Review ----------
class FindingDecision(BaseSchema):
    decision: Literal["accepted", "rejected", "modified"]
    final_correction: str | None = None
    reason: str = ""


class StatusTransition(BaseSchema):
    status: Literal["draft", "submitted", "under_review", "changes_requested", "approved", "rejected", "cleared_by_policy"]
    notes: str = ""


class ApprovalDecision(BaseSchema):
    decision: Literal["approved", "rejected", "changes_requested"]
    notes: str = ""


# ---------- Intelligence ----------
class FeedbackCreate(BaseSchema):
    finding_id: str | None = None
    submission_id: str | None = None
    original_content: str = ""
    issue_category: str = ""
    issue_title: str = ""
    original_suggestion: str = ""
    final_correction: str = ""
    decision: Literal["accepted", "rejected", "modified"] = "accepted"
    feedback_reason: str = ""
    guideline_id: str | None = None


class AnalyzeFeedbackRequest(BaseSchema):
    rebuild: bool = True


class ProposalCreate(BaseSchema):
    group_id: str | None = None
    guideline_id: str | None = None
    title: str = Field(min_length=3, max_length=220)
    current_rule: str = ""
    proposed_rule: str = Field(min_length=5)
    rationale: str = ""
    root_cause: str = "unclear_guideline"


class ProposalDecision(BaseSchema):
    decision: Literal["approved", "rejected", "needs_evidence"]
    notes: str = ""


class WhatIfRequest(BaseSchema):
    current_rule: str
    proposed_rule: str


# ---------- Impact ----------
class ImpactResolve(BaseSchema):
    action: Literal["recheck", "new_review", "resolve"]
    notes: str = ""


class ImpactAnalyzeRequest(BaseSchema):
    fact_id: str | None = None
    previous_value: str
    updated_value: str
    label: str = ""


# ---------- Org ----------
class InviteMemberRequest(BaseSchema):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    role: Role = "content_creator"
    title: str = ""


class MemberUpdateRequest(BaseSchema):
    role: Role
    title: str | None = None


class OrgUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    industry: str | None = None
    brand_colors: list[str] | None = None
    settings: dict[str, Any] | None = None


class RolePermissionUpdate(BaseSchema):
    role: Role
    permission: str
    enabled: bool


class NotificationRead(BaseSchema):
    ids: list[str] | None = None
    all: bool = False
