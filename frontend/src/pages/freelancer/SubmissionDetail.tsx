import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, FileWarning, History, Pencil, Sparkles } from "lucide-react";
import { api, ApiError } from "../../lib/api";
import { useSession } from "../../lib/session";
import type { SubmissionDetail } from "../../lib/types";
import { ClaimList, FindingList } from "../../components/VerificationReport";
import {
  Badge, ErrorNote, Field, LoadingBlock, Modal, SuccessNote, fmtDateTime,
} from "../../components/ui";

export default function FreelancerSubmissionDetail() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const { toast } = useSession();
  const [data, setData] = useState<SubmissionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [tab, setTab] = useState<"feedback" | "content" | "decisions">("feedback");
  const [reviseOpen, setReviseOpen] = useState(false);
  const [revision, setRevision] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api<SubmissionDetail>(`/content/submissions/${id}`));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The submission could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { void load(); }, [load]);

  const flash = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 5000);
  };

  const openRevision = () => {
    if (!data) return;
    setRevision(data.raw_text);
    setReviseOpen(true);
  };

  const applyCorrectionsToDraft = () => {
    let text = revision;
    let used = 0;
    for (const finding of data?.findings || []) {
      if (finding.original_text && finding.suggested_correction && text.includes(finding.original_text)) {
        text = text.replace(finding.original_text, finding.suggested_correction);
        used += 1;
      }
    }
    for (const claim of data?.claims || []) {
      if (claim.claim_text && claim.correction && text.includes(claim.claim_text)) {
        text = text.replace(claim.claim_text, claim.correction);
        used += 1;
      }
    }
    setRevision(text);
    toast("ok", used ? `${used} suggested correction(s) inserted into the draft. Review the wording before resubmitting.` : "No exact matches were found in the current draft.");
  };

  const resubmit = async () => {
    if (!data) return;
    if (revision.trim().length < 10) {
      setError("The revised content is too short to verify.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api(`/content/submissions/${data.id}`, {
        method: "PATCH",
        body: { text: revision, note: "Creator revised content after verification feedback." },
      });
      await api(`/content/submissions/${data.id}/analyze`, { method: "POST", body: {} });
      if (data.status === "changes_requested") {
        await api(`/content/submissions/${data.id}/status`, {
          method: "POST",
          body: { status: "submitted", notes: "Creator revised and resubmitted the content." },
        });
      }
      setReviseOpen(false);
      await load();
      flash("Revision saved and re-verified. The manager will make the next approval decision.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The revision could not be saved.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingBlock label="Loading verification feedback…" />;
  if (!data) {
    return (
      <div>
        <ErrorNote message={error || "Submission not found."} />
        <button className="btn btn-secondary mt-4" onClick={() => navigate("/submissions")}><ArrowLeft size={14} /> Back to submissions</button>
      </div>
    );
  }

  const canRevise = !["under_review", "approved", "rejected"].includes(data.status);
  const managerNotes = data.approvals.filter((a) => a.notes);

  return (
    <div className="fade-in">
      <button className="btn btn-ghost btn-sm mb-3 -ml-2" onClick={() => navigate("/submissions")}>
        <ArrowLeft size={14} /> My Submissions
      </button>

      {notice && <div className="mb-4"><SuccessNote>{notice}</SuccessNote></div>}
      {error && <div className="mb-4"><ErrorNote message={error} /></div>}

      <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge status={data.status} />
            <span className={`badge ${data.analysis_mode === "ai" ? "b-violet" : "b-demo"}`}>
              {data.analysis_mode === "ai" ? "AI-assisted" : "Demo verification"}
            </span>
            <span className="text-[10.5px] muted">v{data.current_version}</span>
          </div>
          <h1 className="page-title mt-2">{data.title}</h1>
          <p className="page-sub">{data.campaign || "No campaign"} · submitted {fmtDateTime(data.created_at)} · {data.word_count} words</p>
        </div>
        {canRevise && (
          <button className="btn btn-primary" onClick={openRevision}><Pencil size={14} /> Revise & resubmit</button>
        )}
      </div>

      {data.status === "changes_requested" && (
        <div className="mb-4 flex items-start gap-2 rounded-xl border px-4 py-3 text-[12px]" style={{ borderColor: "rgba(255,181,71,.3)", background: "rgba(255,181,71,.06)" }}>
          <FileWarning size={15} className="mt-0.5 shrink-0" style={{ color: "var(--bp-warning)" }} />
          <span>Your manager requested changes. Review the findings below, revise the wording, and resubmit. The content is not approved until a new human decision is recorded.</span>
        </div>
      )}
      {data.status === "rejected" && (
        <div className="mb-4 flex items-start gap-2 rounded-xl border px-4 py-3 text-[12px]" style={{ borderColor: "rgba(255,91,112,.28)", background: "rgba(255,91,112,.05)" }}>
          <FileWarning size={15} className="mt-0.5 shrink-0" style={{ color: "var(--bp-danger)" }} />
          <span>This submission was rejected. Read the manager's reason below. Contact your brand manager before starting a new submission.</span>
        </div>
      )}
      {data.status === "approved" && (
        <div className="mb-4 flex items-start gap-2 rounded-xl border px-4 py-3 text-[12px]" style={{ borderColor: "rgba(0,201,154,.26)", background: "rgba(0,201,154,.05)" }}>
          <CheckCircle2 size={15} className="mt-0.5 shrink-0" style={{ color: "var(--bp-success)" }} />
          <span>Approved by the brand team. This content may be used in the campaign.</span>
        </div>
      )}

      <div className="mb-5 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        <Count label="Claims" value={data.counts.claims} />
        <Count label="Supported" value={data.counts.supported} color="var(--bp-success)" />
        <Count label="Contradicted" value={data.counts.contradicted} color="var(--bp-danger)" />
        <Count label="Unsupported" value={data.counts.unsupported} color="var(--bp-warning)" />
        <Count label="Inconclusive" value={data.counts.inconclusive} color="var(--bp-cyan)" />
        <Count label="Open findings" value={data.counts.findings_open} color="var(--bp-warning)" />
      </div>

      <div className="tabs mb-5">
        <button className={`tab ${tab === "feedback" ? "active" : ""}`} onClick={() => setTab("feedback")}>AI feedback</button>
        <button className={`tab ${tab === "content" ? "active" : ""}`} onClick={() => setTab("content")}>My content</button>
        <button className={`tab ${tab === "decisions" ? "active" : ""}`} onClick={() => setTab("decisions")}>Manager decisions</button>
      </div>

      {tab === "feedback" && (
        <div className="space-y-4">
          <section className="card card-pad">
            <div className="mb-4">
              <h2 className="section-title flex items-center gap-2"><Sparkles size={15} style={{ color: "#b9a5ff" }} /> Claims and suggested wording</h2>
              <p className="mt-0.5 text-[11.5px] muted">Each statement is classified against approved knowledge. Corrections are suggestions — you decide how to rewrite your work.</p>
            </div>
            <ClaimList claims={data.claims} />
          </section>
          <section className="card card-pad">
            <h2 className="section-title">Guideline feedback</h2>
            <p className="mt-0.5 text-[11.5px] muted">These findings relate to brand rules, prohibited language, or required statements.</p>
            <div className="mt-3">
              <FindingList findings={data.findings} claims={data.claims} />
            </div>
          </section>

          <div className="rounded-xl border p-4 text-[11.5px] leading-relaxed" style={{ borderColor: "var(--bp-border)" }}>
            <b>What the classifications mean:</b> <span style={{ color: "var(--bp-success)" }}>Supported</span> matches approved evidence;{" "}
            <span style={{ color: "var(--bp-danger)" }}>Contradicted</span> conflicts with an approved fact;{" "}
            <span style={{ color: "var(--bp-warning)" }}>Unsupported</span> has no approved evidence (this does not mean it is false);{" "}
            <span style={{ color: "var(--bp-cyan)" }}>Inconclusive</span> means there is not enough information to decide.
          </div>
        </div>
      )}

      {tab === "content" && (
        <section className="card card-pad">
          <h2 className="section-title mb-3">Submitted text</h2>
          <div className="whitespace-pre-wrap rounded-xl border p-4 text-[13px] leading-relaxed" style={{ borderColor: "var(--bp-border)", background: "#0e1728" }}>
            {data.raw_text}
          </div>
          <div className="mt-4">
            <h3 className="section-title mb-2 flex items-center gap-2"><History size={14} /> Version history</h3>
            <ul className="space-y-2">
              {data.versions.map((v) => (
                <li key={v.id} className="flex items-center justify-between gap-2 border-b pb-2 text-[11.5px] last:border-0" style={{ borderColor: "var(--bp-border)" }}>
                  <span><b>v{v.version}</b> · {v.note}</span>
                  <span className="muted">{fmtDateTime(v.created_at)}</span>
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}

      {tab === "decisions" && (
        <section className="card card-pad">
          <h2 className="section-title mb-3">Manager decision history</h2>
          {managerNotes.length === 0 ? (
            <p className="text-[12.5px] muted">No manager decision notes have been recorded for this submission yet.</p>
          ) : (
            <ul className="space-y-3">
              {managerNotes.map((approval) => (
                <li key={approval.id} className="rounded-lg border p-3" style={{ borderColor: "var(--bp-border)" }}>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge status={approval.new_status} />
                    <span className="text-[11px] font-semibold">{approval.actor?.full_name}</span>
                    <span className="text-[10px] muted">{approval.actor?.title} · {fmtDateTime(approval.created_at)}</span>
                  </div>
                  <p className="mt-1.5 text-[12px] leading-relaxed text-secondary">{approval.notes}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <Modal
        open={reviseOpen}
        onClose={() => setReviseOpen(false)}
        title="Revise and resubmit"
        wide
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setReviseOpen(false)}>Cancel</button>
            <button className="btn btn-secondary" onClick={applyCorrectionsToDraft}>Insert suggested corrections</button>
            <button className="btn btn-primary" onClick={resubmit} disabled={saving}>{saving ? "Re-verifying…" : "Save & re-verify"}</button>
          </>
        }
      >
        <div className="space-y-3">
          <p className="text-[12px] muted">
            Edit the content using the feedback. Saving creates a new version and re-runs verification; your
            manager still makes the approval decision.
          </p>
          <Field label="Revised content">
            <textarea className="textarea" rows={14} value={revision} onChange={(e) => setRevision(e.target.value)} />
          </Field>
        </div>
      </Modal>
    </div>
  );
}

function Count({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div className="card px-3 py-2.5">
      <p className="eyebrow">{label}</p>
      <p className="mt-0.5 text-[19px] font-bold leading-none" style={{ color: color || "var(--bp-ink)" }}>{value}</p>
    </div>
  );
}
