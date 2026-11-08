import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft, CalendarDays, CheckCircle2, FileText, Flag, Info, Send, ShieldAlert, Sparkles,
} from "lucide-react";
import { api, ApiError } from "../../lib/api";
import type { Task } from "../../lib/types";
import { useSession } from "../../lib/session";
import { Badge, ErrorNote, LoadingBlock, SuccessNote, fmtDate, fmtDateTime } from "../../components/ui";

export default function TaskDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const { toast } = useSession();
  const [task, setTask] = useState<Task | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setTask(await api<Task>(`/tasks/${id}`));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The task could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { void load(); }, [load]);

  const start = async () => {
    if (!task) return;
    setSaving(true);
    try {
      await api(`/tasks/${task.id}/status`, { method: "PATCH", body: { status: "in_progress", notes: "Creator started working on this task." } });
      setNotice("Task marked as in progress.");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The task could not be updated.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingBlock label="Loading task brief…" />;
  if (!task) {
    return (
      <div>
        <ErrorNote message={error || "Task not found."} />
        <button className="btn btn-secondary mt-4" onClick={() => navigate("/tasks")}><ArrowLeft size={14} /> Back to tasks</button>
      </div>
    );
  }

  const brief = task.brief;
  const canSubmit = !["approved", "completed"].includes(task.status);

  return (
    <div className="fade-in">
      <button className="btn btn-ghost btn-sm mb-3 -ml-2" onClick={() => navigate("/tasks")}><ArrowLeft size={14} /> Assigned Tasks</button>

      {notice && <div className="mb-4"><SuccessNote>{notice}</SuccessNote></div>}
      {error && <div className="mb-4"><ErrorNote message={error} /></div>}

      <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge status={task.status} />
            <Badge status={task.priority} label={`${task.priority} priority`} />
            <span className="text-[10.5px] muted">Assigned {fmtDate(task.created_at)}</span>
          </div>
          <h1 className="page-title mt-2">{task.title}</h1>
          <p className="page-sub">{task.campaign_name} · due {fmtDate(task.deadline)} · manager {task.manager_name || "Brand team"}</p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          {["assigned"].includes(task.status) && (
            <button className="btn btn-secondary" onClick={start} disabled={saving}>Start working</button>
          )}
          {task.submission_id && (
            <Link to={`/submissions/${task.submission_id}`} className="btn btn-secondary"><FileText size={14} /> View submission</Link>
          )}
          {canSubmit && (
            <Link to={`/submit?task=${task.id}`} className="btn btn-primary"><Send size={14} /> Submit content</Link>
          )}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.45fr_1fr]">
        <div className="space-y-4">
          <section className="card card-pad">
            <h2 className="section-title">Your instructions</h2>
            <p className="mt-2 whitespace-pre-wrap text-[12.5px] leading-relaxed text-secondary">
              {task.instructions || "No additional instructions were provided. Follow the campaign brief."}
            </p>
            {task.manager_notes && (
              <div className="mt-3 rounded-lg border p-3" style={{ borderColor: "rgba(255,181,71,.28)", background: "rgba(255,181,71,.05)" }}>
                <p className="eyebrow" style={{ color: "var(--bp-warning)" }}>Manager note</p>
                <p className="mt-1 text-[12px]">{task.manager_notes}</p>
              </div>
            )}
          </section>

          <section className="card card-pad">
            <h2 className="section-title flex items-center gap-2"><Info size={15} /> Campaign brief</h2>
            {!brief ? (
              <p className="mt-2 text-[12px] muted">No campaign brief is attached to this task.</p>
            ) : (
              <div className="mt-3 space-y-3">
                <Brief label="Objective" value={brief.objective} />
                <Brief label="Target audience" value={brief.target_audience} />
                <div className="grid gap-2 sm:grid-cols-2">
                  <Brief label="Platform" value={brief.platform} />
                  <Brief label="Content format" value={brief.content_type.replace(/_/g, " ")} />
                </div>
                <div className="rounded-lg border p-3" style={{ borderColor: "rgba(0,201,154,.24)", background: "rgba(0,201,154,.04)" }}>
                  <p className="eyebrow flex items-center gap-1.5" style={{ color: "#62ddc0" }}><CheckCircle2 size={11} /> Approved claims you may use</p>
                  <p className="mt-1 whitespace-pre-wrap text-[12px] leading-relaxed">{brief.approved_claims || "No campaign-specific claims listed. Only use approved brand knowledge."}</p>
                </div>
                <div className="rounded-lg border p-3" style={{ borderColor: "rgba(255,91,112,.24)", background: "rgba(255,91,112,.04)" }}>
                  <p className="eyebrow flex items-center gap-1.5" style={{ color: "#ff8b9a" }}><ShieldAlert size={11} /> Do not claim</p>
                  <p className="mt-1 whitespace-pre-wrap text-[12px] leading-relaxed">{brief.prohibited_claims || "Any superlative or comparison without approved evidence."}</p>
                </div>
                {brief.mandatory_messages && <Brief label="Required message" value={brief.mandatory_messages} />}
                {brief.cta && <Brief label="Call to action" value={brief.cta} />}
              </div>
            )}
          </section>
        </div>

        <div className="space-y-4">
          <section className="card card-pad">
            <h2 className="section-title flex items-center gap-2"><CalendarDays size={15} /> Task details</h2>
            <dl className="mt-3 space-y-2.5 text-[12px]">
              <Row label="Campaign" value={task.campaign_name} />
              <Row label="Deadline" value={fmtDate(task.deadline)} />
              <Row label="Priority" value={task.priority} />
              <Row label="Status" value={task.status.replace(/_/g, " ")} />
              <Row label="Last updated" value={fmtDateTime(task.updated_at)} />
            </dl>
          </section>

          {brief && brief.tone_of_voice && (
            <section className="card card-pad">
              <h2 className="section-title flex items-center gap-2"><Sparkles size={15} /> Tone of voice</h2>
              <p className="mt-2 text-[12px] leading-relaxed text-secondary">{brief.tone_of_voice}</p>
            </section>
          )}

          <section className="card card-pad">
            <h2 className="section-title flex items-center gap-2"><Flag size={15} /> Before you submit</h2>
            <ul className="mt-2 space-y-2 text-[11.5px] text-secondary">
              <li>• Only use claims supported by the campaign brief or approved knowledge.</li>
              <li>• Include any mandatory disclaimer exactly as written.</li>
              <li>• Remove superlatives that have no approved comparative evidence.</li>
              <li>• Your submission is verified automatically, then a human decides approval.</li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
}

function Brief({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="eyebrow">{label}</p>
      <p className="mt-0.5 whitespace-pre-wrap text-[12px] leading-relaxed text-secondary">{value || "Not specified"}</p>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="muted">{label}</dt>
      <dd className="text-right font-medium capitalize">{value}</dd>
    </div>
  );
}
