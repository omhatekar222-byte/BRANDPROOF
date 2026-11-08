import { useEffect, useMemo, useState } from "react";
import { BookOpen, Download, FileText, Image as ImageIcon, MessageSquare, Palette, Search, ShieldCheck, Sparkles, Type } from "lucide-react";
import { api, API_ORIGIN, ApiError } from "../../lib/api";
import type { ApprovedClaim, BrandAsset, Fact, Guideline, Page } from "../../lib/types";
import { Badge, Empty, ErrorNote, Field, LoadingBlock, PageHeader, Spinner, fmtDate } from "../../components/ui";

type WalletDoc = { id: string; title: string; doc_type: string; category: string; status: string; version: number; review_date: string | null; file_name: string | null; char_count: number; updated_at: string | null; processing_status?: string; extracted_text?: string };
type AskResponse = { question: string; answer: string; sources: { title: string; locator?: string; text?: string }[]; grounded: boolean; mode: string; ai_error?: string | null };

const CATS = [
  { key: "all", label: "All categories", icon: ShieldCheck },
  { key: "identity", label: "Brand Identity", icon: Sparkles },
  { key: "guidelines", label: "Brand Guidelines", icon: BookOpen },
  { key: "visual", label: "Visual Identity", icon: Palette },
  { key: "products", label: "Products & Services", icon: FileText },
  { key: "marketing", label: "Marketing & Campaigns", icon: MessageSquare },
];

