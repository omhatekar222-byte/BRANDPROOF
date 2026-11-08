import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  AlertTriangle, ArrowRight, BriefcaseBusiness, CheckCircle2, ClipboardList,
  Database, FileSearch, Plus, RefreshCw, ShieldCheck, Sparkles,
} from "lucide-react";
import { api, ApiError } from "../../lib/api";
import { useSession } from "../../lib/session";
import type { Campaign, Dashboard, Finding, Member, Page, Submission, Task } from "../../lib/types";
import { Badge, ErrorNote, LoadingBlock, PageHeader, Stat, fmtDateTime, timeAgo } from "../../components/ui";

export default function OverviewPage() {
  const { user, org } = useSession();
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [approved, setApproved] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [dash, mem, camp, taskList, findingList, approvedList] = await Promise.all([
        api<Dashboard>("/analytics/dashboard"),
        api<Page<Member>>("/admin/members?page_size=100"),
        api<{ items: Campaign[] }>("/campaigns"),
        api<{ items: Task[] }>("/tasks"),
        api<Page<Finding>>("/review/findings?page_size=200"),
        api<Page<Submission>>("/content/submissions?status=approved&page_size=5"),
      ]);
      setDashboard(dash);
      setMembers(mem.items);
      setCampaigns(camp.items);
      setTasks(taskList.items);
      setFindings(findingList.items);
      setApproved(approvedList.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The overview could not be loaded.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const t = dashboard?.totals;
  const creators = members.filter((m) => m.role === "content_creator" && m.is_active);
  const activeCampaigns = campaigns.filter((c) => c.status === "active");
  const awaitingApproval = tasks.filter((task) => task.status === "awaiting_manager_approval");
  const highRisk = findings.filter(
    (f) => ["open", "accepted", "modified"].includes(f.status) && ["high", "critical"].includes(f.severity),
  );
  const recent = dashboard?.recent_activity || [];
  const pendingTasks = tasks.filter((task) => ["submitted", "ai_review_completed", "awaiting_manager_approval"].includes(task.status));
  const emptyWorkspace = (t?.submissions || 0) === 0 && (t?.claims_total || 0) === 0;

  const firstName = user?.full_name?.split(" ")[0] || "there";

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow={org?.is_demo ? "NovaTech demonstration workspace · demo data" : "Brand governance workspace"}
        title={`Welcome to BrandProof, ${firstName}.`}
        subtitle="Your central workspace for maintaining brand consistency, factual accuracy, and content quality. Every number below is read from stored workspace records."
        actions={
          <>
            <button className="btn btn-secondary" onClick={() => navigate("/knowledge?new=document")}>
              <Plus size={14} /> Add Brand Information
            </button>
            <button className="btn btn-secondary" onClick={() => navigate("/review?new=1")}>
              <FileSearch size={14} /> Review Content
            </button>
            <button className="btn btn-primary" onClick={() => navigate("/campaigns?new=1")}>
              <Plus size={14} /> Create Campaign
            </button>
          </>
        }
      />

      {error && <div className="mb-4"><ErrorNote message={error} /></div>}
      {loading && !dashboard ? (
        <LoadingBlock label="Reading workspace records…" />
      ) : (
        <>
          <div className="grid-stats mb-5">
            <Stat label="Registered creators" value={creators.length} sub={`${members.length} workspace members`} />
            <Stat label="Active campaigns" value={activeCampaigns.length} sub={`${campaigns.length} campaigns total`} />
            <Stat label="Total submissions" value={t?.submissions ?? 0} sub={`${t?.approved ?? 0} approved`} />
            <Stat label="Pending reviews" value={t?.pending_reviews ?? 0} sub="submitted or under review" color="var(--bp-warning)" />
            <Stat label="Awaiting approval" value={awaitingApproval.length} sub="manager decisions queued" color="var(--bp-cyan)" />
            <Stat label="High-risk findings" value={highRisk.length} sub={`${t?.claims_contradicted ?? 0} contradicted claims`} color="var(--bp-danger)" />
          </div>

          {emptyWorkspace && (
            <section className="card card-pad mb-5" style={{ borderColor: "rgba(139,92,246,.28)" }}>
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl" style={{ background: "var(--bp-violet-soft)", color: "#c1a8ff" }}>
                  <Sparkles size={18} />
                </span>
                <div>
                  <h2 className="section-title">Start with the company's source of truth</h2>
                  <p className="page-sub">
                    This workspace has no recorded knowledge or submissions yet. Add the company profile and
                    at least one approved claim with evidence, then submit content for verification. The AI
                    can only compare content against approved information that actually exists here.
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Link to="/knowledge?tab=profile" className="btn btn-primary">Set up company profile</Link>
                    <Link to="/knowledge?tab=claims&new=1" className="btn btn-secondary">Add approved claim</Link>
                    <Link to="/review?new=1" className="btn btn-secondary">Submit content</Link>
                  </div>
                </div>
              </div>
            </section>
          )}

          <div className="mb-5 grid gap-4 lg:grid-cols-[1.35fr_1fr]">
            <section className="card card-pad">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h2 className="section-title">Brand compliance overview</h2>
                  <p className="mt-0.5 text-[11.5px] muted">Classifications across every verified claim in this workspace.</p>
                </div>
                <button className="btn btn-ghost btn-icon" onClick={load} title="Refresh overview" aria-label="Refresh">
                  <RefreshCw size={14} />
                </button>
              </div>
              <ComplianceBar
                supported={t?.claims_supported ?? 0}
                contradicted={t?.claims_contradicted ?? 0}
                unsupported={t?.claims_unsupported ?? 0}
                inconclusive={t?.claims_inconclusive ?? 0}
              />
              <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
                <MiniStat label="Supported" value={t?.claims_supported ?? 0} color="var(--bp-success)" />
                <MiniStat label="Contradicted" value={t?.claims_contradicted ?? 0} color="var(--bp-danger)" />
                <MiniStat label="Unsupported" value={t?.claims_unsupported ?? 0} color="var(--bp-warning)" />
                <MiniStat label="Inconclusive" value={t?.claims_inconclusive ?? 0} color="var(--bp-cyan)" />
              </div>
              <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 border-t pt-3 text-[11px] muted" style={{ borderColor: "var(--bp-border)" }}>
                <span><b style={{ color: "var(--bp-ink)" }}>{t?.claims_total ?? 0}</b> claims checked</span>
                <span><b style={{ color: "var(--bp-ink)" }}>{t?.findings_open ?? 0}</b> open findings</span>
                <span><b style={{ color: "var(--bp-ink)" }}>{t?.findings_resolved ?? 0}</b> resolved</span>
              </div>
            </section>

            <section className="card card-pad">
              <h2 className="section-title flex items-center gap-2">
                <AlertTriangle size={15} style={{ color: "var(--bp-warning)" }} /> Needs your attention
              </h2>
              <div className="mt-3 space-y-2.5">
                <AttentionRow
                  icon={<FileSearch size={14} />}
                  label="Submissions awaiting review"
                  value={t?.pending_reviews ?? 0}
                  to="/review"
                />
                <AttentionRow
                  icon={<ShieldCheck size={14} />}
                  label="Tasks awaiting approval"
                  value={awaitingApproval.length}
                  to="/approvals"
                />
                <AttentionRow
                  icon={<AlertTriangle size={14} />}
                  label="High-risk findings open"
                  value={highRisk.length}
                  to="/review"
                />
                <AttentionRow
                  icon={<BrainCircuitIcon />}
                  label="Recurring issue groups"
                  value={t?.recurring_groups ?? 0}
                  to="/intelligence"
                />
                <AttentionRow
                  icon={<ClipboardList size={14} />}
                  label="Guideline proposals pending"
                  value={t?.proposals_pending ?? 0}
                  to="/intelligence"
                />
              </div>
              <button className="btn btn-primary mt-4 w-full" onClick={() => navigate("/approvals")}>
                Open Approval Centre <ArrowRight size={14} />
              </button>
            </section>
          </div>

          <div className="grid gap-4 lg:grid-cols-[1.35fr_1fr]">
            <section className="card overflow-hidden">
              <div className="flex items-center justify-between gap-3 border-b px-5 py-4" style={{ borderColor: "var(--bp-border)" }}>
                <h2 className="section-title">Recent activity</h2>
                <Link to="/review" className="text-[11px] font-semibold" style={{ color: "var(--bp-cyan)" }}>View all submissions</Link>
              </div>
              {recent.length === 0 ? (
                <div className="p-5">
                  <p className="text-[12.5px] muted">
                    No submissions yet. Once content is submitted, verification outcomes and decisions appear here.
                  </p>
                </div>
              ) : (
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr><th>Submission</th><th>Type</th><th>Status</th><th>Last updated</th></tr>
                    </thead>
                    <tbody>
                      {recent.slice(0, 7).map((row) => (
                        <tr key={row.id}>
                          <td className="primary-cell">
                            <Link to={`/review/${row.id}`} className="hover:underline">{row.title}</Link>
                          </td>
                          <td className="capitalize">{row.content_type.replace(/_/g, " ")}</td>
                          <td><Badge status={row.status} /></td>
                          <td className="text-[11.5px] muted">{timeAgo(row.updated_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <div className="space-y-4">
              <section className="card card-pad">
                <h2 className="section-title">Pending manager decisions</h2>
                {awaitingApproval.length === 0 && pendingTasks.length === 0 ? (
                  <p className="mt-2 text-[12.5px] muted">No submissions are waiting for a final decision.</p>
                ) : (
                  <ul className="mt-3 space-y-2.5">
                    {pendingTasks.slice(0, 4).map((task) => (
                      <li key={task.id} className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="truncate text-[12px] font-medium">{task.title}</p>
                          <p className="truncate text-[10.5px] muted">{task.creator_name} · {task.campaign_name}</p>
                        </div>
                        <Badge status={task.status} />
                      </li>
                    ))}
                  </ul>
                )}
                <Link to="/approvals" className="btn btn-secondary mt-3 w-full">Review approvals</Link>
              </section>

              <section className="card card-pad">
                <h2 className="section-title">Recently approved content</h2>
                {approved.length === 0 ? (
                  <p className="mt-2 text-[12.5px] muted">Approved content will be listed here with its reviewer and date.</p>
                ) : (
                  <ul className="mt-3 space-y-2.5">
                    {approved.map((s) => (
                      <li key={s.id} className="flex items-start justify-between gap-2">
                        <Link to={`/review/${s.id}`} className="min-w-0 truncate text-[12px] hover:underline">{s.title}</Link>
                        <span className="shrink-0 text-[10px] muted">{fmtDateTime(s.approved_at)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>
          </div>

          <section className="card mt-4 overflow-hidden">
            <div className="flex items-center justify-between gap-3 border-b px-5 py-4" style={{ borderColor: "var(--bp-border)" }}>
              <div>
                <h2 className="section-title">High-risk findings</h2>
                <p className="mt-0.5 text-[11.5px] muted">Contradictions and serious guideline violations that remain open.</p>
              </div>
              <Link to="/intelligence" className="btn btn-secondary btn-sm"><Sparkles size={13} /> View patterns</Link>
            </div>
            {highRisk.length === 0 ? (
              <p className="p-5 text-[12.5px] muted">No high-risk findings are open. Findings appear here after content verification.</p>
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead><tr><th>Finding</th><th>Submission</th><th>Category</th><th>Severity</th><th>Status</th></tr></thead>
                  <tbody>
                    {highRisk.slice(0, 6).map((f) => (
                      <tr key={f.id}>
                        <td className="primary-cell max-w-[380px]">
                          <Link to={`/review/${f.submission_id}`} className="hover:underline">{f.title}</Link>
                        </td>
                        <td className="max-w-[220px] truncate">{f.submission_title}</td>
                        <td className="capitalize">{f.category.replace(/_/g, " ")}</td>
                        <td><Badge status={f.severity} /></td>
                        <td><Badge status={f.status} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="mt-4 grid gap-3 sm:grid-cols-3">
            <QuickAction icon={<Database size={16} />} title="Brand Knowledge" body="Company profile, approved claims, guidelines and evidence." to="/knowledge" />
            <QuickAction icon={<BriefcaseBusiness size={16} />} title="Campaigns" body="Assign creators and manage campaign-specific requirements." to="/campaigns" />
            <QuickAction icon={<CheckCircle2 size={16} />} title="Approval Centre" body="Make final human decisions independent of the AI result." to="/approvals" />
          </section>
        </>
      )}
    </div>
  );
}

function BrainCircuitIcon() {
  return <Sparkles size={14} />;
}

function MiniStat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="rounded-lg border p-2.5" style={{ borderColor: "var(--bp-border)", background: "var(--bp-surface-inset)" }}>
      <p className="text-[9.5px] font-semibold uppercase tracking-wide" style={{ color: "var(--bp-muted)" }}>{label}</p>
      <p className="mt-0.5 text-[18px] font-bold leading-none" style={{ color }}>{value}</p>
    </div>
  );
}

function ComplianceBar({ supported, contradicted, unsupported, inconclusive }: { supported: number; contradicted: number; unsupported: number; inconclusive: number }) {
  const total = supported + contradicted + unsupported + inconclusive;
  if (total === 0) {
    return <p className="text-[12.5px] muted">No claims have been verified yet. Submit content to produce classifications.</p>;
  }
  const parts = [
    { value: supported, color: "var(--bp-success)" },
    { value: contradicted, color: "var(--bp-danger)" },
    { value: unsupported, color: "var(--bp-warning)" },
    { value: inconclusive, color: "var(--bp-cyan)" },
  ];
  return (
    <div className="flex h-2.5 w-full overflow-hidden rounded-full" style={{ background: "#0d1729" }}>
      {parts.map((p, i) => p.value > 0 && (
        <div key={i} style={{ width: `${(p.value / total) * 100}%`, background: p.color }} title={`${p.value} of ${total}`} />
      ))}
    </div>
  );
}

function AttentionRow({ icon, label, value, to }: { icon: React.ReactNode; label: string; value: number; to: string }) {
  return (
    <Link to={to} className="flex items-center gap-2.5 rounded-lg px-1 py-1.5 hover:bg-[var(--bp-hover-notif)]">
      <span className="grid h-7 w-7 place-items-center rounded-lg" style={{ background: "var(--bp-surface-inset)", color: "var(--bp-muted)" }}>{icon}</span>
      <span className="flex-1 text-[12px] text-secondary">{label}</span>
      <span className="text-[13px] font-bold">{value}</span>
    </Link>
  );
}

function QuickAction({ icon, title, body, to }: { icon: React.ReactNode; title: string; body: string; to: string }) {
  return (
    <Link to={to} className="card card-pad hover-card block">
      <span className="mb-2 inline-flex" style={{ color: "#b9a5ff" }}>{icon}</span>
      <p className="text-[12.5px] font-semibold">{title}</p>
      <p className="mt-0.5 text-[11px] muted">{body}</p>
    </Link>
  );
}
