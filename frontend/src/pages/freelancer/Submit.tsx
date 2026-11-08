import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { CheckCircle2, FileUp, Send, ShieldAlert, Sparkles } from "lucide-react";
import { api, ApiError } from "../../lib/api";
import type { Submission, Task } from "../../lib/types";
import { useSession } from "../../lib/session";
import { Badge, Empty, ErrorNote, Field, LoadingBlock, PageHeader } from "../../components/ui";

export default function SubmitPage() {
  const navigate = useNavigate();
  const { toast } = useSession();
  const [params] = useSearchParams();
  const preselect = params.get("task") || "";
  const [tasks, setTasks] = useState<Task[]>([]);
  const [taskId, setTaskId] = useState(preselect);
  const [loading, setLoading] = useState(true);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [mode, setMode] = useState<"text" | "file">("text");
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const data = await api<{ items: Task[] }>("/tasks");
        setTasks(data.items.filter((t) => !["approved", "completed"].includes(t.status)));
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Tasks could not be loaded.");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  const selected = useMemo(() => tasks.find((t) => t.id === taskId) || null, [tasks, taskId]);

  useEffect(() => {
    if (selected) {
      setTitle((current) => current || `${selected.title} — copy`);
    }
  }, [selected]);

  const submit = async () => {
    setError("");
    if (!selected) { setError("Select the assigned task this content belongs to."); return; }
    if (!title.trim()) { setError("Give the submission a title."); return; }
    try {
      setSubmitting(true);
      let result: Submission;
      if (mode === "file") {
        if (!file) throw new ApiError("Choose a document to upload.", 422);
        const form = new FormData();
        form.append("file", file);
        form.append("title", title.trim());
        form.append("content_type", selected.brief?.content_type || "advertisement");
        form.append("campaign", selected.campaign_name);
        form.append("product", selected.brief?.product || "");
        form.append("submit_now", "true");
        form.append("analyze_now", "true");
        result = await api<Submission>("/content/submissions/upload", { method: "POST", body: form });
      } else {
        if (text.trim().length < 10) throw new ApiError("Write or paste at least a sentence of content.", 422);
        result = await api<Submission>("/content/submissions", {
          method: "POST",
          body: {
            title: title.trim(),
            content_type: selected.brief?.content_type || "advertisement",
            campaign: selected.campaign_name,
            product: selected.brief?.product || "",
            text,
            submit_now: true,
            analyze_now: true,
          },
        });
      }
      try {
        await api(`/tasks/${selected.id}/status`, {
          method: "PATCH",
          body: {
            status: selected.submission_id ? "resubmitted" : "submitted",
            notes: "Content submitted for verification by the creator.",
            submission_id: result.id,
          },
        });
      } catch {
        // The submission exists even if the task status sync fails; surface it as a warning.
        toast("err", "Content saved, but the task status could not be updated.");
      }
      toast("ok", "Content submitted and verified. Review the feedback now.");
      navigate(`/submissions/${result.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The submission failed.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow="Submit against your brief"
        title="Submit Content"
        subtitle="Choose your assigned task, write or upload the deliverable, then submit it for automatic verification against approved brand knowledge."
      />

      {error && <div className="mb-4"><ErrorNote message={error} /></div>}

      {loading ? (
        <LoadingBlock label="Loading your tasks…" />
      ) : tasks.length === 0 ? (
        <Empty
          title="No open tasks to submit against"
          hint="You can submit content once your manager assigns a campaign task. Contact your brand manager if you expected a task."
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1fr_1.35fr]">
          <div className="space-y-4">
            <section className="card card-pad">
              <h2 className="section-title">1. Choose the task</h2>
              <div className="mt-3 space-y-2">
                {tasks.map((task) => (
                  <button
                    key={task.id}
                    onClick={() => { setTaskId(task.id); setTitle(""); }}
                    className={`w-full rounded-lg border p-3 text-left transition-colors ${taskId === task.id ? "bg-[rgba(139,92,246,.08)]" : "hover:bg-[var(--bp-hover-subtle)]"}`}
                    style={{ borderColor: taskId === task.id ? "rgba(139,92,246,.45)" : "var(--bp-border)" }}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-[12.5px] font-semibold">{task.title}</p>
                      <Badge status={task.status} />
                    </div>
                    <p className="mt-0.5 text-[10.5px] muted">{task.campaign_name} · {task.brief?.content_type?.replace(/_/g, " ")}</p>
                    {task.submission_id && <p className="mt-1 text-[10px]" style={{ color: "var(--bp-warning)" }}>A submission already exists — submitting again will create a revision.</p>}
                  </button>
                ))}
              </div>
            </section>

            {selected && (
              <section className="card card-pad">
                <h2 className="section-title">Brief reminders</h2>
                <div className="mt-3 space-y-2.5">
                  <div className="rounded-lg border p-2.5" style={{ borderColor: "rgba(0,201,154,.22)", background: "rgba(0,201,154,.04)" }}>
                    <p className="eyebrow flex items-center gap-1.5" style={{ color: "#62ddc0" }}><CheckCircle2 size={11} /> Approved claims</p>
                    <p className="mt-1 whitespace-pre-wrap text-[11px] leading-relaxed">{selected.brief?.approved_claims || "Only use claims approved in the campaign brief."}</p>
                  </div>
                  <div className="rounded-lg border p-2.5" style={{ borderColor: "rgba(255,91,112,.22)", background: "rgba(255,91,112,.04)" }}>
                    <p className="eyebrow flex items-center gap-1.5" style={{ color: "#ff8b9a" }}><ShieldAlert size={11} /> Prohibited</p>
                    <p className="mt-1 whitespace-pre-wrap text-[11px] leading-relaxed">{selected.brief?.prohibited_claims || "No unverified superlatives or comparisons."}</p>
                  </div>
                  {selected.brief?.mandatory_messages && (
                    <p className="text-[11px]"><b>Required message:</b> {selected.brief.mandatory_messages}</p>
                  )}
                </div>
              </section>
            )}
          </div>

          <section className="card card-pad self-start">
            <h2 className="section-title">2. Your content</h2>
            <div className="mt-3 space-y-3">
              <Field label="Submission title">
                <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Instagram Story ad copy" />
              </Field>
              <div className="flex gap-2">
                <button className={`btn ${mode === "text" ? "btn-primary" : "btn-secondary"}`} onClick={() => setMode("text")}>Write / paste</button>
                <button className={`btn ${mode === "file" ? "btn-primary" : "btn-secondary"}`} onClick={() => setMode("file")}>Upload file</button>
              </div>

              {mode === "text" ? (
                <Field label="Content" hint="Everything you write is compared with approved company evidence. Unsupported statements will be flagged, not silently accepted.">
                  <textarea className="textarea" rows={12} value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste or write your final copy here…" />
                </Field>
              ) : (
                <Field label="Content file" hint="PDF, DOCX, TXT or MD. The real text is extracted. Image OCR is only used when available on the server.">
                  <input type="file" className="input" accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg" onChange={(e) => setFile(e.target.files?.[0] || null)} />
                  {selected && <p className="field-hint">Campaign: {selected.campaign_name}</p>}
                </Field>
              )}

              <div className="flex items-start gap-2 rounded-lg border p-3 text-[11px]" style={{ borderColor: "var(--bp-border)" }}>
                <Sparkles size={14} className="mt-0.5 shrink-0" style={{ color: "#b9a5ff" }} />
                <span className="muted">
                  Submitting runs verification immediately. You will see each claim's classification, explanation,
                  evidence and suggested correction. Nothing is published until your manager approves it.
                </span>
              </div>

              <div className="flex justify-end gap-2">
                <button className="btn btn-secondary" onClick={() => navigate("/tasks")}>Cancel</button>
                <button className="btn btn-primary" onClick={submit} disabled={submitting || !selected}>
                  <Send size={14} /> {submitting ? "Submitting & verifying…" : "Submit for verification"}
                </button>
              </div>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