export default function KnowledgeWalletPage() {
  const [overview, setOverview] = useState<{ last_updated_at: string | null; counts: Record<string, number> } | null>(null);
  const [docs, setDocs] = useState<WalletDoc[]>([]);
  const [facts, setFacts] = useState<Fact[]>([]);
  const [claims, setClaims] = useState<ApprovedClaim[]>([]);
  const [guidelines, setGuidelines] = useState<Guideline[]>([]);
  const [assets, setAssets] = useState<BrandAsset[]>([]);
  const [cat, setCat] = useState("all");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [askQ, setAskQ] = useState("");
  const [asking, setAsking] = useState(false);
  const [askRes, setAskRes] = useState<AskResponse | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true); setError("");
      try {
        const [ov, d, f, c, g, a] = await Promise.all([
          api<{ last_updated_at: string | null; counts: Record<string, number> }>("/wallet/overview"),
          api<Page<WalletDoc>>("/wallet/documents?page_size=100"),
          api<Page<Fact>>("/wallet/facts?page_size=100"),
          api<Page<ApprovedClaim>>("/wallet/claims?page_size=100"),
          api<{ items: Guideline[] }>("/wallet/guidelines"),
          api<{ items: BrandAsset[] }>("/wallet/assets"),
        ]);
        setOverview(ov); setDocs(d.items); setFacts(f.items); setClaims(c.items); setGuidelines(g.items); setAssets(a.items);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Knowledge Wallet could not be loaded.");
      } finally { setLoading(false); }
    };
    void load();
  }, []);

  const term = q.trim().toLowerCase();
  const match = (s: string) => !term || s.toLowerCase().includes(term);

  const show = (cKey: string) => cat === "all" || cat === cKey;
  const fGuidelines = useMemo(() => guidelines.filter((g) => match(g.title + " " + g.content + " " + g.summary)), [guidelines, term]);
  const fDocs = useMemo(() => docs.filter((d) => match(d.title + " " + d.category + " " + d.doc_type)), [docs, term]);
  const fFacts = useMemo(() => facts.filter((f) => match(f.key + " " + f.value + " " + f.product)), [facts, term]);
  const fClaims = useMemo(() => claims.filter((c) => match(c.claim_text + " " + c.category)), [claims, term]);
  const fAssets = useMemo(() => assets.filter((a) => match(a.name + " " + a.asset_type)), [assets, term]);

  const ask = async () => {
    if (askQ.trim().length < 2) return;
    setAsking(true); setAskRes(null);
    try {
      setAskRes(await api<AskResponse>("/wallet/ask", { method: "POST", body: { question: askQ } }));
    } catch (err) {
      setAskRes({ question: askQ, answer: err instanceof ApiError ? err.message : "The assistant could not answer right now.", sources: [], grounded: true, mode: "error" });
    } finally { setAsking(false); }
  };

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow="Read-only approved knowledge"
        title="Knowledge Wallet"
        subtitle="Official brand information maintained by your administrator. Use this as the source of truth before creating or submitting content."
      />
      {error && <div className="mb-4"><ErrorNote message={error} /></div>}
      {loading ? <LoadingBlock label="Loading approved knowledge…" /> : (
        <>
          <div className="mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            <div className="card px-4 py-3"><p className="eyebrow">Last updated</p><p className="mt-1 text-[12.5px] font-semibold">{overview?.last_updated_at ? fmtDate(overview.last_updated_at) : "—"}</p></div>
            <div className="card px-4 py-3"><p className="eyebrow">Approved sources</p><p className="mt-1 text-[18px] font-bold">{(overview?.counts?.approved_documents || 0) + (overview?.counts?.approved_facts || 0)}</p></div>
            <div className="card px-4 py-3"><p className="eyebrow">Guidelines & claims</p><p className="mt-1 text-[18px] font-bold">{(overview?.counts?.approved_guidelines || 0) + (overview?.counts?.approved_claims || 0)}</p></div>
            <div className="card px-4 py-3"><p className="eyebrow">Brand assets</p><p className="mt-1 text-[18px] font-bold">{overview?.counts?.approved_assets || 0}</p></div>
          </div>

          <div className="mb-4 grid gap-4 lg:grid-cols-[1.5fr_1fr]">
            <div className="card card-pad">
              <h2 className="section-title flex items-center gap-2"><Sparkles size={15} style={{ color: "#b9a5ff" }} /> Ask about brand guidelines</h2>
              <p className="mt-0.5 text-[11.5px] muted">Answers are grounded in approved knowledge and cite sources. If information is missing, the assistant will say so.</p>
              <div className="mt-3 flex gap-2">
                <input className="input" value={askQ} onChange={(e) => setAskQ(e.target.value)} placeholder="e.g. What claims are permitted in our advertisements?" onKeyDown={(e) => e.key === "Enter" && void ask()} />
                <button className="btn btn-primary" onClick={() => void ask()} disabled={asking}>{asking ? <Spinner /> : "Ask"}</button>
              </div>
              {askRes && (
                <div className="mt-3 rounded-lg border p-3" style={{ borderColor: "var(--bp-border)", background: "var(--bp-surface-inset)" }}>
                  <p className="text-[12px] leading-relaxed whitespace-pre-wrap">{askRes.answer}</p>
                  {askRes.sources?.length > 0 && (
                    <div className="mt-2 border-t pt-2" style={{ borderColor: "var(--bp-border)" }}>
                      <p className="eyebrow">Sources</p>
                      <ul className="mt-1 space-y-1">
                        {askRes.sources.map((s, i) => <li key={i} className="text-[10.5px] muted">{s.title}{s.locator ? ` · ${s.locator}` : ""}</li>)}
                      </ul>
                    </div>
                  )}
                  <p className="mt-2 text-[10px] muted">Grounded answer · {askRes.mode === "ai" ? "AI-assisted" : "deterministic retrieval"}{askRes.ai_error ? " (AI fallback used)" : ""}</p>
                </div>
              )}
            </div>
            <div className="card card-pad">
              <h2 className="section-title">Search the Knowledge Wallet</h2>
              <div className="relative mt-3">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--bp-muted)" }} />
                <input className="input pl-9" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search approved information…" />
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {CATS.map((c) => (
                  <button key={c.key} className={`pill-tab ${cat === c.key ? "active" : ""}`} onClick={() => setCat(c.key)}>{c.label}</button>
                ))}
              </div>
              <p className="mt-3 text-[11px] muted">You can read and download permitted assets, but you cannot edit, approve or delete official brand knowledge.</p>
            </div>
          </div>

          {show("identity") && (fGuidelines.filter(g => ["messaging","tone","brand","terminology"].includes(g.category)).length > 0) && (
            <section className="card card-pad mb-4">
              <h2 className="section-title mb-3">1. Brand Identity</h2>
              <div className="grid gap-2 md:grid-cols-2">
                {fGuidelines.filter(g => ["messaging","tone","brand","terminology"].includes(g.category)).map((g) => (
                  <article key={g.id} className="rounded-lg border p-3" style={{ borderColor: "var(--bp-border)" }}>
                    <div className="flex items-center gap-2"><p className="text-[12.5px] font-semibold">{g.title}</p><Badge status="approved" /></div>
                    <p className="mt-1 text-[11.5px] leading-relaxed text-secondary whitespace-pre-wrap">{g.content}</p>
                  </article>
                ))}
              </div>
            </section>
          )}

          {show("guidelines") && (
            <section className="card card-pad mb-4">
              <h2 className="section-title mb-3">2. Brand Guidelines</h2>
              {fGuidelines.length === 0 ? <p className="text-[12px] muted">No approved guidelines match.</p> : (
                <div className="space-y-2">
                  {fGuidelines.map((g) => (
                    <article key={g.id} className="rounded-lg border p-3" style={{ borderColor: "var(--bp-border)" }}>
                      <div className="flex flex-wrap items-center gap-2"><p className="text-[12.5px] font-semibold">{g.title}</p><span className="text-[10px] uppercase muted">{g.category}</span><Badge status="approved" /></div>
                      {g.summary && <p className="mt-0.5 text-[11px] muted">{g.summary}</p>}
                      <p className="mt-1.5 text-[11.5px] leading-relaxed text-secondary whitespace-pre-wrap">{g.content}</p>
                    </article>
                  ))}
                </div>
              )}
            </section>
          )}

          {show("visual") && (
            <section className="card card-pad mb-4">
              <h2 className="section-title mb-3">3. Visual Identity</h2>
              {fAssets.length === 0 ? <p className="text-[12px] muted">No approved visual assets available.</p> : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {fAssets.map((asset) => (
                    <article key={asset.id} className="card overflow-hidden">
                      <div className="flex h-28 items-center justify-center border-b" style={{ borderColor: "var(--bp-border)", background: "var(--bp-surface-inset)" }}>
                        {asset.file_url ? <img src={asset.file_url.startsWith("http") ? asset.file_url : `${API_ORIGIN}${asset.file_url}`} alt={asset.name} className="max-h-24 max-w-full object-contain" />
                          : asset.color_hex ? <div><div className="mx-auto h-14 w-14 rounded-xl border" style={{ background: asset.color_hex }} /><p className="mt-1 font-mono text-[10px] text-center muted">{asset.color_hex}</p></div>
                          : asset.asset_type === "font" ? <Type size={26} style={{ color: "var(--bp-muted)" }} /> : <ImageIcon size={26} style={{ color: "var(--bp-muted)" }} />}
                      </div>
                      <div className="p-3">
                        <p className="text-[12px] font-semibold">{asset.name}</p>
                        <p className="text-[10.5px] capitalize muted">{asset.asset_type}{asset.notes ? ` · ${asset.notes}` : ""}</p>
                        {asset.file_url && <a href={asset.file_url.startsWith("http") ? asset.file_url : `${API_ORIGIN}${asset.file_url}`} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-[10.5px]" style={{ color: "var(--bp-cyan)" }}><Download size={11} /> Download / open</a>}
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </section>
          )}

          {show("products") && (
            <section className="card card-pad mb-4">
              <h2 className="section-title mb-3">4. Products and Services</h2>
              {fFacts.length === 0 && fDocs.filter(d => ["product_spec","warranty_pricing"].includes(d.doc_type)).length === 0 ? <p className="text-[12px] muted">No approved product information matches.</p> : (
                <>
                  {fFacts.length > 0 && (
                    <div className="table-wrap mb-3"><table className="table"><thead><tr><th>Approved fact</th><th>Value</th><th>Product</th><th>Source</th></tr></thead><tbody>
                      {fFacts.map((f) => <tr key={f.id}><td className="primary-cell">{f.key}</td><td>{f.value}</td><td>{f.product || "—"}</td><td className="text-[11px] muted">{f.document_title || f.source_locator || "Approved record"}</td></tr>)}
                    </tbody></table></div>
                  )}
                  <div className="grid gap-2 md:grid-cols-2">
                    {fDocs.filter(d => ["product_spec","warranty_pricing","company_info"].includes(d.doc_type)).map((d) => (
                      <div key={d.id} className="rounded-lg border p-3" style={{ borderColor: "var(--bp-border)" }}>
                        <p className="text-[12px] font-semibold">{d.title}</p>
                        <p className="text-[10.5px] muted capitalize">{d.doc_type.replace(/_/g, " ")} · v{d.version} · updated {fmtDate(d.updated_at)}</p>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </section>
          )}

          {show("marketing") && (
            <section className="card card-pad mb-4">
              <h2 className="section-title mb-3">5. Marketing and Campaign Guidelines</h2>
              {fClaims.length === 0 ? <p className="text-[12px] muted">No approved/prohibited claims match.</p> : (
                <div className="space-y-2">
                  {fClaims.map((c) => (
                    <div key={c.id} className="flex items-start justify-between gap-3 rounded-lg border p-3" style={{ borderColor: "var(--bp-border)" }}>
                      <div><p className="text-[12px]">{c.claim_text}</p><p className="mt-0.5 text-[10.5px] muted capitalize">{c.category}{c.expiry_date ? ` · review/expiry ${fmtDate(c.expiry_date)}` : ""}</p></div>
                      <Badge status={c.status} />
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}
        </>
      )}
    </div>
  );
}
