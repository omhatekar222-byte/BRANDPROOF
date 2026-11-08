export interface User {
  id: string;
  full_name: string;
  email: string;
  title: string;
  avatar_color: string;
}

export interface Organisation {
  id: string;
  name: string;
  slug: string;
  industry: string;
  brand_colors: string[];
  is_demo: boolean;
  role?: string;
  settings: Record<string, unknown>;
}

export interface SessionPayload {
  access_token: string;
  token_type: string;
  user: User;
  organisations: Organisation[];
  active_organisation_id: string | null;
  role: string | null;
  role_label: string | null;
  permissions: string[];
  entry_role?: "administrator" | "freelancer";
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export type Classification = "supported" | "contradicted" | "unsupported" | "inconclusive" | "pending";
export interface ExampleCorrection {
  submission_id: string;
  submission_title: string;
  reviewer_decision: string;
  original: string;
  suggestion: string;
  final: string;
  reason: string;
  date: string;
}

export interface ExtractedClaim {
  id: string;
  submission_id: string;
  claim_text: string;
  category: string;
  risk_level: string;
  status: Classification;
  confidence: number;
  explanation: string;
  suggested_action: string;
  correction: string;
  evidence_document_id: string | null;
  evidence_source_label: string;
  evidence_passage: string;
  evidence_locator: string;
  evidence: Record<string, unknown>;
  extractor: string;
  created_at: string;
}

export interface Finding {
  id: string;
  submission_id: string;
  claim_id: string | null;
  title: string;
  category: string;
  severity: "low" | "medium" | "high" | "critical";
  original_text: string;
  explanation: string;
  guideline_ref: string;
  guideline_id: string | null;
  source_document_id: string | null;
  source_passage: string;
  source_locator: string;
  suggested_correction: string;
  confidence: number;
  detector: string;
  status: "open" | "accepted" | "rejected" | "modified" | "resolved";
  resolved_at: string | null;
  created_at: string;
  submission_title?: string;
  content_type?: string;
}

export interface ApprovalRecord {
  id: string;
  entity_type: string;
  entity_id: string;
  decision: string;
  notes: string;
  previous_status: string;
  new_status: string;
  actor: User | null;
  created_at: string;
}

export interface Submission {
  id: string;
  title: string;
  content_type: string;
  campaign: string;
  product: string;
  source_type: string;
  file_name: string | null;
  status: string;
  current_version: number;
  submitted_by: User | null;
  analysis_mode: string;
  analysis_error: string | null;
  proof_score: Record<string, unknown>;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
  word_count: number;
  excerpt: string;
  open_findings?: number;
}

export interface SubmissionDetail extends Submission {
  raw_text: string;
  versions: { id: string; version: number; note: string; created_at: string }[];
  claims: ExtractedClaim[];
  findings: Finding[];
  comments: { id: string; author: User | null; body: string; created_at: string }[];
  approvals: ApprovalRecord[];
  fact_usage: { fact_id: string; key: string; value: string; product: string; status: string; matched_text: string }[];
  counts: {
    claims: number;
    supported: number;
    contradicted: number;
    unsupported: number;
    inconclusive: number;
    findings_open: number;
    findings_resolved: number;
  };
}

export interface Dashboard {
  totals: {
    submissions: number;
    pending_reviews: number;
    approved: number;
    rejected: number;
    changes_requested: number;
    drafts: number;
    claims_total: number;
    claims_supported: number;
    claims_contradicted: number;
    claims_unsupported: number;
    claims_inconclusive: number;
    findings_open: number;
    findings_resolved: number;
    proposals_pending: number;
    impacts_open: number;
    recurring_groups: number;
    active_days: number;
  };
  recent_activity: { id: string; title: string; status: string; content_type: string; updated_at: string | null }[];
  guideline_gap_detector: {
    id: string; title: string; category: string; finding_count: number;
    root_cause: string; root_cause_note: string; suggested_improvement: string;
    examples: string[]; status: string; affected_count: number;
  }[];
  claim_expiry_radar: { id: string; claim_text: string; expiry_date: string; days_to_expiry: number; expired: boolean }[];
  expiry_radar: {
    claims: { id: string; claim_text: string; expiry_date: string; days_to_expiry: number; expired: boolean }[];
    documents_overdue: { id: string; title: string; review_date: string }[];
    facts_overdue: { id: string; key: string; value: string; review_date: string }[];
  };
  pending_actions: { type: string; label: string; link: string }[];
  by_status: Record<string, number>;
}

export interface DocumentItem {
  id: string;
  title: string;
  doc_type: string;
  category: string;
  status: string;
  version: number;
  approved_by: string | null;
  effective_date: string | null;
  review_date: string | null;
  file_name: string | null;
  tags: string[];
  page_count: number;
  char_count: number;
  created_at: string;
  updated_at: string;
  extracted_text?: string;
  facts?: Fact[];
}

export interface Fact {
  id: string;
  key: string;
  value: string;
  product: string;
  category: string;
  status: string;
  document_id: string | null;
  document_title: string | null;
  source_locator: string;
  review_date: string | null;
}

export interface ApprovedClaim {
  id: string;
  claim_text: string;
  category: string;
  status: "approved" | "prohibited" | "draft";
  evidence_document_id: string | null;
  review_date: string | null;
  expiry_date: string | null;
  created_at: string;
  expired?: boolean;
  days_to_expiry?: number | null;
}

export interface Guideline {
  id: string;
  title: string;
  category: string;
  content: string;
  summary: string;
  status: string;
  version: number;
  effective_date: string | null;
  review_date: string | null;
  updated_at: string;
}

export interface BrandAsset {
  id: string;
  name: string;
  asset_type: string;
  file_path: string | null;
  file_url: string | null;
  color_hex: string | null;
  is_approved: boolean;
  notes: string;
}

export interface Campaign {
  id: string;
  name: string;
  product: string;
  objective: string;
  target_audience: string;
  platform: string;
  content_type: string;
  description: string;
  approved_claims_text: string;
  prohibited_claims_text: string;
  mandatory_messages: string;
  tone_of_voice: string;
  cta: string;
  deadline: string | null;
  priority: string;
  status: string;
  deliverables: { format?: string; quantity?: number; platform?: string }[];
  task_count: number;
  knowledge_document_ids?: string[];
  assigned_creator_ids?: string[];
}

export interface Task {
  id: string;
  campaign_id: string;
  campaign_name: string;
  title: string;
  instructions: string;
  status: string;
  priority: string;
  deadline: string | null;
  creator_name: string;
  creator_email: string;
  manager_name: string;
  submission_id: string | null;
  manager_notes: string;
  creator_notes: string;
  created_at: string;
  updated_at: string;
  brief?: {
    campaign_name: string;
    product: string;
    objective: string;
    target_audience: string;
    platform: string;
    content_type: string;
    approved_claims: string;
    prohibited_claims: string;
    mandatory_messages: string;
    tone_of_voice: string;
    cta: string;
    deadline: string | null;
    deliverables: { format?: string; quantity?: number; platform?: string }[];
  };
}

export interface Member {
  id: string;
  user_id: string;
  full_name: string;
  email: string;
  role: string;
  title: string;
  avatar_color: string;
  is_active: boolean;
  joined_at: string;
}

export interface ExampleCorrection {
  submission_id: string;
  submission_title: string;
  reviewer_decision: string;
  original: string;
  suggestion: string;
  final: string;
  reason: string;
  date: string;
}

export interface RecurringGroup {
  id: string;
  signature: string;
  title: string;
  category: string;
  possible_root_cause: string;
  root_cause_label?: string;
  root_cause_note: string;
  suggested_improvement: string;
  finding_count: number;
  affected_submission_ids: string[];
  affected_count: number;
  example_corrections: (string | ExampleCorrection)[];
  status: string;
  first_seen: string;
  last_seen: string;
}

export interface GuidelineProposal {
  id: string;
  group_id: string | null;
  guideline_id: string | null;
  title: string;
  current_rule: string;
  proposed_rule: string;
  rationale: string;
  root_cause: string;
  evidence: string[];
  status: string;
  created_at: string;
  decided_at: string | null;
}

export interface FeedbackRecord {
  id: string;
  finding_id: string | null;
  submission_id: string | null;
  reviewer: User | null;
  original_content: string;
  issue_category: string;
  issue_title: string;
  original_suggestion: string;
  final_correction: string;
  decision: string;
  feedback_reason: string;
  created_at: string;
}

export interface NotificationItem {
  id: string;
  title: string;
  message: string;
  type: string;
  link: string;
  is_read: boolean;
  created_at: string;
}

export interface AnalysisResult {
  analysis_mode: string;
  analysis_error?: string | null;
  claims?: ExtractedClaim[];
  findings?: Finding[];
  counts?: Record<string, number>;
}
