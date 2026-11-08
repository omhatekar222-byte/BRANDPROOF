import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ClipboardList, Search, Send } from "lucide-react";
import { api, ApiError } from "../../lib/api";
import type { Task } from "../../lib/types";
import { Badge, Empty, ErrorNote, LoadingBlock, PageHeader, fmtDate } from "../../components/ui";

const FILTERS = [
  { value: "open", label: "Open" },
  { value: "submitted", label: "Submitted" },
  { value: "approved", label: "Completed" },
  { value: "all", label: "All" },
];

export default function TasksPage() {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [filter, setFilter] = useState("open");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const data = await api<{ items: Task[] }>("/tasks");
        setTasks(data.items);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Tasks could not be loaded.");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    return tasks.filter((task) => {
      if (term && !(task.title + " " + task.campaign_name + " " + task.instructions).toLowerCase().includes(term)) return false;
      if (filter === "all") return true;
      if (filter === "open") return !["approved", "completed", "rejected"].includes(task.status);
      if (filter === "submitted") return ["submitted", "resubmitted", "ai_review_completed", "awaiting_manager_approval", "changes_requested"].includes(task.status);
      if (filter === "approved") return ["approved", "completed"].includes(task.status);
      return true;
    });
  }, [tasks, filter, query]);

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow="Work assigned to you"
        title="Assigned Tasks"
        subtitle="Each task includes the campaign brief, required format, relevant approved claims, and its deadline."
        actions={<button className="btn btn-primary" onClick={() => navigate("/submit")}><Send size={14} /> Submit content</button>}
      />

      {error && <div className="mb-4"><ErrorNote message={error} /></div>}

      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative min-w-[230px] flex-1 sm:max-w-md">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--bp-muted)" }} />
          <input className="input pl-9" placeholder="Search tasks…" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        <div className="pill-tabs">
          {FILTERS.map((f) => (
            <button key={f.value} className={`pill-tab ${filter === f.value ? "active" : ""}`} onClick={() => setFilter(f.value)}>{f.label}</button>
          ))}
        </div>
      </div>

      {loading ? (
        <LoadingBlock label="Loading assigned tasks…" />
      ) : filtered.length === 0 ? (
        <Empty
          title="No tasks match this filter"
          hint={tasks.length === 0 ? "Your manager has not assigned any campaign tasks yet." : "Try another filter or search term."}
        />
      ) : (
        <div className="space-y-2.5">
          {filtered.map((task) => (
            <button
              key={task.id}
              onClick={() => navigate(`/tasks/${task.id}`)}
              className="card card-pad hover-card flex w-full flex-col gap-3 text-left sm:flex-row sm:items-center"
            >
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg" style={{ background: "var(--bp-violet-soft)", color: "#c1a8ff" }}>
                <ClipboardList size={16} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="text-[13px] font-semibold">{task.title}</span>
                  <Badge status={task.status} />
                  <Badge status={task.priority} label={`${task.priority} priority`} />
                </span>
                <span className="mt-0.5 block truncate text-[11px] muted">
                  {task.campaign_name} · due {fmtDate(task.deadline)} · {task.manager_name ? `assigned by ${task.manager_name}` : "brand team"}
                </span>
                <span className="mt-1 line-clamp-1 text-[11.5px]" style={{ color: "var(--bp-text)" }}>{task.instructions}</span>
              </span>
              <span className="shrink-0 text-[11px] font-semibold" style={{ color: "var(--bp-cyan)" }}>Open task →</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
