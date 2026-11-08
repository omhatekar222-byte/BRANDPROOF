import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { FileSearch, FileUp, Filter, Plus, Search, Send, Sparkles } from "lucide-react";
import { api, ApiError, qs } from "../../lib/api";
import { useSession } from "../../lib/session";
import type { Campaign, Dashboard, Page, Submission } from "../../lib/types";
import {
  Badge, Empty, ErrorNote, Field, LoadingBlock, Modal, PageHeader, Stat, fmtDateTime, timeAgo,
} from "../../components/ui";

const STATUS_FILTERS = [
  { value: "", label: "All" },
  { value: "submitted", label: "Submitted" },
  { value: "under_review", label: "Under review" },
  { value: "changes_requested", label: "Changes requested" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "draft", label: "Draft" },
];

const CONTENT_TYPES = ["advertisement", "social_post", "product_description", "email", "landing_page", "press_release", "document", "presentation"];

export default function ReviewPage() {
  const navigate = useNavigate();
  const { toast } = useSession();
  const [params] = useSearchParams();
  const [items, setItems] = useState<Submission[]>([]);
  const [total, setTotal] = useState(0);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [status, setStatus] = useState("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [newOpen, setNewOpen] = useState(params.get("new") === "1");

  // create form
  const [mode, setMode] = useState<"text" | "file">("text");
  const [title, setTitle] = useState("");
  const [contentType, setContentType] = useState("advertisement");
  const [campaign, setCampaign] = useState("");
  const [product, setProduct] = useState("");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");

  const load = async (term = query, state = status) => {
    setLoading(true);
    setError("");
    try {
      const [list, dash, camp] = await Promise.all([
        api<Page<Submission>>(`/content/submissions${qs({ q: term, status: state, page_size: 100 })}`),
        api<Dashboard>("/analytics/dashboard"),
        api<{ items: Campaign[] }>("/campaigns"),
      ]);
      setItems(list.items);
      setTotal(list.total);
      setDashboard(dash);
      setCampaigns(camp.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Submissions could not be loaded.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [status]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void load(query, status); }, 300);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  const openNew = () => {
    setFormError("");
    setNewOpen(true);
  };

  const submit = async () => {
    setFormError("");
    try {
      if (!title.trim() || title.trim().length < 2) throw new ApiError("Give the submission a title.", 422);
      let result: Submission;
      if (mode === "file") {
        if (!file) throw new ApiError("Choose a file to analyse.", 422);
        const form = new FormData();
        form.append("file", file);
        form.append("title", title.trim());
        form.append("content_type", contentType);
        form.append("campaign", campaign);
        form.append("product", product);
        form.append("submit_now", "true");
        form.append("analyze_now", "true");
        setSubmitting(true);
        result = await api<Submission>("/content/submissions/upload", { method: "POST", body: form });
      } else {
        if (text.trim().length < 10) throw new ApiError("Paste at least a sentence of content (10+ characters).", 422);
        setSubmitting(true);
        result = await api<Submission>("/content/submissions", {
          method: "POST",
          body: {
            title: title.trim(),
            content_type: contentType,
            campaign,
            product,
            text,
            submit_now: true,
            analyze_now: true,
          },
        });
      }
      setNewOpen(false);
      setTitle(""); setText(""); setFile(null); setCampaign(""); setProduct("");
      toast("ok", "Content analysed against approved brand knowledge.");
      navigate(`/review/${result.id}`);
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Submission failed.");
    } finally {
      setSubmitting(false);
    }
  };

  const t = dashboard?.totals;
  const awaiting = items.filter((s) => ["submitted", "under_review"].includes(s.status)).length;

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow="Evidence-backed verification"
        title="Content Review"
        subtitle="Submit content, identify individual claims, and compare each one against approved company knowledge and guidelines. The AI never invents evidence."
        actions={
          <button className="btn btn-primary" onClick={openNew}><Plus size={14} /> New review</button>
        }
      />

      <div className="mb-5 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
        <Stat label="Total submissions" value={t?.submissions ?? 0} />
        <Stat label="Awaiting review" value={t?.pending_reviews ?? 0} color="var(--bp-warning)" />
        <Stat label="Contradicted claims" value={t?.claims_contradicted ?? 0} color="var(--bp-danger)" />
        <Stat label="Unsupported claims" value={t?.claims_unsupported ?? 0} color="var(--bp-warning)" />
        <Stat label="Supported claims" value={t?.claims_supported ?? 0} color="var(--bp-success)" />
      </div>

      {error && <div className="mb-4"><ErrorNote message={error} /></div>}

      <div className="card overflow-hidden">
        <div className="flex flex-col gap-3 border-b p-4 sm:flex-row sm:items-center" style={{ borderColor: "var(--bp-border)" }}>
          <div className="relative min-w-[220px] flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--bp-muted)" }} />
            <input
              className="input pl-9"
              placeholder="Search by title, campaign, product or content…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-1.5 overflow-x-auto">
            <Filter size={13} className="shrink-0" style={{ color: "var(--bp-muted)" }} />
            {STATUS_FILTERS.map((f) => (
              <button key={f.value} className={`pill-tab ${status === f.value ? "active" : ""}`} onClick={() => setStatus(f.value)}>
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <LoadingBlock label="Loading submissions…" />
        ) : items.length === 0 ? (
          <div className="p-5">
            <Empty
              title={query || status ? "No submissions match these filters" : "No content submitted yet"}
              hint={query || status ? "Try a different search or status filter." : "Submit advertising copy, a social post or a document. Each factual statement will be checked against approved knowledge."}
              action={<button className="btn btn-primary" onClick={openNew}><Send size={14} /> Submit content for review</button>}
            />
          </div>
        ) : (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr><th>Submission</th><th>Creator</th><th>Campaign</th><th>Status</th><th>Verification</th><th>Updated</th></tr>
                </thead>
                <tbody>
                  {items.map((s) => (
                    <tr key={s.id} className="cursor-pointer" onClick={() => navigate(`/review/${s.id}`)}>
                      <td className="primary-cell">
                        <p className="max-w-[320px] truncate">{s.title}</p>
                        <p className="text-[10.5px] font-normal capitalize muted">{s.content_type.replace(/_/g, " ")} · v{s.current_version} · {s.word_count} words</p>
                      </td>
                      <td>{s.submitted_by?.full_name || "—"}</td>
                      <td className="max-w-[170px] truncate">{s.campaign || "—"}</td>
                      <td><Badge status={s.status} /></td>
                      <td>
                        <div className="flex items-center gap-1.5">
                          <span className={`badge ${s.analysis_mode === "ai" ? "b-violet" : s.analysis_mode === "demo" ? "b-demo" : "b-neutral"}`}>
                            {s.analysis_mode === "not_analyzed" ? "Not analysed" : s.analysis_mode}
                          </span>
                          {!!s.open_findings && <span className="text-[10.5px]" style={{ color: "var(--bp-warning)" }}>{s.open_findings} open</span>}
                        </div>
                      </td>
                      <td className="whitespace-nowrap text-[11.5px] muted">{timeAgo(s.updated_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between border-t px-4 py-2.5 text-[11px] muted" style={{ borderColor: "var(--bp-border)" }}>
              <span>{items.length} of {total} submissions shown</span>
              <span>{awaiting} awaiting a decision</span>
            </div>
          </>
        )}
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <div className="card card-pad">
          <div className="flex items-center gap-2 text-[12px] font-semibold"><Sparkles size={14} style={{ color: "#b9a5ff" }} /> How verification works</div>
          <p className="mt-1.5 text-[11.5px] leading-relaxed muted">
            Claims are extracted, matched to approved facts and documents, then classified as supported,
            contradicted, unsupported or inconclusive with an explanation and source.
          </p>
        </div>
        <div className="card card-pad">
          <div className="flex items-center gap-2 text-[12px] font-semibold"><FileUp size={14} style={{ color: "var(--bp-cyan)" }} /> Document extraction</div>
          <p className="mt-1.5 text-[11.5px] leading-relaxed muted">
            PDF, DOCX, TXT and MD uploads use their real extracted text. Unreadable files are rejected,
            never silently marked as analysed.
          </p>
        </div>
        <div className="card card-pad">
          <div className="flex items-center gap-2 text-[12px] font-semibold"><FileSearch size={14} style={{ color: "var(--bp-success)" }} /> Human control</div>
          <p className="mt-1.5 text-[11.5px] leading-relaxed muted">
            A supported AI result is not an approval. Final decisions are made in the Approval Centre and
            recorded in the audit history.
          </p>
        </div>
      </div>

      <Modal
        open={newOpen}
        onClose={() => setNewOpen(false)}
        title="Submit content for verification"
        wide
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setNewOpen(false)}>Cancel</button>
            <button className="btn btn-primary" onClick={submit} disabled={submitting}>
              {submitting ? "Analysing…" : "Submit & verify"}
            </button>
          </>
        }
      >
        <div className="space-y-3.5">
          {formError && <ErrorNote message={formError} />}
          <div className="flex gap-2">
            <button className={`btn ${mode === "text" ? "btn-primary" : "btn-secondary"}`} onClick={() => setMode("text")}>Paste text</button>
            <button className={`btn ${mode === "file" ? "btn-primary" : "btn-secondary"}`} onClick={() => setMode("file")}>Upload file</button>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Submission title" className="sm:col-span-2">
              <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. NovaPhone X launch advertisement" />
            </Field>
            <Field label="Content type">
              <select className="select" value={contentType} onChange={(e) => setContentType(e.target.value)}>
                {CONTENT_TYPES.map((c) => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}
              </select>
            </Field>
            <Field label="Campaign (optional)">
              <input className="input" list="review-campaigns" value={campaign} onChange={(e) => setCampaign(e.target.value)} placeholder="Campaign name" />
              <datalist id="review-campaigns">
                {campaigns.map((c) => <option key={c.id} value={c.name} />)}
              </datalist>
            </Field>
            <Field label="Product (optional)" className="sm:col-span-2">
              <input className="input" value={product} onChange={(e) => setProduct(e.target.value)} placeholder="e.g. NovaPhone X" />
            </Field>
          </div>

          {mode === "text" ? (
            <Field label="Content to verify" hint="Paste the exact copy that would be published. Individual claims are extracted from this text.">
              <textarea className="textarea" rows={10} value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste advertisement copy, a social post, product description…" />
            </Field>
          ) : (
            <Field label="Content file" hint="Supported: PDF, DOCX, TXT, MD. Image OCR depends on the server's OCR engine and is never simulated.">
              <input type="file" className="input" accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg" onChange={(e) => setFile(e.target.files?.[0] || null)} />
              {file && <p className="field-hint">Selected: {file.name} ({Math.round(file.size / 1024)} KB)</p>}
            </Field>
          )}

          <div className="rounded-lg border p-3 text-[11px] muted" style={{ borderColor: "var(--bp-border)" }}>
            The submitted content is treated as untrusted data. It is analysed against the approved knowledge
            in this workspace and stored with its verification report; it is not published automatically.
          </div>
        </div>
      </Modal>
    </div>
  );
}
