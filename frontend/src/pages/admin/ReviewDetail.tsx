import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  AlertTriangle, ArrowLeft, CheckCircle2, FileText, History, RefreshCw, Send, Sparkles, Wand2,
} from "lucide-react";
import { api, ApiError } from "../../lib/api";
import { useSession } from "../../lib/session";
import type { Finding, SubmissionDetail } from "../../lib/types";
import { ClaimList, FindingList } from "../../components/VerificationReport";
import {
  Badge, Confirm, ErrorNote, Field, LoadingBlock, Modal, SuccessNote,
  fmtDateTime, timeAgo,
} from "../../components/ui";

export default function ReviewDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const { toast } = useSession();
  const [data, setData] = useState<SubmissionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [tab, setTab] = useState<"report" | "content" | "history">("report");
  const [busy, setBusy] = useState(false);
  const [decision, setDecision] = useState<null | { finding: Finding; kind: "rejected" | "investigate"; reason: string }>(null);
  const [confirmAnalyze, setConfirmAnalyze] = useState(false);
  const [confirmSend, setConfirmSend] = useState(false);
  const [confirmApply, setConfirmApply] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const detail = await api<SubmissionDetail>(`/content/submissions/${id}`);
      setData(detail);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The submission could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { void load(); }, [load]);

  const flash = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 4500);
  };

  const reanalyze = async () => {
    setConfirmAnalyze(false);
    setBusy(true);
    setError("");
    try {
      await api(`/content/submissions/${id}/analyze`, { method: "POST", body: {} });
      await load();
      flash("Verification re-run against the current approved knowledge base.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Analysis failed.");
    } finally {
      setBusy(false);
    }
  };

  const sendToApproval = async () => {
    setConfirmSend(false);
    setBusy(true);
    try {
      await api(`/content/submissions/${id}/status`, { method: "POST", body: { status: "under_review", notes: "Sent to the Approval Centre by an administrator." } });
      await load();
      flash("Content moved to the Approval Centre. The AI result is separate from the human decision.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The status could not be updated.");
    } finally {
      setBusy(false);
    }
  };

  const decideFinding = async (finding: Finding, kind: "accepted" | "rejected" | "investigate", reason = "") => {
    if (kind === "rejected" || kind === "investigate") {
      setDecision({ finding, kind, reason: reason || (kind === "investigate" ? "Marked for manual investigation." : "") });
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api(`/review/findings/${finding.id}/decide`, { method: "POST", body: { decision: "accepted", reason: "Accepted by administrator." } });
      await load();
      flash("Correction accepted. Reviewer decisions are stored as organisational feedback.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The decision could not be saved.");
    } finally {
      setBusy(false);
    }
  };

  const submitRejection = async () => {
    if (!decision) return;
    if (!decision.reason.trim()) {
      setError("Provide a reason for rejecting or marking this finding.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api(`/review/findings/${decision.finding.id}/decide`, {
        method: "POST",
        body: {
          decision: "rejected",
          reason: decision.kind === "investigate"
            ? `Marked for manual investigation: ${decision.reason.trim()}`
            : decision.reason.trim(),
        },
      });
      setDecision(null);
      await load();
      flash(decision.kind === "investigate" ? "Finding marked for manual investigation." : "Finding rejected with a recorded reason.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The decision could not be saved.");
    } finally {
      setBusy(false);
    }
  };

  const applyCorrections = async () => {
    setConfirmApply(false);
    setBusy(true);
    try {
      const result = await api<{ applied: number; skipped: number }>(`/content/submissions/${id}/apply-corrections`, { method: "POST", body: {} });
      await load();
      flash(`Applied ${result.applied} correction(s)${result.skipped ? `, skipped ${result.skipped}` : ""}. The content was re-analysed.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Corrections could not be applied.");
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <LoadingBlock label="Loading verification report…" />;

  if (!data) {
    return (
      <div>
        <ErrorNote message={error || "Submission not found."} />
        <button className="btn btn-secondary mt-4" onClick={() => navigate("/review")}><ArrowLeft size={14} /> Back to Content Review</button>
      </div>
    );
  }

  const counts = data.counts;
  const proposed = data.findings.filter((f) => f.suggested_correction && ["open", "accepted", "modified"].includes(f.status)).length;
  const aiOrDemo = data.analysis_mode;

  return (
    <div className="fade-in">
      <button className="btn btn-ghost btn-sm mb-3 -ml-2" onClick={() => navigate("/review")}>
        <ArrowLeft size={14} /> Content Review
      </button>

      <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge status={data.status} />
            <span className={`badge ${aiOrDemo === "ai" ? "b-violet" : aiOrDemo === "demo" ? "b-demo" : "b-neutral"}`}>
              {aiOrDemo === "ai" ? "AI-assisted analysis" : aiOrDemo === "demo" ? "Demo verification engine" : "Not analysed"}
            </span>
            <span className="text-[10.5px] muted">v{data.current_version}</span>
          </div>
          <h1 className="page-title mt-2">{data.title}</h1>
          <p className="page-sub">
            {data.submitted_by?.full_name || "Unknown creator"} · {data.campaign || "No campaign"} · {data.content_type.replace(/_/g, " ")} · submitted {fmtDateTime(data.created_at)}
          </p>
          {data.analysis_mode === "demo" && (
            <p className="mt-2 max-w-3xl text-[10.5px] leading-relaxed" style={{ color: "#a997e8" }}>
              No external AI provider is configured. These results come from deterministic claim extraction and
              evidence retrieval against this workspace. They are labelled demo output and no model-generated
              citation is implied.
            </p>
          )}
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <button className="btn btn-secondary" onClick={() => setConfirmAnalyze(true)} disabled={busy}>
            <RefreshCw size={14} /> Request new analysis
          </button>
          <button className="btn btn-primary" onClick={() => setConfirmSend(true)} disabled={busy || data.status === "under_review" || data.status === "approved"}>
            <Send size={14} /> {data.status === "under_review" ? "In Approval Centre" : "Send to approval"}
          </button>
        </div>
      </div>

      {notice && <div className="mb-4"><SuccessNote>{notice}</SuccessNote></div>}
      {error && <div className="mb-4"><ErrorNote message={error} /></div>}

      <div className="mb-5 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        <CountCard label="Claims identified" value={counts.claims} />
        <CountCard label="Supported" value={counts.supported} color="var(--bp-success)" />
        <CountCard label="Contradicted" value={counts.contradicted} color="var(--bp-danger)" />
        <CountCard label="Unsupported" value={counts.unsupported} color="var(--bp-warning)" />
        <CountCard label="Inconclusive" value={counts.inconclusive} color="var(--bp-cyan)" />
        <CountCard label="Open findings" value={counts.findings_open} color="var(--bp-warning)" />
      </div>

      <div className="tabs mb-5">
        <button className={`tab ${tab === "report" ? "active" : ""}`} onClick={() => setTab("report")}>Verification report</button>
        <button className={`tab ${tab === "content" ? "active" : ""}`} onClick={() => setTab("content")}>Submitted content</button>
        <button className={`tab ${tab === "history" ? "active" : ""}`} onClick={() => setTab("history")}>Decision history ({data.approvals.length})</button>
      </div>

      {tab === "report" && (
        <div className="space-y-5">
          <section className="card card-pad">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="section-title flex items-center gap-2"><Sparkles size={15} style={{ color: "#b9a5ff" }} /> Claim-level verification</h2>
                <p className="mt-0.5 text-[11.5px] muted">Every claim is classified independently with its explanation and evidence.</p>
              </div>
              {data.status !== "approved" && (
                <button className="btn btn-secondary btn-sm" onClick={() => setConfirmApply(true)} disabled={busy}>
                  <Wand2 size={13} /> Apply accepted corrections
                </button>
              )}
            </div>
            <ClaimList claims={data.claims} />
          </section>

          {data.fact_usage.length > 0 && (
            <section className="card card-pad">
              <h2 className="section-title flex items-center gap-2"><FileText size={15} /> Approved facts matched in this content</h2>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {data.fact_usage.map((fact) => (
                  <div key={fact.fact_id} className="rounded-lg border p-3" style={{ borderColor: "var(--bp-border)", background: "var(--bp-surface-inset)" }}>
                    <p className="text-[11.5px] font-semibold">{fact.key}</p>
                    <p className="text-[12px]" style={{ color: "var(--bp-success)" }}>{fact.value}</p>
                    <p className="mt-1 text-[10.5px] muted">Matched: “{fact.matched_text}” · {fact.status}</p>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="card card-pad">
            <div className="mb-4">
              <h2 className="section-title flex items-center gap-2"><AlertTriangle size={15} style={{ color: "var(--bp-warning)" }} /> Guideline and policy findings</h2>
              <p className="mt-0.5 text-[11.5px] muted">
                {proposed} actionable correction{proposed === 1 ? "" : "s"} available. Accepting, rejecting, or marking a
                finding records a manager decision and reason for future analysis.
              </p>
            </div>
            <FindingList
              findings={data.findings}
              claims={data.claims}
              busyId={busy ? "busy" : null}
              onDecide={(finding, kind) => { void decideFinding(finding, kind); }}
            />
          </section>
        </div>
      )}

      {tab === "content" && (
        <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
          <section className="card card-pad">
            <h2 className="section-title mb-3">Submitted text</h2>
            <div className="whitespace-pre-wrap rounded-xl border p-4 text-[13px] leading-relaxed" style={{ borderColor: "var(--bp-border)", background: "#0e1728" }}>
              {data.raw_text || "No text stored for this submission."}
            </div>
          </section>
          <section className="card card-pad">
            <h2 className="section-title mb-3 flex items-center gap-2"><History size={15} /> Versions</h2>
            <ul className="space-y-2.5">
              {data.versions.map((v) => (
                <li key={v.id} className="flex items-start justify-between gap-3 border-b pb-2.5 last:border-0 last:pb-0" style={{ borderColor: "var(--bp-border)" }}>
                  <div>
                    <p className="text-[12px] font-semibold">Version {v.version}</p>
                    <p className="text-[11px] muted">{v.note}</p>
                  </div>
                  <span className="shrink-0 text-[10.5px] muted">{fmtDateTime(v.created_at)}</span>
                </li>
              ))}
            </ul>
            {data.file_name && (
              <p className="mt-4 border-t pt-3 text-[11px] muted" style={{ borderColor: "var(--bp-border)" }}>
                Source file: {data.file_name} ({data.source_type})
              </p>
            )}
          </section>
        </div>
      )}

      {tab === "history" && (
        <section className="card card-pad">
          <h2 className="section-title mb-3">Approval and status history</h2>
          {data.approvals.length === 0 ? (
            <p className="text-[12.5px] muted">No human decisions have been recorded for this submission yet.</p>
          ) : (
            <ol className="relative space-y-4 border-l pl-5" style={{ borderColor: "var(--bp-border)" }}>
              {data.approvals.map((approval) => (
                <li key={approval.id} className="relative">
                  <span className="absolute -left-[26px] top-1 h-2.5 w-2.5 rounded-full" style={{ background: approval.decision === "approved" ? "var(--bp-success)" : approval.decision === "rejected" ? "var(--bp-danger)" : "var(--bp-warning)" }} />
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-[12.5px] font-semibold capitalize">{approval.decision.replace(/_/g, " ")}</p>
                    <span className="text-[10.5px] muted">{approval.previous_status} → {approval.new_status}</span>
                  </div>
                  <p className="mt-0.5 text-[11px] muted">
                    {approval.actor?.full_name || "Administrator"} · {approval.actor?.title || "Brand team"} · {fmtDateTime(approval.created_at)}
                  </p>
                  {approval.notes && <p className="mt-1.5 rounded-lg border p-2.5 text-[11.5px] text-secondary" style={{ borderColor: "var(--bp-border)" }}>{approval.notes}</p>}
                </li>
              ))}
            </ol>
          )}
        </section>
      )}

      <Modal
        open={!!decision}
        onClose={() => setDecision(null)}
        title={decision?.kind === "investigate" ? "Mark finding for investigation" : "Reject suggested correction"}
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setDecision(null)}>Cancel</button>
            <button className="btn btn-primary" onClick={submitRejection} disabled={busy}>{busy ? "Saving…" : "Save decision"}</button>
          </>
        }
      >
        {decision && (
          <div className="space-y-3">
            <p className="text-[12.5px] text-secondary">“{decision.finding.title}”</p>
            <Field label={decision.kind === "investigate" ? "What needs investigation?" : "Reason for rejecting this correction"} hint="The reason is stored and used as organisational context in later reviews.">
              <textarea className="textarea" rows={4} value={decision.reason} onChange={(e) => setDecision({ ...decision, reason: e.target.value })} placeholder="Explain your decision. The manager always retains final authority." />
            </Field>
            <p className="text-[11px] muted">Rejecting the AI's suggestion does not approve the content. The submission still requires a final approval decision.</p>
          </div>
        )}
      </Modal>

      <Confirm
        open={confirmAnalyze}
        onClose={() => setConfirmAnalyze(false)}
        onConfirm={reanalyze}
        title="Request new analysis"
        body="This re-runs claim extraction and evidence checks against the current approved knowledge. Existing reviewer decisions on findings are kept."
        confirmLabel="Run analysis"
      />
      <Confirm
        open={confirmSend}
        onClose={() => setConfirmSend(false)}
        onConfirm={sendToApproval}
        title="Send to Approval Centre"
        body="The submission will be marked for a human decision. An AI 'supported' result alone does not approve or publish anything."
        confirmLabel="Send to approval"
      />
      <Confirm
        open={confirmApply}
        onClose={() => setConfirmApply(false)}
        onConfirm={applyCorrections}
        title="Apply accepted corrections"
        body="Actionable corrections will replace their matched original sentences, creating a new version, then the content will be re-analysed. Nothing is approved automatically."
        confirmLabel="Apply corrections"
      />
    </div>
  );
}

function CountCard({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div className="card px-3.5 py-3">
      <p className="eyebrow">{label}</p>
      <p className="mt-1 text-[20px] font-bold leading-none" style={{ color: color || "var(--bp-ink)" }}>{value}</p>
    </div>
  );
}
