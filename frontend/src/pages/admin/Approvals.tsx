import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle, ArrowRight, CheckCircle2, ClipboardCheck, FileText, ShieldCheck, XCircle,
} from "lucide-react";
import { api, ApiError } from "../../lib/api";
import { useSession } from "../../lib/session";
import type { Page, Submission, SubmissionDetail, Task } from "../../lib/types";
import {
  Badge, Confirm, Empty, ErrorNote, Field, LoadingBlock, PageHeader, SuccessNote,
  fmtDateTime, timeAgo,
} from "../../components/ui";

export default function ApprovalsPage() {
  const { toast } = useSession();
  const [queue, setQueue] = useState<Submission[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SubmissionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [notes, setNotes] = useState("");
  const [override, setOverride] = useState(false);
  const [confirmDecision, setConfirmDecision] = useState<null | "approved" | "rejected" | "changes_requested">(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async (keepSelected = true) => {
    setLoading(true);
    setError("");
    try {
      const [submitted, underReview, taskList] = await Promise.all([
        api<Page<Submission>>("/content/submissions?status=submitted&page_size=100"),
        api<Page<Submission>>("/content/submissions?status=under_review&page_size=100"),
        api<{ items: Task[] }>("/tasks"),
      ]);
      const items = [...submitted.items, ...underReview.items]
        .filter((s, index, list) => list.findIndex((x) => x.id === s.id) === index)
        .sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1));
      setQueue(items);
      setTasks(taskList.items);
      if (!keepSelected || !selectedId || !items.some((s) => s.id === selectedId)) {
        setSelectedId(items[0]?.id || null);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The approval queue could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [selectedId]);

  useEffect(() => { void load(); }, []);

  const loadDetail = async (id: string) => {
    setDetailLoading(true);
    setDetail(null);
    setNotes("");
    setOverride(false);
    try {
      const data = await api<SubmissionDetail>(`/content/submissions/${id}`);
      setDetail(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The submission could not be opened.");
    } finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => {
    if (selectedId) void loadDetail(selectedId);
    else setDetail(null);
  }, [selectedId]);

  const flash = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 5000);
  };

  const recommendation = useMemo(() => {
    if (!detail) return null;
    const c = detail.counts;
    if (c.contradicted > 0) return { decision: "changes_requested" as const, label: "Request changes", reason: `${c.contradicted} contradicted claim(s) need correction.` };
    if (c.unsupported > 0) return { decision: "changes_requested" as const, label: "Request changes", reason: `${c.unsupported} unsupported claim(s) lack approved evidence.` };
    if (c.inconclusive > 0) return { decision: "changes_requested" as const, label: "Request changes", reason: `${c.inconclusive} claim(s) are inconclusive and need evidence.` };
    if (c.claims === 0) return { decision: "changes_requested" as const, label: "Request changes", reason: "No verifiable claims were identified in this content." };
    return { decision: "approved" as const, label: "Approve", reason: "All identified claims are supported by approved evidence." };
  }, [detail]);

  const needsOverride = !!recommendation && confirmDecision !== null && confirmDecision !== recommendation.decision;

  const decide = async () => {
    if (!detail || !confirmDecision) return;
    if (notes.trim().length < 3) {
      setError("Add a decision note so the approval history is explainable.");
      return;
    }
    if (needsOverride && !override) {
      setError("This decision overrides the AI recommendation. Confirm the override before continuing.");
      return;
    }
    const decision = confirmDecision;
    setConfirmDecision(null);
    setSaving(true);
    setError("");
    try {
      const prefix = needsOverride ? `Override of AI recommendation (${recommendation?.label}): ` : "";
      await api(`/content/submissions/${detail.id}/decision`, {
        method: "POST",
        body: { decision, notes: `${prefix}${notes.trim()}` },
      });
      await load(false);
      flash(
        decision === "approved"
          ? "Content approved. The decision and its reason are recorded in the audit history."
          : decision === "rejected"
            ? "Content rejected and the creator has been notified."
            : "Changes requested. The creator can now revise and resubmit.",
      );
      setNotes("");
      setOverride(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The decision could not be saved.");
    } finally {
      setSaving(false);
    }
  };

  const decideTask = async (task: Task, status: string) => {
    setSaving(true);
    setError("");
    try {
      await api(`/tasks/${task.id}/status`, { method: "PATCH", body: { status, notes: "Decided from the Approval Centre." } });
      await load();
      flash(`Task “${task.title}” marked ${status.replace(/_/g, " ")}.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The task could not be updated.");
    } finally {
      setSaving(false);
    }
  };

  const awaitingTasks = tasks.filter((task) => task.status === "awaiting_manager_approval");

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow="Human decision, always separate from AI"
        title="Approval Centre"
        subtitle="Review the verification report and make the final decision. An AI classification of supported does not publish content — only a recorded human approval can."
      />

      {notice && <div className="mb-4"><SuccessNote>{notice}</SuccessNote></div>}
      {error && <div className="mb-4"><ErrorNote message={error} /></div>}

      {loading ? (
        <LoadingBlock label="Loading the approval queue…" />
      ) : queue.length === 0 ? (
        <Empty
          title="Nothing is awaiting approval"
          hint="Submissions appear here after content review. Send a verified submission to approval from its verification page."
          action={<Link to="/review" className="btn btn-primary">Open Content Review <ArrowRight size={14} /></Link>}
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[350px_1fr]">
          <section className="card self-start overflow-hidden">
            <div className="border-b px-4 py-3" style={{ borderColor: "var(--bp-border)" }}>
              <h2 className="section-title">Approval queue</h2>
              <p className="text-[11px] muted">{queue.length} submission{queue.length === 1 ? "" : "s"} awaiting a decision</p>
            </div>
            <div className="max-h-[calc(100vh-240px)] overflow-y-auto">
              {queue.map((item) => (
                <button
                  key={item.id}
                  onClick={() => setSelectedId(item.id)}
                  className={`block w-full border-b px-4 py-3 text-left last:border-0 ${selectedId === item.id ? "bg-[rgba(139,92,246,.09)]" : "hover:bg-[var(--bp-hover-subtle)]"}`}
                  style={{ borderColor: "var(--bp-border)" }}
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="min-w-0 truncate text-[12.5px] font-semibold">{item.title}</p>
                    <Badge status={item.status} />
                  </div>
                  <p className="mt-1 truncate text-[10.5px] muted">
                    {item.submitted_by?.full_name || "Unknown"} · {item.campaign || "No campaign"}
                  </p>
                  <div className="mt-1.5 flex items-center justify-between text-[10px] muted">
                    <span>{timeAgo(item.created_at)}</span>
                    <span>{item.open_findings ?? 0} open finding(s)</span>
                  </div>
                </button>
              ))}
            </div>
          </section>

          <section className="min-w-0">
            {detailLoading || !detail ? (
              <div className="card card-pad"><LoadingBlock label="Loading the verification report…" /></div>
            ) : (
              <div className="space-y-4">
                <div className="card card-pad">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge status={detail.status} />
                        <span className={`badge ${detail.analysis_mode === "ai" ? "b-violet" : "b-demo"}`}>
                          {detail.analysis_mode === "ai" ? "AI-assisted" : "Demo engine"}
                        </span>
                        <span className="text-[10.5px] muted">v{detail.current_version}</span>
                      </div>
                      <h2 className="mt-2 text-[17px] font-semibold tracking-tight">{detail.title}</h2>
                      <p className="mt-0.5 text-[11.5px] muted">
                        {detail.submitted_by?.full_name} · {detail.campaign || "No campaign"} · submitted {fmtDateTime(detail.created_at)}
                      </p>
                    </div>
                    <Link to={`/review/${detail.id}`} className="btn btn-secondary btn-sm shrink-0">
                      <FileText size={13} /> Full report
                    </Link>
                  </div>

                  <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-5">
                    <CountBox label="Claims" value={detail.counts.claims} />
                    <CountBox label="Supported" value={detail.counts.supported} color="var(--bp-success)" />
                    <CountBox label="Contradicted" value={detail.counts.contradicted} color="var(--bp-danger)" />
                    <CountBox label="Unsupported" value={detail.counts.unsupported} color="var(--bp-warning)" />
                    <CountBox label="Inconclusive" value={detail.counts.inconclusive} color="var(--bp-cyan)" />
                  </div>
                </div>

                <div className="card card-pad">
                  <h3 className="section-title flex items-center gap-2"><ShieldCheck size={15} /> AI recommendation (advisory)</h3>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <span className={`badge ${recommendation?.decision === "approved" ? "b-supported" : "b-unsupported"}`}>
                      {recommendation?.label}
                    </span>
                    <span className="text-[12px] text-secondary">{recommendation?.reason}</span>
                  </div>
                  <p className="mt-2 text-[10.5px] leading-relaxed muted">
                    This is not an approval. The verification engine has no publishing authority; your recorded
                    decision below is the only thing that changes the content's approval status.
                  </p>
                  {detail.findings.filter((f) => ["high", "critical"].includes(f.severity) && f.status !== "resolved").length > 0 && (
                    <p className="mt-2 flex items-center gap-1.5 text-[11px]" style={{ color: "var(--bp-danger)" }}>
                      <AlertTriangle size={12} /> {detail.findings.filter((f) => ["high", "critical"].includes(f.severity) && f.status !== "resolved").length} high-risk finding(s) remain unresolved.
                    </p>
                  )}
                </div>

                <div className="card card-pad">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="section-title">Key findings</h3>
                    <Link to={`/review/${detail.id}`} className="text-[11px] font-semibold" style={{ color: "var(--bp-cyan)" }}>Inspect all findings</Link>
                  </div>
                  {detail.claims.length === 0 ? (
                    <p className="mt-2 text-[12px] muted">No claims were identified. REVIEW the content manually before deciding.</p>
                  ) : (
                    <ul className="mt-3 space-y-2">
                      {detail.claims.filter((c) => c.status !== "supported").slice(0, 4).map((claim) => (
                        <li key={claim.id} className="rounded-lg border p-2.5" style={{ borderColor: "var(--bp-border)" }}>
                          <div className="flex items-start justify-between gap-2">
                            <p className="text-[12px] leading-snug">{claim.claim_text}</p>
                            <Badge status={claim.status} />
                          </div>
                          <p className="mt-1 line-clamp-2 text-[11px] muted">{claim.explanation}</p>
                        </li>
                      ))}
                      {detail.claims.every((c) => c.status === "supported") && (
                        <li className="rounded-lg border p-2.5 text-[12px]" style={{ borderColor: "rgba(0,201,154,.25)", background: "rgba(0,201,154,.05)" }}>
                          <CheckCircle2 size={13} className="mr-1.5 inline" style={{ color: "var(--bp-success)" }} />
                          All {detail.claims.length} identified claims are supported by approved evidence.
                        </li>
                      )}
                    </ul>
                  )}
                </div>

                {detail.approvals.length > 0 && (
                  <div className="card card-pad">
                    <h3 className="section-title">Decision history</h3>
                    <ul className="mt-2 space-y-2">
                      {detail.approvals.map((a) => (
                        <li key={a.id} className="rounded-lg border p-2.5 text-[11.5px]" style={{ borderColor: "var(--bp-border)" }}>
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-semibold capitalize">{a.decision.replace(/_/g, " ")}</span>
                            <span className="text-[10px] muted">{a.previous_status} → {a.new_status}</span>
                            <span className="ml-auto text-[10px] muted">{a.actor?.full_name} · {fmtDateTime(a.created_at)}</span>
                          </div>
                          {a.notes && <p className="mt-1 muted">{a.notes}</p>}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="card card-pad">
                  <h3 className="section-title flex items-center gap-2"><ClipboardCheck size={15} /> Record your decision</h3>
                  <div className="mt-3">
                    <Field label="Decision note" hint="Required. Stored with the decision-maker role, timestamp and previous status.">
                      <textarea className="textarea" rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Explain the decision, including any context the creator needs." />
                    </Field>
                  </div>
                  <label className={`mt-3 flex items-start gap-2 rounded-lg border p-2.5 text-[11.5px] ${needsOverride ? "" : "opacity-70"}`} style={{ borderColor: needsOverride ? "rgba(255,181,71,.45)" : "var(--bp-border)", background: needsOverride ? "rgba(255,181,71,.06)" : "transparent" }}>
                    <input type="checkbox" className="check mt-0.5" checked={override} onChange={(e) => setOverride(e.target.checked)} disabled={!needsOverride} />
                    <span>
                      <b>Override the AI recommendation</b>
                      <span className="block text-[10.5px] muted">
                        {needsOverride
                          ? `You are choosing “${confirmDecision === "approved" ? "Approve" : confirmDecision === "rejected" ? "Reject" : "Request changes"}” while the engine suggests “${recommendation?.label}”. The reason above will be recorded as an override.`
                          : "Selecting a decision that differs from the AI recommendation requires this confirmation and a reason."}
                      </span>
                    </span>
                  </label>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button className="btn btn-primary" disabled={saving} onClick={() => setConfirmDecision("approved")}><CheckCircle2 size={14} /> Approve</button>
                    <button className="btn btn-secondary" disabled={saving} onClick={() => setConfirmDecision("changes_requested")}>Request changes</button>
                    <button className="btn btn-danger" disabled={saving} onClick={() => setConfirmDecision("rejected")}><XCircle size={14} /> Reject</button>
                  </div>
                </div>
              </div>
            )}
          </section>
        </div>
      )}

      <section className="card mt-5 overflow-hidden">
        <div className="border-b px-4 py-3" style={{ borderColor: "var(--bp-border)" }}>
          <h2 className="section-title">Creator tasks awaiting approval</h2>
          <p className="text-[11px] muted">Task-level decisions are separate from content approval and are logged on the task.</p>
        </div>
        {awaitingTasks.length === 0 ? (
          <p className="p-4 text-[12.5px] muted">No tasks are waiting for a manager decision.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Task</th><th>Creator</th><th>Campaign</th><th>Status</th><th /></tr></thead>
              <tbody>
                {awaitingTasks.map((task) => (
                  <tr key={task.id}>
                    <td className="primary-cell">{task.title}</td>
                    <td>{task.creator_name}</td>
                    <td>{task.campaign_name}</td>
                    <td><Badge status={task.status} /></td>
                    <td>
                      <div className="flex justify-end gap-1.5">
                        <button className="btn btn-ghost btn-sm" disabled={saving} onClick={() => decideTask(task, "approved")}>Approve</button>
                        <button className="btn btn-ghost btn-sm" disabled={saving} onClick={() => decideTask(task, "changes_requested")}>Request changes</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <Confirm
        open={!!confirmDecision}
        onClose={() => setConfirmDecision(null)}
        onConfirm={decide}
        title={
          confirmDecision === "approved" ? "Approve this content?"
            : confirmDecision === "rejected" ? "Reject this content?"
              : "Request changes?"
        }
        body={
          confirmDecision === "approved"
            ? "Approval records your identity and reason. The creator will be notified and the content becomes approved for use in this workspace."
            : confirmDecision === "rejected"
              ? "The creator will be notified and the content will be marked rejected. Provide a clear reason above."
              : "The creator will be able to revise and resubmit the content for verification."
        }
        confirmLabel={confirmDecision === "approved" ? "Approve" : confirmDecision === "rejected" ? "Reject" : "Request changes"}
        danger={confirmDecision === "rejected"}
        error={error}
      />
    </div>
  );
}

function CountBox({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div className="rounded-lg border px-2.5 py-2" style={{ borderColor: "var(--bp-border)", background: "var(--bp-surface-inset)" }}>
      <p className="text-[9.5px] uppercase tracking-wide muted">{label}</p>
      <p className="mt-0.5 text-[18px] font-bold leading-none" style={{ color: color || "var(--bp-ink)" }}>{value}</p>
    </div>
  );
}
