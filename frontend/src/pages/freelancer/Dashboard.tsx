import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle, ArrowRight, CalendarDays, CheckCircle2, ClipboardList, Clock,
  FileSearch, Send, Sparkles, XCircle,
} from "lucide-react";
import { api, ApiError } from "../../lib/api";
import { useSession } from "../../lib/session";
import type { Campaign, Page, Submission, Task } from "../../lib/types";
import { Badge, Empty, ErrorNote, LoadingBlock, PageHeader, Stat, fmtDate, timeAgo } from "../../components/ui";

export default function FreelancerDashboard() {
  const { user } = useSession();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const [taskList, subs, camp] = await Promise.all([
          api<{ items: Task[] }>("/tasks"),
          api<Page<Submission>>("/content/submissions?page_size=100"),
          api<{ items: Campaign[] }>("/campaigns"),
        ]);
        setTasks(taskList.items);
        setSubmissions(subs.items);
        setCampaigns(camp.items);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Your dashboard could not be loaded.");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  const pendingTasks = tasks.filter((t) => !["approved", "completed", "rejected"].includes(t.status));
  const changes = submissions.filter((s) => s.status === "changes_requested");
  const approved = submissions.filter((s) => s.status === "approved");
  const rejected = submissions.filter((s) => s.status === "rejected");
  const readyToSubmit = tasks.filter((t) => ["assigned", "accepted", "in_progress", "changes_requested"].includes(t.status));

  const nextDeadline = useMemo(() => {
    const upcoming = pendingTasks
      .filter((t) => t.deadline)
      .map((t) => ({ task: t, date: new Date(t.deadline as string).getTime() }))
      .filter((item) => !Number.isNaN(item.date))
      .sort((a, b) => a.date - b.date);
    return upcoming[0] || null;
  }, [pendingTasks]);

  const firstName = user?.full_name?.split(" ")[0] || "there";

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow="Creator workspace"
        title={`Hello, ${firstName}.`}
        subtitle="Your assigned work, deadlines, and verification feedback. Content is checked against the same approved brand knowledge your manager maintains."
        actions={<Link to="/submit" className="btn btn-primary"><Send size={14} /> Submit content</Link>}
      />

      {error && <div className="mb-4"><ErrorNote message={error} /></div>}

      {loading ? (
        <LoadingBlock label="Loading your assignments…" />
      ) : (
        <>
          <div className="mb-5 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
            <Stat label="Assigned campaigns" value={campaigns.length} />
            <Stat label="Open tasks" value={pendingTasks.length} sub={`${readyToSubmit.length} waiting for content`} />
            <Stat label="Pending corrections" value={changes.length} color="var(--bp-warning)" />
            <Stat label="Approved submissions" value={approved.length} color="var(--bp-success)" />
            <Stat label="Rejected submissions" value={rejected.length} color="var(--bp-danger)" />
          </div>

          {nextDeadline && (
            <div className="mb-5 flex flex-wrap items-center gap-3 rounded-xl border px-4 py-3" style={{ borderColor: "rgba(6,214,240,.25)", background: "rgba(6,214,240,.05)" }}>
              <Clock size={16} style={{ color: "var(--bp-cyan)" }} />
              <p className="text-[12.5px]">
                Next deadline: <b>{nextDeadline.task.title}</b> · {fmtDate(nextDeadline.task.deadline)}
              </p>
              <Link to={`/tasks/${nextDeadline.task.id}`} className="btn btn-cyan btn-sm ml-auto">Open task <ArrowRight size={12} /></Link>
            </div>
          )}

          <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
            <section className="card overflow-hidden">
              <div className="flex items-center justify-between gap-2 border-b px-4 py-3.5" style={{ borderColor: "var(--bp-border)" }}>
                <h2 className="section-title flex items-center gap-2"><ClipboardList size={15} /> My tasks</h2>
                <Link to="/tasks" className="text-[11px] font-semibold" style={{ color: "var(--bp-cyan)" }}>View all</Link>
              </div>
              {tasks.length === 0 ? (
                <div className="p-5">
                  <Empty title="No tasks assigned yet" hint="Your manager will assign campaign tasks here. Once assigned, open the brief to see the approved claims and requirements." />
                </div>
              ) : (
                <div className="divide-y" style={{ borderColor: "var(--bp-border)" }}>
                  {tasks.slice(0, 5).map((task) => (
                    <Link key={task.id} to={`/tasks/${task.id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-[var(--bp-hover-subtle)]">
                      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg" style={{ background: "var(--bp-surface-inset)", color: "var(--bp-muted)" }}>
                        <ClipboardList size={14} />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[12.5px] font-medium">{task.title}</span>
                        <span className="block truncate text-[10.5px] muted">{task.campaign_name} · due {fmtDate(task.deadline)}</span>
                      </span>
                      <Badge status={task.status} />
                    </Link>
                  ))}
                </div>
              )}
            </section>

            <div className="space-y-4">
              <section className="card card-pad">
                <div className="flex items-center justify-between gap-2">
                  <h2 className="section-title flex items-center gap-2"><AlertTriangle size={15} style={{ color: "var(--bp-warning)" }} /> Pending corrections</h2>
                  <Link to="/feedback" className="text-[11px]" style={{ color: "var(--bp-cyan)" }}>Feedback</Link>
                </div>
                {changes.length === 0 ? (
                  <p className="mt-2 text-[12px] muted">No corrections are waiting. New feedback will appear here after verification.</p>
                ) : (
                  <ul className="mt-3 space-y-2">
                    {changes.slice(0, 4).map((submission) => (
                      <li key={submission.id}>
                        <Link to={`/submissions/${submission.id}`} className="flex items-center justify-between gap-2 rounded-lg border px-2.5 py-2 hover:border-[#435878]" style={{ borderColor: "var(--bp-border)" }}>
                          <span className="min-w-0 truncate text-[12px]">{submission.title}</span>
                          <span className="shrink-0"><Badge status={submission.status} /></span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section className="card card-pad">
                <h2 className="section-title flex items-center gap-2"><CalendarDays size={15} /> Assigned campaigns</h2>
                {campaigns.length === 0 ? (
                  <p className="mt-2 text-[12px] muted">You are not assigned to a campaign yet.</p>
                ) : (
                  <ul className="mt-3 space-y-2.5">
                    {campaigns.map((campaign) => (
                      <li key={campaign.id} className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="truncate text-[12px] font-medium">{campaign.name}</p>
                          <p className="text-[10.5px] muted">Due {fmtDate(campaign.deadline)}</p>
                        </div>
                        <Badge status={campaign.status} />
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <section className="card overflow-hidden">
              <div className="flex items-center justify-between gap-2 border-b px-4 py-3.5" style={{ borderColor: "var(--bp-border)" }}>
                <h2 className="section-title">Recent submissions</h2>
                <Link to="/submissions" className="text-[11px] font-semibold" style={{ color: "var(--bp-cyan)" }}>All submissions</Link>
              </div>
              {submissions.length === 0 ? (
                <p className="p-4 text-[12.5px] muted">You have not submitted content yet.</p>
              ) : (
                <div className="divide-y" style={{ borderColor: "var(--bp-border)" }}>
                  {submissions.slice(0, 5).map((submission) => (
                    <Link key={submission.id} to={`/submissions/${submission.id}`} className="flex items-center justify-between gap-2 px-4 py-2.5 hover:bg-[var(--bp-hover-subtle)]">
                      <span className="min-w-0">
                        <span className="block truncate text-[12px]">{submission.title}</span>
                        <span className="block text-[10px] muted">{timeAgo(submission.updated_at)} · {submission.campaign || "No campaign"}</span>
                      </span>
                      <Badge status={submission.status} />
                    </Link>
                  ))}
                </div>
              )}
            </section>

            <section className="card card-pad">
              <h2 className="section-title flex items-center gap-2"><Sparkles size={15} style={{ color: "#b9a5ff" }} /> How to get content approved</h2>
              <ol className="mt-3 space-y-2.5 text-[12px] text-secondary">
                <li className="flex gap-2"><span className="font-bold" style={{ color: "#b9a5ff" }}>1.</span> Open the task and read the campaign brief and approved claims.</li>
                <li className="flex gap-2"><span className="font-bold" style={{ color: "#b9a5ff" }}>2.</span> Submit your copy. Each factual claim is checked against approved company evidence.</li>
                <li className="flex gap-2"><span className="font-bold" style={{ color: "#b9a5ff" }}>3.</span> Read the feedback: contradicted, unsupported and inconclusive claims each include an explanation.</li>
                <li className="flex gap-2"><span className="font-bold" style={{ color: "#b9a5ff" }}>4.</span> Revise and resubmit. Your manager makes the final approval decision.</li>
              </ol>
              <div className="mt-3 flex flex-wrap gap-2">
                <Link to="/tasks" className="btn btn-secondary btn-sm"><ClipboardList size={13} /> My tasks</Link>
                <Link to="/feedback" className="btn btn-secondary btn-sm"><FileSearch size={13} /> Review feedback</Link>
              </div>
            </section>
          </div>

          {approved.length > 0 && (
            <div className="mt-4 flex items-start gap-2 rounded-xl border px-4 py-3 text-[12px]" style={{ borderColor: "rgba(0,201,154,.25)", background: "rgba(0,201,154,.05)" }}>
              <CheckCircle2 size={15} className="mt-0.5 shrink-0" style={{ color: "var(--bp-success)" }} />
              <span>{approved.length} of your submissions {approved.length === 1 ? "has" : "have"} been approved by the brand team. Approved content is listed under My Submissions.</span>
            </div>
          )}
          {rejected.length > 0 && (
            <div className="mt-2 flex items-start gap-2 rounded-xl border px-4 py-3 text-[12px]" style={{ borderColor: "rgba(255,91,112,.22)", background: "rgba(255,91,112,.05)" }}>
              <XCircle size={15} className="mt-0.5 shrink-0" style={{ color: "var(--bp-danger)" }} />
              <span>{rejected.length} submission{rejected.length === 1 ? " was" : "s were"} rejected. Open the submission to read the manager's reason, then contact your manager before resubmitting.</span>
            </div>
          )}
        </>
      )}
    </div>
  );
}
