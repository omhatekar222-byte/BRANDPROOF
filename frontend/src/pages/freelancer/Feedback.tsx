import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, CheckCircle2, MessageSquareWarning, Search } from "lucide-react";
import { api, ApiError } from "../../lib/api";
import type { Finding, Page } from "../../lib/types";
import { Badge, Empty, ErrorNote, LoadingBlock, PageHeader, Stat, fmtDate } from "../../components/ui";

const FILTERS = [
  { value: "open", label: "Needs attention" },
  { value: "resolved", label: "Resolved" },
  { value: "all", label: "All" },
];

export default function FeedbackPage() {
  const [findings, setFindings] = useState<Finding[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("open");
  const [query, setQuery] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const data = await api<Page<Finding>>("/review/findings?page_size=200");
        setFindings(data.items);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Feedback could not be loaded.");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    return findings.filter((finding) => {
      if (filter === "open" && !["open", "accepted", "modified"].includes(finding.status)) return false;
      if (filter === "resolved" && finding.status !== "resolved") return false;
      if (term && !(finding.title + " " + finding.explanation + " " + (finding.submission_title || "")).toLowerCase().includes(term)) return false;
      return true;
    });
  }, [findings, filter, query]);

  const open = findings.filter((f) => ["open", "accepted", "modified"].includes(f.status));
  const high = open.filter((f) => ["high", "critical"].includes(f.severity));

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow="Verification feedback"
        title="Feedback & Corrections"
        subtitle="Issues identified in your submissions, with the reason, the evidence used, and the suggested correction. Revise the content and resubmit when ready."
      />

      {error && <div className="mb-4"><ErrorNote message={error} /></div>}

      <div className="mb-5 grid gap-2 sm:grid-cols-3">
        <Stat label="Feedback items" value={findings.length} />
        <Stat label="Needs attention" value={open.length} color="var(--bp-warning)" />
        <Stat label="High severity" value={high.length} color="var(--bp-danger)" />
      </div>

      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative min-w-[230px] flex-1 sm:max-w-md">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--bp-muted)" }} />
          <input className="input pl-9" placeholder="Search feedback…" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        <div className="pill-tabs">
          {FILTERS.map((f) => (
            <button key={f.value} className={`pill-tab ${filter === f.value ? "active" : ""}`} onClick={() => setFilter(f.value)}>{f.label}</button>
          ))}
        </div>
      </div>

      {loading ? (
        <LoadingBlock label="Loading feedback…" />
      ) : filtered.length === 0 ? (
        <Empty
          title={findings.length === 0 ? "No feedback yet" : "Nothing matches this filter"}
          hint={findings.length === 0 ? "Verification feedback appears after you submit content. Each issue will include its explanation and suggested correction." : "Try a different filter or search term."}
          action={findings.length === 0 ? <Link to="/submit" className="btn btn-primary">Submit content</Link> : undefined}
        />
      ) : (
        <div className="space-y-2.5">
          {filtered.map((finding) => (
            <article key={finding.id} className="card card-pad">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-[13px] font-semibold">{finding.title}</h2>
                    <Badge status={finding.severity} />
                    <Badge status={finding.status} />
                  </div>
                  <p className="mt-0.5 text-[10.5px] muted">
                    {finding.submission_title || "Submission"} · {finding.category.replace(/_/g, " ")} · {fmtDate(finding.created_at)}
                  </p>
                </div>
                <Link to={`/submissions/${finding.submission_id}`} className="btn btn-secondary btn-sm shrink-0">
                  Open submission
                </Link>
              </div>

              {finding.original_text && (
                <p className="mt-2.5 border-l-2 pl-3 text-[12px] italic" style={{ borderColor: "#405478" }}>“{finding.original_text}”</p>
              )}
              <p className="mt-2 text-[12px] leading-relaxed text-secondary">{finding.explanation}</p>

              {finding.suggested_correction && (
                <div className="mt-2.5 flex items-start gap-2 rounded-lg border p-2.5" style={{ borderColor: "rgba(0,201,154,.22)", background: "rgba(0,201,154,.05)" }}>
                  {finding.status === "resolved" ? (
                    <CheckCircle2 size={14} className="mt-0.5 shrink-0" style={{ color: "var(--bp-success)" }} />
                  ) : (
                    <MessageSquareWarning size={14} className="mt-0.5 shrink-0" style={{ color: "var(--bp-success)" }} />
                  )}
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: "#62ddc0" }}>Suggested correction</p>
                    <p className="text-[11.5px] leading-relaxed">{finding.suggested_correction}</p>
                  </div>
                </div>
              )}

              {finding.source_passage && (
                <p className="mt-2 text-[11px] muted">
                  <AlertTriangle size={11} className="mr-1 inline" /> Evidence: {finding.source_passage}
                  {finding.source_locator ? ` (${finding.source_locator})` : ""}
                </p>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
