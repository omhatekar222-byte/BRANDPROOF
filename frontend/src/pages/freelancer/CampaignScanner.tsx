import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, CheckCircle2, FileUp, RefreshCw, ScanSearch, Send, Sparkles } from "lucide-react";
import { api, ApiError } from "../../lib/api";
import { useSession } from "../../lib/session";
import type { Submission, SubmissionDetail } from "../../lib/types";
import { ClaimList, FindingList } from "../../components/VerificationReport";
import { Badge, Empty, ErrorNote, Field, LoadingBlock, PageHeader, SuccessNote } from "../../components/ui";

type ScanResult = SubmissionDetail;

export default function CampaignScannerPage() {
  const navigate = useNavigate();
  const { toast } = useSession();
  const [title, setTitle] = useState("");
  const [contentType, setContentType] = useState("advertisement");
  const [campaign, setCampaign] = useState("");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<"text" | "file">("text");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [submissionId, setSubmissionId] = useState<string | null>(null);
  const [result, setResult] = useState<ScanResult | null>(null);

  const runScan = async (rescan = false) => {
    setError(""); setNotice("");
    try {
      setBusy(true);
      let sid = submissionId;
      if (!rescan) {
        if (!title.trim()) throw new ApiError("Add a title for this campaign/advertisement scan.", 422);
        if (mode === "file") {
          if (!file) throw new ApiError("Choose a file to scan.", 422);
          const form = new FormData();
          form.append("file", file);
          form.append("title", title.trim());
          form.append("content_type", contentType);
          form.append("campaign", campaign || "Campaign scan");
          form.append("submit_now", "false"); // scan before submission to organisation
          form.append("analyze_now", "true");
          const created = await api<Submission>("/content/submissions/upload", { method: "POST", body: form });
          sid = created.id;
        } else {
          if (text.trim().length < 10) throw new ApiError("Paste or write campaign/advertisement content to scan.", 422);
          const created = await api<Submission>("/content/submissions", {
            method: "POST",
            body: { title: title.trim(), content_type: contentType, campaign: campaign || "Campaign scan", product: "", text, submit_now: false, analyze_now: true },
          });
          sid = created.id;
        }
        setSubmissionId(sid);
      } else if (sid) {
        // update text if changed, then re-analyze
        if (mode === "text" && text.trim().length >= 10) {
          await api(`/content/submissions/${sid}`, { method: "PATCH", body: { text, note: "Rescanned after edits" } }).catch(() => null);
        }
        await api(`/content/submissions/${sid}/analyze`, { method: "POST", body: {} });
      }
      if (!sid) throw new ApiError("Scan could not be started.", 500);
      const detail = await api<ScanResult>(`/content/submissions/${sid}`);
      setResult(detail);
      setNotice(rescan ? "Content rescanned against the latest approved knowledge." : "Scan complete. Review evidence and recommendations before submitting.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The scan failed.");
    } finally { setBusy(false); }
  };

  const submitForReview = async () => {
    if (!submissionId) return;
    setBusy(true); setError("");
    try {
      await api(`/content/submissions/${submissionId}/status`, { method: "POST", body: { status: "submitted", notes: "Submitted for administrator review after campaign scan." } });
      toast("ok", "Submitted for administrator review. You cannot approve your own content.");
      navigate(`/submissions/${submissionId}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not submit for review.");
    } finally { setBusy(false); }
  };

  const applyCorrections = async () => {
    if (!submissionId) return;
    setBusy(true); setError("");
    try {
      const res = await api<{ applied: number }>(`/content/submissions/${submissionId}/apply-corrections`, { method: "POST", body: {} });
      const detail = await api<ScanResult>(`/content/submissions/${submissionId}`);
      setResult(detail);
      setNotice(`Applied ${res.applied || 0} correction(s) and rescanned. Review the result before submitting.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Corrections could not be applied.");
    } finally { setBusy(false); }
  };

  const statusMap: Record<string, string> = { supported: "Verified", contradicted: "Contradicted", unsupported: "Unsupported", inconclusive: "Needs Review" };

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow="Freelancer pre-submission check"
        title="Campaign Scanner"
        subtitle="Scan campaigns and advertisements against the administrator's approved Knowledge Wallet before submitting to the organisation."
      />
      {notice && <div className="mb-4"><SuccessNote>{notice}</SuccessNote></div>}
      {error && <div className="mb-4"><ErrorNote message={error} /></div>}

      <div className="grid gap-4 lg:grid-cols-[1fr_1.45fr]">
        <section className="card card-pad self-start">
          <h2 className="section-title flex items-center gap-2"><ScanSearch size={15} /> Content to scan</h2>
          <div className="mt-3 space-y-3">
            <Field label="Title"><input className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Nova X1 launch ad copy" /></Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Content type">
                <select className="select" value={contentType} onChange={(e) => setContentType(e.target.value)}>
                  {["advertisement","social_post","product_description","email","landing_page","press_release","document"].map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
                </select>
              </Field>
              <Field label="Campaign (optional)"><input className="input" value={campaign} onChange={(e) => setCampaign(e.target.value)} /></Field>
            </div>
            <div className="flex gap-2">
              <button className={`btn ${mode === "text" ? "btn-primary" : "btn-secondary"}`} onClick={() => setMode("text")}>Paste text</button>
              <button className={`btn ${mode === "file" ? "btn-primary" : "btn-secondary"}`} onClick={() => setMode("file")}>Upload file</button>
            </div>
            {mode === "text" ? (
              <Field label="Campaign / advertisement content"><textarea className="textarea" rows={12} value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste your campaign copy here…" /></Field>
            ) : (
              <Field label="File (PDF, DOCX, TXT, MD, supported images)"><input type="file" className="input" accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg" onChange={(e) => setFile(e.target.files?.[0] || null)} /></Field>
            )}
            <div className="rounded-lg border p-3 text-[11px] muted" style={{ borderColor: "var(--bp-border)" }}>
              Scans check unclaimed/unsupported statements, contradictions, outdated info, prohibited claims, brand language issues, and missing required information against approved evidence. Missing evidence is <b>Unsupported</b>, not automatically false.
            </div>
            <div className="flex flex-wrap gap-2">
              <button className="btn btn-primary" onClick={() => void runScan(!!submissionId)} disabled={busy}><ScanSearch size={14} /> {busy ? "Scanning…" : submissionId ? "Rescan" : "Scan content"}</button>
              {submissionId && <button className="btn btn-secondary" onClick={() => void runScan(true)} disabled={busy}><RefreshCw size={14} /> Rescan revised</button>}
            </div>
          </div>
        </section>

        <section className="space-y-4">
          {!result ? (
            <div className="card card-pad"><Empty title="No scan results yet" hint="Submit campaign copy or a document to generate an evidence-based report with recommended corrections." /></div>
          ) : (
            <>
              <div className="card card-pad">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <h2 className="section-title flex items-center gap-2"><Sparkles size={15} style={{ color: "#b9a5ff" }} /> Scan report</h2>
                    <p className="mt-0.5 text-[11px] muted">{result.analysis_mode === "demo" ? "Deterministic demo verification" : "Analysis"} · v{result.current_version} · you cannot approve your own content.</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button className="btn btn-secondary btn-sm" onClick={applyCorrections} disabled={busy}>Apply suggested corrections</button>
                    <button className="btn btn-primary btn-sm" onClick={submitForReview} disabled={busy}><Send size={13} /> Submit for Administrator review</button>
                  </div>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-5">
                  <Count label="Claims" value={result.counts.claims} />
                  <Count label="Verified" value={result.counts.supported} color="var(--bp-success)" />
                  <Count label="Contradicted" value={result.counts.contradicted} color="var(--bp-danger)" />
                  <Count label="Unsupported" value={result.counts.unsupported} color="var(--bp-warning)" />
                  <Count label="Needs review" value={result.counts.inconclusive} color="var(--bp-cyan)" />
                </div>
                {result.claims.some(c => c.status === "unsupported") && (
                  <p className="mt-3 text-[11px]" style={{ color: "var(--bp-warning)" }}><AlertTriangle size={12} className="inline mr-1" />Unsupported claims lack approved evidence — that does not mean they are false, but they should be removed or supported before submission.</p>
                )}
              </div>
              <div className="card card-pad">
                <h3 className="section-title mb-3">Claim findings & evidence</h3>
                <ClaimList claims={result.claims} />
              </div>
              <div className="card card-pad">
                <h3 className="section-title mb-1">Guideline / policy findings</h3>
                <p className="text-[11px] muted mb-3">Includes restricted language, prohibited claims, terminology, and required statements.</p>
                <FindingList findings={result.findings} claims={result.claims} />
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}

function Count({ label, value, color }: { label: string; value: number; color?: string }) {
  return <div className="rounded-lg border px-3 py-2.5" style={{ borderColor: "var(--bp-border)" }}><p className="eyebrow">{label}</p><p className="mt-0.5 text-[18px] font-bold" style={{ color: color || "var(--bp-ink)" }}>{value}</p></div>;
}
