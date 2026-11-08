import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search } from "lucide-react";
import { api, ApiError } from "../../lib/api";
import type { Page, Submission } from "../../lib/types";
import { Badge, Empty, ErrorNote, LoadingBlock, PageHeader, Stat, timeAgo } from "../../components/ui";

const FILTERS = [
  { value: "", label: "All" },
  { value: "submitted", label: "Submitted" },
  { value: "changes_requested", label: "Changes requested" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
];

export default function MySubmissionsPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("");
  const [query, setQuery] = useState("");

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const data = await api<Page<Submission>>("/content/submissions?page_size=100");
        setItems(data.items);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Your submissions could not be loaded.");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    return items.filter((s) => {
      if (filter && s.status !== filter) return false;
      if (term && !(s.title + " " + s.campaign + " " + s.product).toLowerCase().includes(term)) return false;
      return true;
    });
  }, [items, filter, query]);

  const counts = useMemo(() => {
    const map: Record<string, number> = {};
    for (const item of items) map[item.status] = (map[item.status] || 0) + 1;
    return map;
  }, [items]);

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow="Your submission history"
        title="My Submissions"
        subtitle="Every piece of content you have submitted, its verification outcome, and the manager's approval status."
      />

      {error && <div className="mb-4"><ErrorNote message={error} /></div>}

      <div className="mb-5 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Total submissions" value={items.length} />
        <Stat label="Awaiting review" value={(counts.submitted || 0) + (counts.under_review || 0)} color="var(--bp-warning)" />
        <Stat label="Needs correction" value={counts.changes_requested || 0} color="var(--bp-cyan)" />
        <Stat label="Approved" value={counts.approved || 0} color="var(--bp-success)" />
      </div>

      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative min-w-[230px] flex-1 sm:max-w-md">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--bp-muted)" }} />
          <input className="input pl-9" placeholder="Search your submissions…" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        <div className="pill-tabs">
          {FILTERS.map((f) => (
            <button key={f.value} className={`pill-tab ${filter === f.value ? "active" : ""}`} onClick={() => setFilter(f.value)}>{f.label}</button>
          ))}
        </div>
      </div>

      {loading ? (
        <LoadingBlock label="Loading your submissions…" />
      ) : filtered.length === 0 ? (
        <Empty
          title={items.length === 0 ? "No submissions yet" : "No submissions match this filter"}
          hint={items.length === 0 ? "Open an assigned task, submit your content, and its verification report will appear here." : "Try another status filter or search term."}
          action={items.length === 0 ? <button className="btn btn-primary" onClick={() => navigate("/tasks")}>Open my tasks</button> : undefined}
        />
      ) : (
        <div className="card overflow-hidden">
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Submission</th><th>Campaign</th><th>Status</th><th>Verification</th><th>Open findings</th><th>Updated</th></tr></thead>
              <tbody>
                {filtered.map((item) => (
                  <tr key={item.id} className="cursor-pointer" onClick={() => navigate(`/submissions/${item.id}`)}>
                    <td className="primary-cell">
                      <p className="max-w-[340px] truncate">{item.title}</p>
                      <p className="text-[10.5px] font-normal capitalize muted">{item.content_type.replace(/_/g, " ")} · v{item.current_version}</p>
                    </td>
                    <td>{item.campaign || "—"}</td>
                    <td><Badge status={item.status} /></td>
                    <td>
                      <span className={`badge ${item.analysis_mode === "ai" ? "b-violet" : item.analysis_mode === "demo" ? "b-demo" : "b-neutral"}`}>
                        {item.analysis_mode === "not_analyzed" ? "Not analysed" : item.analysis_mode}
                      </span>
                    </td>
                    <td>{item.open_findings ?? 0}</td>
                    <td className="whitespace-nowrap text-[11.5px] muted">{timeAgo(item.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
