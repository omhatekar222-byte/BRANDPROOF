import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  BriefcaseBusiness, CalendarDays, ChevronRight, ClipboardList, Pencil, Plus, Send, UserPlus, Users,
} from "lucide-react";
import { api, ApiError } from "../../lib/api";
import { useSession } from "../../lib/session";
import type { Campaign, Member, Page, Submission, Task } from "../../lib/types";
import {
  Avatar, Badge, Empty, ErrorNote, Field, LoadingBlock, Modal, PageHeader, SuccessNote, fmtDate,
} from "../../components/ui";

const blankCampaign = {
  name: "", product: "", objective: "", target_audience: "", platform: "", content_type: "advertisement",
  description: "", approved_claims_text: "", prohibited_claims_text: "", mandatory_messages: "",
  tone_of_voice: "", cta: "", deadline: "", priority: "medium", status: "draft",
};

export default function CampaignsPage() {
  const { toast } = useSession();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [creators, setCreators] = useState<Member[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [form, setForm] = useState<null | typeof blankCampaign & { id?: string }>(null);
  const [selected, setSelected] = useState<Campaign | null>(null);
  const [saving, setSaving] = useState(false);
  const [taskCreator, setTaskCreator] = useState("");
  const [taskTitle, setTaskTitle] = useState("");
  const [taskInstructions, setTaskInstructions] = useState("");
  const [taskDeadline, setTaskDeadline] = useState("");
  const [taskPriority, setTaskPriority] = useState("medium");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [camp, members, taskList, subs] = await Promise.all([
        api<{ items: Campaign[] }>("/campaigns"),
        api<Page<Member>>("/admin/members?role=content_creator&page_size=100"),
        api<{ items: Task[] }>("/tasks"),
        api<Page<Submission>>("/content/submissions?page_size=200"),
      ]);
      setCampaigns(camp.items);
      setCreators(members.items);
      setTasks(taskList.items);
      setSubmissions(subs.items);
      if (selected) {
        const refreshed = camp.items.find((c) => c.id === selected.id);
        if (refreshed) setSelected(refreshed);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Campaigns could not be loaded.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const flash = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 4200);
  };

  const save = async () => {
    if (!form) return;
    if (!form.name.trim()) { setError("A campaign name is required."); return; }
    setSaving(true);
    setError("");
    try {
      const body = {
        ...form,
        deadline: form.deadline || null,
      };
      if (form.id) await api(`/campaigns/${form.id}`, { method: "PATCH", body });
      else await api("/campaigns", { method: "POST", body });
      setForm(null);
      await load();
      flash(form.id ? "Campaign updated." : "Campaign created. Assign creators to begin.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The campaign could not be saved.");
    } finally {
      setSaving(false);
    }
  };

  const assignTask = async () => {
    if (!selected) return;
    if (!taskCreator || !taskTitle.trim()) {
      setError("Choose a creator and give the task a title.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api(`/campaigns/${selected.id}/tasks`, {
        method: "POST",
        body: {
          creator_id: taskCreator,
          title: taskTitle.trim(),
          instructions: taskInstructions,
          priority: taskPriority,
          deadline: taskDeadline || null,
        },
      });
      setTaskTitle(""); setTaskInstructions(""); setTaskDeadline(""); setTaskCreator("");
      await load();
      flash("Task assigned to the creator.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The task could not be assigned.");
    } finally {
      setSaving(false);
    }
  };

  const setStatus = async (campaign: Campaign, status: string) => {
    setSaving(true);
    try {
      await api(`/campaigns/${campaign.id}`, { method: "PATCH", body: { status } });
      await load();
      flash(`Campaign marked ${status}.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Status update failed.");
    } finally {
      setSaving(false);
    }
  };

  const byCampaign = useMemo(() => {
    const map: Record<string, Submission[]> = {};
    for (const submission of submissions) {
      if (!submission.campaign) continue;
      (map[submission.campaign] ||= []).push(submission);
    }
    return map;
  }, [submissions]);

  const selectedTasks = selected ? tasks.filter((t) => t.campaign_id === selected.id) : [];
  const selectedSubs = selected ? byCampaign[selected.name] || [] : [];
  const selectedCreatorIds = new Set(selectedTasks.map((t) => t.creator_name));

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow="Organise work around a purpose"
        title="Campaigns"
        subtitle="Campaigns hold the brief, assigned creators, campaign-specific rules, and every submission made against them."
        actions={<button className="btn btn-primary" onClick={() => setForm({ ...blankCampaign })}><Plus size={14} /> Create campaign</button>}
      />

      {notice && <div className="mb-4"><SuccessNote>{notice}</SuccessNote></div>}
      {error && <div className="mb-4"><ErrorNote message={error} /></div>}

      {loading ? (
        <LoadingBlock label="Loading campaigns…" />
      ) : campaigns.length === 0 ? (
        <Empty
          title="No campaigns yet"
          hint="Create a campaign, add the approved claims and prohibited phrases, then assign it to a creator. Their submissions will be verified against the same knowledge."
          action={<button className="btn btn-primary" onClick={() => setForm({ ...blankCampaign })}>Create the first campaign</button>}
        />
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {campaigns.map((campaign) => {
            const subs = byCampaign[campaign.name] || [];
            const pending = subs.filter((s) => ["submitted", "under_review"].includes(s.status)).length;
            const approved = subs.filter((s) => s.status === "approved").length;
            const rejected = subs.filter((s) => s.status === "rejected").length;
            const campaignTasks = tasks.filter((t) => t.campaign_id === campaign.id);
            return (
              <article key={campaign.id} className="card card-pad hover-card flex flex-col">
                <div className="flex items-start justify-between gap-2">
                  <span className="grid h-9 w-9 place-items-center rounded-lg" style={{ background: "var(--bp-violet-soft)", color: "#c1a8ff" }}>
                    <BriefcaseBusiness size={16} />
                  </span>
                  <div className="flex gap-1">
                    <Badge status={campaign.status} />
                    <button className="btn btn-ghost btn-icon" aria-label="Edit campaign" onClick={() => setForm({
                      name: campaign.name, product: campaign.product, objective: campaign.objective,
                      target_audience: campaign.target_audience, platform: campaign.platform,
                      content_type: campaign.content_type, description: campaign.description,
                      approved_claims_text: campaign.approved_claims_text,
                      prohibited_claims_text: campaign.prohibited_claims_text,
                      mandatory_messages: campaign.mandatory_messages, tone_of_voice: campaign.tone_of_voice,
                      cta: campaign.cta, deadline: campaign.deadline ? campaign.deadline.slice(0, 16) : "",
                      priority: campaign.priority, status: campaign.status, id: campaign.id,
                    })}>
                      <Pencil size={13} />
                    </button>
                  </div>
                </div>
                <h2 className="mt-3 text-[14px] font-semibold">{campaign.name}</h2>
                <p className="mt-1 line-clamp-2 text-[11.5px] leading-relaxed muted">{campaign.objective || campaign.description || "No brief written yet."}</p>
                <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-[10.5px] muted">
                  <span className="flex items-center gap-1"><Users size={11} /> {campaignTasks.length} assigned task{campaignTasks.length === 1 ? "" : "s"}</span>
                  <span className="flex items-center gap-1"><ClipboardList size={11} /> {subs.length} submission{subs.length === 1 ? "" : "s"}</span>
                  <span className="flex items-center gap-1"><CalendarDays size={11} /> {fmtDate(campaign.deadline)}</span>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-1.5">
                  <MiniCount label="Pending" value={pending} color="var(--bp-warning)" />
                  <MiniCount label="Approved" value={approved} color="var(--bp-success)" />
                  <MiniCount label="Rejected" value={rejected} color="var(--bp-danger)" />
                </div>
                <button className="btn btn-secondary mt-3 w-full" onClick={() => setSelected(campaign)}>
                  Open campaign <ChevronRight size={13} />
                </button>
              </article>
            );
          })}
        </div>
      )}

      {/* campaign create / edit */}
      <Modal
        open={!!form}
        onClose={() => setForm(null)}
        title={form?.id ? "Edit campaign" : "Create campaign"}
        wide
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setForm(null)}>Cancel</button>
            <button className="btn btn-primary" onClick={save} disabled={saving}>{saving ? "Saving…" : "Save campaign"}</button>
          </>
        }
      >
        {form && (
          <div className="grid gap-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Campaign name" className="sm:col-span-2">
                <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Summer Product Launch" />
              </Field>
              <Field label="Product">
                <input className="input" value={form.product} onChange={(e) => setForm({ ...form, product: e.target.value })} />
              </Field>
              <Field label="Content type">
                <select className="select" value={form.content_type} onChange={(e) => setForm({ ...form, content_type: e.target.value })}>
                  {["advertisement", "social_post", "product_description", "email", "landing_page", "press_release"].map((c) => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}
                </select>
              </Field>
              <Field label="Platform">
                <input className="input" value={form.platform} onChange={(e) => setForm({ ...form, platform: e.target.value })} placeholder="Instagram, LinkedIn…" />
              </Field>
              <Field label="Target audience">
                <input className="input" value={form.target_audience} onChange={(e) => setForm({ ...form, target_audience: e.target.value })} />
              </Field>
              <Field label="Objective" className="sm:col-span-2">
                <textarea className="textarea" rows={2} value={form.objective} onChange={(e) => setForm({ ...form, objective: e.target.value })} />
              </Field>
              <Field label="Campaign description" className="sm:col-span-2">
                <textarea className="textarea" rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
              </Field>
              <Field label="Approved claims for creators" className="sm:col-span-2" hint="Only claims already approved in Brand Knowledge should be copied here.">
                <textarea className="textarea" rows={3} value={form.approved_claims_text} onChange={(e) => setForm({ ...form, approved_claims_text: e.target.value })} />
              </Field>
              <Field label="Prohibited claims" className="sm:col-span-2">
                <textarea className="textarea" rows={2} value={form.prohibited_claims_text} onChange={(e) => setForm({ ...form, prohibited_claims_text: e.target.value })} />
              </Field>
              <Field label="Mandatory messages">
                <input className="input" value={form.mandatory_messages} onChange={(e) => setForm({ ...form, mandatory_messages: e.target.value })} />
              </Field>
              <Field label="Tone of voice">
                <input className="input" value={form.tone_of_voice} onChange={(e) => setForm({ ...form, tone_of_voice: e.target.value })} />
              </Field>
              <Field label="Call to action">
                <input className="input" value={form.cta} onChange={(e) => setForm({ ...form, cta: e.target.value })} />
              </Field>
              <Field label="Deadline">
                <input type="datetime-local" className="input" value={form.deadline} onChange={(e) => setForm({ ...form, deadline: e.target.value })} />
              </Field>
              <Field label="Priority">
                <select className="select" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
                  {["low", "medium", "high", "urgent"].map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </Field>
              <Field label="Status">
                <select className="select" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                  {["draft", "active", "completed", "cancelled"].map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </Field>
            </div>
          </div>
        )}
      </Modal>

      {/* campaign detail */}
      <Modal
        open={!!selected}
        onClose={() => setSelected(null)}
        title={selected?.name || "Campaign"}
        wide
        footer={
          selected && (
            <>
              <button className="btn btn-secondary" onClick={() => setStatus(selected, selected.status === "active" ? "completed" : "active")} disabled={saving}>
                Mark {selected.status === "active" ? "completed" : "active"}
              </button>
              <button className="btn btn-primary" onClick={() => setSelected(null)}>Done</button>
            </>
          )
        }
      >
        {selected && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge status={selected.status} />
              <Badge status={selected.priority} label={`${selected.priority} priority`} />
              <span className="text-[11px] muted">{selected.platform || "No platform"} · deadline {fmtDate(selected.deadline)}</span>
            </div>

            <section className="grid gap-2 sm:grid-cols-3">
              <InfoTile label="Tasks assigned" value={selectedTasks.length} />
              <InfoTile label="Submissions" value={selectedSubs.length} />
              <InfoTile label="Creators" value={selectedCreatorIds.size} />
            </section>

            <section>
              <h3 className="section-title mb-2">Campaign brief</h3>
              <div className="grid gap-2 sm:grid-cols-2">
                <BriefField label="Objective" value={selected.objective} />
                <BriefField label="Target audience" value={selected.target_audience} />
                <BriefField label="Approved claims" value={selected.approved_claims_text} />
                <BriefField label="Prohibited claims" value={selected.prohibited_claims_text} />
                <BriefField label="Mandatory message" value={selected.mandatory_messages} />
                <BriefField label="Tone / CTA" value={[selected.tone_of_voice, selected.cta].filter(Boolean).join(" · ")} />
              </div>
            </section>

            <section>
              <h3 className="section-title mb-2 flex items-center gap-2"><Users size={14} /> Assigned tasks</h3>
              {selectedTasks.length === 0 ? (
                <p className="text-[12px] muted">No tasks assigned yet. Use the form below to assign a creator.</p>
              ) : (
                <div className="table-wrap rounded-lg border" style={{ borderColor: "var(--bp-border)" }}>
                  <table className="table">
                    <thead><tr><th>Task</th><th>Creator</th><th>Status</th><th>Deadline</th></tr></thead>
                    <tbody>
                      {selectedTasks.map((task) => (
                        <tr key={task.id}>
                          <td className="primary-cell">{task.title}</td>
                          <td>{task.creator_name}</td>
                          <td><Badge status={task.status} /></td>
                          <td className="text-[11px] muted">{fmtDate(task.deadline)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section className="rounded-xl border p-3.5" style={{ borderColor: "var(--bp-border)", background: "var(--bp-surface-inset)" }}>
              <h3 className="text-[12.5px] font-semibold flex items-center gap-2"><UserPlus size={14} /> Assign a creator</h3>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <Field label="Creator">
                  <select className="select" value={taskCreator} onChange={(e) => setTaskCreator(e.target.value)}>
                    <option value="">Select a creator…</option>
                    {creators.map((creator) => (
                      <option key={creator.user_id} value={creator.user_id}>{creator.full_name} · {creator.title}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Task title">
                  <input className="input" value={taskTitle} onChange={(e) => setTaskTitle(e.target.value)} placeholder="e.g. Instagram launch copy" />
                </Field>
                <Field label="Instructions" className="sm:col-span-2">
                  <textarea className="textarea" rows={2} value={taskInstructions} onChange={(e) => setTaskInstructions(e.target.value)} />
                </Field>
                <Field label="Deadline">
                  <input type="datetime-local" className="input" value={taskDeadline} onChange={(e) => setTaskDeadline(e.target.value)} />
                </Field>
                <Field label="Priority">
                  <select className="select" value={taskPriority} onChange={(e) => setTaskPriority(e.target.value)}>
                    {["low", "medium", "high", "urgent"].map((p) => <option key={p} value={p}>{p}</option>)}
                  </select>
                </Field>
              </div>
              <div className="mt-3 flex justify-end">
                <button className="btn btn-primary btn-sm" onClick={assignTask} disabled={saving}><Send size={13} /> Assign task</button>
              </div>
            </section>

            <section>
              <h3 className="section-title mb-2">Campaign submissions</h3>
              {selectedSubs.length === 0 ? (
                <p className="text-[12px] muted">No content has been submitted under this campaign yet.</p>
              ) : (
                <div className="space-y-1.5">
                  {selectedSubs.map((sub) => (
                    <Link key={sub.id} to={`/review/${sub.id}`} onClick={() => setSelected(null)} className="flex items-center justify-between gap-2 rounded-lg border px-3 py-2 hover:border-[#435878]" style={{ borderColor: "var(--bp-border)" }}>
                      <span className="min-w-0 truncate text-[12px]">{sub.title}</span>
                      <span className="flex shrink-0 items-center gap-2">
                        <span className="text-[10.5px] muted">{sub.submitted_by?.full_name}</span>
                        <Badge status={sub.status} />
                      </span>
                    </Link>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </Modal>
    </div>
  );
}

function MiniCount({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="rounded-lg border px-2 py-1.5 text-center" style={{ borderColor: "var(--bp-border)", background: "var(--bp-surface-inset)" }}>
      <p className="text-[9px] uppercase tracking-wide muted">{label}</p>
      <p className="text-[14px] font-bold leading-tight" style={{ color }}>{value}</p>
    </div>
  );
}

function InfoTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border px-3 py-2" style={{ borderColor: "var(--bp-border)", background: "var(--bp-surface-inset)" }}>
      <p className="eyebrow">{label}</p>
      <p className="mt-0.5 text-[18px] font-bold leading-none">{value}</p>
    </div>
  );
}

function BriefField({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border p-2.5" style={{ borderColor: "var(--bp-border)" }}>
      <p className="eyebrow">{label}</p>
      <p className="mt-1 whitespace-pre-wrap text-[11.5px] leading-relaxed text-secondary">{value || "Not specified"}</p>
    </div>
  );
}
