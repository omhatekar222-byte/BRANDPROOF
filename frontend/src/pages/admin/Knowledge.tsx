import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Archive, BookOpen, Building2, CheckCircle2, FileText, Image as ImageIcon, Layers,
  MessageSquare, Palette, Pencil, Plus, Search, ShieldCheck, Sparkles, Trash2, Upload, X,
} from "lucide-react";
import { api, API_ORIGIN, ApiError } from "../../lib/api";
import { useSession } from "../../lib/session";
import type {
  ApprovedClaim, BrandAsset, DocumentItem, Fact, Guideline, Organisation, Page,
} from "../../lib/types";
import {
  Badge, Confirm, Empty, ErrorNote, Field, LoadingBlock, Modal, PageHeader,
  SuccessNote, fmtDate,
} from "../../components/ui";

type Tab = "profile" | "claims" | "guidelines" | "documents" | "assets" | "assistant";

const TABS: { key: Tab; label: string }[] = [
  { key: "profile", label: "Company profile" },
  { key: "claims", label: "Approved claims" },
  { key: "guidelines", label: "Brand guidelines" },
  { key: "documents", label: "Documents & evidence" },
  { key: "assets", label: "Brand assets" },
  { key: "assistant", label: "AI Assistant" },
];

const DOC_TYPES = [
  ["product_spec", "Product specification"],
  ["company_info", "Company information"],
  ["approved_claim", "Approved claim source"],
  ["guideline", "Guideline document"],
  ["terminology", "Terminology"],
  ["warranty_pricing", "Warranty & pricing"],
  ["restricted_language", "Restricted language"],
  ["asset", "Asset reference"],
];

const emptyProfile = {
  name: "", industry: "", description: "", website: "", mission: "",
  target_audience: "", positioning: "",
};

export default function KnowledgePage() {
  const { org, refresh, toast } = useSession();
  const [params, setParams] = useSearchParams();
  const tab = (params.get("tab") as Tab) || "profile";
  const setTab = (next: Tab) => {
    const p = new URLSearchParams(params);
    p.set("tab", next);
    p.delete("new");
    setParams(p, { replace: true });
  };

  const [organisation, setOrganisation] = useState<Organisation | null>(org);
  const [profile, setProfile] = useState(emptyProfile);
  const [organizationName, setOrganizationName] = useState(org?.name || "");
  const [industry, setIndustry] = useState(org?.industry || "");
  const [claims, setClaims] = useState<ApprovedClaim[]>([]);
  const [guidelines, setGuidelines] = useState<Guideline[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [facts, setFacts] = useState<Fact[]>([]);
  const [assets, setAssets] = useState<BrandAsset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");

  // modal state
  const [claimForm, setClaimForm] = useState<null | Partial<ApprovedClaim>>(null);
  const [guidelineForm, setGuidelineForm] = useState<null | Partial<Guideline>>(null);
  const [documentForm, setDocumentForm] = useState<null | { title: string; doc_type: string; category: string; text: string; status: string; review_date: string }>(null);
  const [uploadForm, setUploadForm] = useState<null | { title: string; doc_type: string; category: string; status: string; review_date: string; file: File | null }>(null);
  const [factForm, setFactForm] = useState<null | { key: string; value: string; product: string; category: string; document_id: string; status: string; source_locator: string }>(null);
  const [assetForm, setAssetForm] = useState<null | { name: string; asset_type: string; color_hex: string; notes: string; file: File | null }>(null);
  const [deleteTarget, setDeleteTarget] = useState<null | { kind: "claim" | "asset"; id: string; label: string }>(null);
  const [saving, setSaving] = useState(false);
  const [documentPreview, setDocumentPreview] = useState<DocumentItem | null>(null);
  const [askQ, setAskQ] = useState("");
  const [askBusy, setAskBusy] = useState(false);
  const [askRes, setAskRes] = useState<{ answer: string; sources: { title: string; locator?: string }[]; mode: string; grounded: boolean } | null>(null);
  const [removeDoc, setRemoveDoc] = useState<DocumentItem | null>(null);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [dash, claimList, guidelineList, docList, assetList, factList] = await Promise.all([
        api<{ organisation: Organisation }>("/admin/overview"),
        api<Page<ApprovedClaim>>("/knowledge/claims?page_size=100"),
        api<{ items: Guideline[] }>("/knowledge/guidelines"),
        api<Page<DocumentItem>>("/knowledge/documents?page_size=100"),
        api<{ items: BrandAsset[] }>("/knowledge/assets"),
        api<Page<Fact>>("/knowledge/facts?page_size=100"),
      ]);
      setOrganisation(dash.organisation);
      setOrganizationName(dash.organisation.name);
      setIndustry(dash.organisation.industry);
      const s = (dash.organisation.settings || {}) as Record<string, string>;
      setProfile({
        name: dash.organisation.name || "",
        industry: dash.organisation.industry || "",
        description: s.description || "",
        website: s.website || "",
        mission: s.mission || "",
        target_audience: s.target_audience || "",
        positioning: s.positioning || "",
      });
      setClaims(claimList.items);
      setGuidelines(guidelineList.items);
      setDocuments(docList.items);
      setAssets(assetList.items);
      setFacts(factList.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Brand knowledge could not be loaded.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (params.get("new") === "document") setDocumentForm({ title: "", doc_type: "company_info", category: "General", text: "", status: "approved", review_date: "" });
    if (params.get("new") === "1" && tab === "claims") setClaimForm({ claim_text: "", category: "product", status: "approved", evidence_document_id: null, review_date: "", expiry_date: "" });
  }, [params, tab]);

  const flash = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 4500);
  };

  const run = async (fn: () => Promise<void>) => {
    setSaving(true);
    setError("");
    try {
      await fn();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The action could not be completed.");
    } finally {
      setSaving(false);
    }
  };

  const saveProfile = () => run(async () => {
    await api("/admin/organisation", {
      method: "PATCH",
      body: {
        name: organizationName,
        industry,
        settings: {
          description: profile.description,
          website: profile.website,
          mission: profile.mission,
          target_audience: profile.target_audience,
          positioning: profile.positioning,
        },
      },
    });
    await refresh();
    await load();
    flash("Company profile saved. The verification engine will use this approved information.");
  });

  const saveClaim = () => run(async () => {
    if (!claimForm || !claimForm.claim_text || claimForm.claim_text.trim().length < 3) {
      throw new ApiError("Enter a claim statement before saving.", 422);
    }
    const body = {
      claim_text: claimForm.claim_text.trim(),
      category: claimForm.category || "product",
      status: claimForm.status || "approved",
      evidence_document_id: claimForm.evidence_document_id || null,
      review_date: claimForm.review_date || null,
      expiry_date: claimForm.expiry_date || null,
    };
    if (claimForm.id) await api(`/knowledge/claims/${claimForm.id}`, { method: "PATCH", body });
    else await api("/knowledge/claims", { method: "POST", body });
    setClaimForm(null);
    await load();
    flash(claimForm.id ? "Claim updated." : "Claim added to the approved register.");
  });

  const saveGuideline = () => run(async () => {
    if (!guidelineForm?.title || !guidelineForm.content) throw new ApiError("A title and guideline content are required.", 422);
    const body = {
      title: guidelineForm.title,
      category: guidelineForm.category || "messaging",
      summary: guidelineForm.summary || "",
      content: guidelineForm.content,
      status: guidelineForm.status || "draft",
      effective_date: guidelineForm.effective_date || null,
      review_date: guidelineForm.review_date || null,
    };
    if (guidelineForm.id) await api(`/knowledge/guidelines/${guidelineForm.id}`, { method: "PATCH", body: { ...body, change_summary: "Updated from the Brand Knowledge workspace" } });
    else await api("/knowledge/guidelines", { method: "POST", body });
    setGuidelineForm(null);
    await load();
    flash(guidelineForm.id ? "Guideline updated." : "Guideline created.");
  });

  const saveDocument = () => run(async () => {
    if (!documentForm?.title || !documentForm.text.trim()) throw new ApiError("A title and document text are required.", 422);
    await api("/knowledge/documents", {
      method: "POST",
      body: { ...documentForm, review_date: documentForm.review_date || null, tags: [] },
    });
    setDocumentForm(null);
    await load();
    flash("Knowledge document saved. Only documents marked approved are used as evidence.");
  });

  const uploadDocument = () => run(async () => {
    if (!uploadForm?.file) throw new ApiError("Choose a file to upload.", 422);
    const form = new FormData();
    form.append("file", uploadForm.file);
    form.append("title", uploadForm.title || uploadForm.file.name);
    form.append("doc_type", uploadForm.doc_type);
    form.append("category", uploadForm.category);
    form.append("status", uploadForm.status);
    if (uploadForm.review_date) form.append("review_date", uploadForm.review_date);
    await api("/knowledge/documents/upload", { method: "POST", body: form });
    setUploadForm(null);
    await load();
    flash("Document uploaded and its real text extracted for retrieval.");
  });

  const saveFact = () => run(async () => {
    if (!factForm?.key || !factForm.value) throw new ApiError("Enter both the fact key and its approved value.", 422);
    await api("/knowledge/facts", {
      method: "POST",
      body: { ...factForm, document_id: factForm.document_id || null, review_date: null, effective_date: null },
    });
    setFactForm(null);
    await load();
    flash("Approved fact added. It can now be used during verification.");
  });

  const saveAsset = () => run(async () => {
    if (!assetForm?.name) throw new ApiError("Give this brand asset a name.", 422);
    if (assetForm.file) {
      const form = new FormData();
      form.append("file", assetForm.file);
      form.append("name", assetForm.name);
      form.append("asset_type", assetForm.asset_type);
      form.append("notes", assetForm.notes);
      await api("/knowledge/assets/upload", { method: "POST", body: form });
    } else {
      await api("/knowledge/assets", {
        method: "POST",
        body: {
          name: assetForm.name,
          asset_type: assetForm.asset_type,
          color_hex: assetForm.color_hex || null,
          notes: assetForm.notes,
        },
      });
    }
    setAssetForm(null);
    await load();
    flash("Brand asset saved.");
  });

  const deleteItem = () => run(async () => {
    if (!deleteTarget) return;
    if (deleteTarget.kind === "claim") await api(`/knowledge/claims/${deleteTarget.id}`, { method: "DELETE" });
    else await api(`/knowledge/assets/${deleteTarget.id}`, { method: "DELETE" });
    setDeleteTarget(null);
    await load();
    flash("Record removed.");
  });

  const removeDocument = () => run(async () => {
    if (!removeDoc) return;
    await api(`/knowledge/documents/${removeDoc.id}`, { method: "DELETE" });
    setRemoveDoc(null);
    await load();
    flash("Document removed. It is no longer in the knowledge repository.");
  });

  const askAssistant = async () => {
    if (askQ.trim().length < 2) return;
    setAskBusy(true); setAskRes(null);
    try {
      const res = await api<{ answer: string; sources: { title: string; locator?: string }[]; mode: string; grounded: boolean }>("/wallet/ask", { method: "POST", body: { question: askQ } });
      setAskRes(res);
    } catch (err) {
      setAskRes({ answer: err instanceof ApiError ? err.message : "The assistant could not answer.", sources: [], mode: "error", grounded: true });
    } finally { setAskBusy(false); }
  };

  const archiveDocument = (doc: DocumentItem) => run(async () => {
    await api(`/knowledge/documents/${doc.id}/archive`, { method: "POST" });
    await load();
    flash("Document archived. It is no longer used as evidence.");
  });

  const approveDocument = (doc: DocumentItem) => run(async () => {
    await api(`/knowledge/documents/${doc.id}`, { method: "PATCH", body: { status: "approved" } });
    await load();
    flash("Document approved and available as evidence.");
  });

  const filteredDocuments = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return documents;
    return documents.filter((d) =>
      (d.title + " " + d.category + " " + d.doc_type).toLowerCase().includes(term),
    );
  }, [documents, search]);

  const approvedDocs = documents.filter((d) => d.status === "approved");
  const unapprovedDocs = documents.filter((d) => d.status !== "approved" && d.status !== "archived");
  const expiredClaims = claims.filter((c) => c.expired).length;
  const expiringClaims = claims.filter((c) => c.status === "approved" && c.days_to_expiry !== null && c.days_to_expiry !== undefined && c.days_to_expiry >= 0 && c.days_to_expiry <= 45).length;

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow="Single source of truth"
        title="Brand Knowledge"
        subtitle="Approved company facts, claims and guidelines that the verification engine is allowed to rely on. Unverified records are kept separate and never treated as evidence."
        actions={
          <>
            <button className="btn btn-secondary" onClick={() => setUploadForm({ title: "", doc_type: "company_info", category: "General", status: "draft", review_date: "", file: null })}>
              <Upload size={14} /> Upload document
            </button>
            <button className="btn btn-primary" onClick={() => {
              if (tab === "claims") setClaimForm({ claim_text: "", category: "product", status: "approved", evidence_document_id: null, review_date: "", expiry_date: "" });
              else if (tab === "guidelines") setGuidelineForm({ title: "", category: "messaging", content: "", summary: "", status: "approved" });
              else if (tab === "assets") setAssetForm({ name: "", asset_type: "logo", color_hex: "", notes: "", file: null });
              else setDocumentForm({ title: "", doc_type: "company_info", category: "General", text: "", status: "approved", review_date: "" });
            }}>
              <Plus size={14} /> Add {tab === "claims" ? "claim" : tab === "guidelines" ? "guideline" : tab === "assets" ? "asset" : "information"}
            </button>
          </>
        }
      />

      {notice && <div className="mb-4"><SuccessNote>{notice}</SuccessNote></div>}
      {error && <div className="mb-4"><ErrorNote message={error} /></div>}

      <div className="tabs mb-5">
        {TABS.map((item) => (
          <button key={item.key} className={`tab ${tab === item.key ? "active" : ""}`} onClick={() => setTab(item.key)}>
            {item.label}
          </button>
        ))}
      </div>

      <div className="mb-5 grid gap-2 sm:grid-cols-4">
        <SummaryChip label="Approved documents" value={approvedDocs.length} hint={`${unapprovedDocs.length} unverified`} />
        <SummaryChip label="Approved claims" value={claims.filter((c) => c.status === "approved").length} hint={`${claims.filter((c) => c.status === "prohibited").length} prohibited`} />
        <SummaryChip label="Guidelines" value={guidelines.length} hint={`${guidelines.filter((g) => g.status === "approved").length} approved`} />
        <SummaryChip label="Claims needing review" value={expiredClaims + expiringClaims} hint={`${expiredClaims} expired · ${expiringClaims} expiring`} />
      </div>

      {loading ? (
        <LoadingBlock label="Loading approved knowledge…" />
      ) : (
        <>
          {tab === "profile" && (
            <section className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
              <div className="card card-pad">
                <h2 className="section-title mb-1 flex items-center gap-2"><Building2 size={15} /> Company profile</h2>
                <p className="mb-4 text-[11.5px] muted">This is the organisation every verification result is checked against.</p>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="Company name">
                    <input className="input" value={organizationName} onChange={(e) => setOrganizationName(e.target.value)} />
                  </Field>
                  <Field label="Industry">
                    <input className="input" value={industry} onChange={(e) => setIndustry(e.target.value)} placeholder="Consumer electronics" />
                  </Field>
                  <Field label="Official website" className="sm:col-span-2">
                    <input className="input" value={profile.website} onChange={(e) => setProfile({ ...profile, website: e.target.value })} placeholder="https://" />
                  </Field>
                  <Field label="Company description" className="sm:col-span-2">
                    <textarea className="textarea" rows={3} value={profile.description} onChange={(e) => setProfile({ ...profile, description: e.target.value })} placeholder="What the company does, in approved language." />
                  </Field>
                  <Field label="Brand mission" className="sm:col-span-2">
                    <textarea className="textarea" rows={2} value={profile.mission} onChange={(e) => setProfile({ ...profile, mission: e.target.value })} />
                  </Field>
                  <Field label="Target audience">
                    <textarea className="textarea" rows={3} value={profile.target_audience} onChange={(e) => setProfile({ ...profile, target_audience: e.target.value })} />
                  </Field>
                  <Field label="Company positioning">
                    <textarea className="textarea" rows={3} value={profile.positioning} onChange={(e) => setProfile({ ...profile, positioning: e.target.value })} />
                  </Field>
                </div>
                <div className="mt-4 flex justify-end">
                  <button className="btn btn-primary" onClick={saveProfile} disabled={saving}>
                    {saving ? "Saving…" : "Save company profile"}
                  </button>
                </div>
              </div>
              <div className="space-y-4">
                <div className="card card-pad">
                  <h3 className="section-title flex items-center gap-2"><ShieldCheck size={15} style={{ color: "var(--bp-success)" }} /> What the AI may use</h3>
                  <ul className="mt-3 space-y-2 text-[12px] text-secondary">
                    <li className="flex gap-2"><CheckCircle2 size={14} className="mt-0.5 shrink-0" style={{ color: "var(--bp-success)" }} /> Approved documents and their extracted text</li>
                    <li className="flex gap-2"><CheckCircle2 size={14} className="mt-0.5 shrink-0" style={{ color: "var(--bp-success)" }} /> Approved facts and the approved claim register</li>
                    <li className="flex gap-2"><CheckCircle2 size={14} className="mt-0.5 shrink-0" style={{ color: "var(--bp-success)" }} /> Approved brand guidelines and prohibited terms</li>
                    <li className="flex gap-2"><X size={14} className="mt-0.5 shrink-0" style={{ color: "var(--bp-danger)" }} /> Draft, outdated or archived records are excluded</li>
                  </ul>
                </div>
                <div className="card card-pad">
                  <h3 className="section-title">Workspace details</h3>
                  <dl className="mt-3 space-y-2 text-[12px]">
                    <Row label="Workspace" value={organisation?.name || "—"} />
                    <Row label="Slug" value={organisation?.slug || "—"} />
                    <Row label="Data type" value={organisation?.is_demo ? "Seeded demonstration records" : "Workspace records"} />
                    <Row label="Approved documents" value={`${approvedDocs.length} of ${documents.length}`} />
                    <Row label="Approved facts" value={`${facts.filter((f) => f.status === "approved").length} of ${facts.length}`} />
                  </dl>
                </div>
              </div>
            </section>
          )}

          {tab === "claims" && (
            <section className="card overflow-hidden">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b px-4 py-3.5" style={{ borderColor: "var(--bp-border)" }}>
                <div>
                  <h2 className="section-title">Approved claim register</h2>
                  <p className="text-[11px] muted">Each approved claim must trace to a source document. Prohibited phrases are enforced during verification.</p>
                </div>
                <button className="btn btn-primary btn-sm" onClick={() => setClaimForm({ claim_text: "", category: "product", status: "approved", evidence_document_id: null, review_date: "", expiry_date: "" })}>
                  <Plus size={13} /> New claim
                </button>
              </div>
              {claims.length === 0 ? (
                <div className="p-5">
                  <Empty title="No claims registered" hint="Add an approved claim with its supporting source. Without approved evidence, matching statements can only be classified as unsupported." action={<button className="btn btn-primary" onClick={() => setClaimForm({ claim_text: "", category: "product", status: "approved" })}>Add the first claim</button>} />
                </div>
              ) : (
                <div className="table-wrap">
                  <table className="table">
                    <thead><tr><th>Claim</th><th>Category</th><th>Evidence source</th><th>Status</th><th>Review / expiry</th><th /></tr></thead>
                    <tbody>
                      {claims.map((claim) => {
                        const source = documents.find((d) => d.id === claim.evidence_document_id);
                        return (
                          <tr key={claim.id}>
                            <td className="primary-cell max-w-[380px]">{claim.claim_text}</td>
                            <td className="capitalize">{claim.category}</td>
                            <td>
                              {source ? (
                                <span className="flex items-center gap-1.5">
                                  <FileText size={13} className="shrink-0" style={{ color: source.status === "approved" ? "var(--bp-success)" : "var(--bp-warning)" }} />
                                  <span className="max-w-[180px] truncate">{source.title}</span>
                                </span>
                              ) : (
                                <span className="text-[11.5px]" style={{ color: "var(--bp-warning)" }}>No evidence attached</span>
                              )}
                            </td>
                            <td><Badge status={claim.status} /></td>
                            <td className="text-[11px] muted">
                              {fmtDate(claim.review_date)} / {fmtDate(claim.expiry_date)}
                              {claim.expired && <span className="badge b-outdated ml-1.5">Expired</span>}
                            </td>
                            <td>
                              <div className="flex justify-end gap-1">
                                <button className="btn btn-ghost btn-icon" onClick={() => setClaimForm(claim)} aria-label="Edit claim"><Pencil size={14} /></button>
                                <button className="btn btn-ghost btn-icon" onClick={() => setDeleteTarget({ kind: "claim", id: claim.id, label: claim.claim_text })} aria-label="Delete claim"><Trash2 size={14} /></button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}

          {tab === "guidelines" && (
            <section className="grid gap-3 md:grid-cols-2">
              {guidelines.length === 0 && (
                <div className="md:col-span-2">
                  <Empty title="No brand guidelines yet" hint="Add tone, terminology, prohibited expressions or visual rules so verification can evaluate them." action={<button className="btn btn-primary" onClick={() => setGuidelineForm({ title: "", category: "tone", content: "", summary: "", status: "approved" })}>Add a guideline</button>} />
                </div>
              )}
              {guidelines.map((g) => (
                <article key={g.id} className="card card-pad">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-[13.5px] font-semibold">{g.title}</h3>
                        <Badge status={g.status} />
                        <span className="text-[10px] muted">v{g.version}</span>
                      </div>
                      <p className="mt-0.5 text-[10.5px] uppercase tracking-wide muted">{g.category}</p>
                    </div>
                    <button className="btn btn-ghost btn-icon" onClick={() => setGuidelineForm(g)} aria-label="Edit guideline"><Pencil size={14} /></button>
                  </div>
                  <p className="mt-3 whitespace-pre-wrap text-[12px] leading-relaxed text-secondary">{g.content}</p>
                  <div className="mt-3 border-t pt-2.5 text-[10.5px] muted" style={{ borderColor: "var(--bp-border)" }}>
                    Review {fmtDate(g.review_date)} · effective {fmtDate(g.effective_date)}
                  </div>
                </article>
              ))}
            </section>
          )}

          {tab === "documents" && (
            <section className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <div className="relative min-w-[220px] flex-1">
                  <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--bp-muted)" }} />
                  <input className="input pl-9" placeholder="Search documents by title, type or category…" value={search} onChange={(e) => setSearch(e.target.value)} />
                </div>
                <button className="btn btn-secondary" onClick={() => setDocumentForm({ title: "", doc_type: "company_info", category: "General", text: "", status: "approved", review_date: "" })}>
                  <Plus size={14} /> Paste information
                </button>
                <button className="btn btn-secondary" onClick={() => setFactForm({ key: "", value: "", product: "", category: "product", document_id: "", status: "approved", source_locator: "" })}>
                  <Plus size={14} /> Add approved fact
                </button>
              </div>

              <div className="card overflow-hidden">
                <div className="border-b px-4 py-3" style={{ borderColor: "var(--bp-border)" }}>
                  <h2 className="section-title flex items-center gap-2"><FileText size={15} /> Documents & extracted evidence</h2>
                </div>
                {filteredDocuments.length === 0 ? (
                  <p className="p-5 text-[12.5px] muted">No documents match this search.</p>
                ) : (
                  <div className="table-wrap">
                    <table className="table">
                      <thead><tr><th>Document</th><th>Type</th><th>Approval</th><th>Processing</th><th>Version</th><th>Review date</th><th /></tr></thead>
                      <tbody>
                        {filteredDocuments.map((doc) => (
                          <tr key={doc.id}>
                            <td className="primary-cell">
                              <button className="text-left hover:underline" onClick={() => setDocumentPreview(doc)}>{doc.title}</button>
                              {doc.file_name && <p className="text-[10px] font-normal muted">{doc.file_name}</p>}
                            </td>
                            <td className="capitalize">{doc.doc_type.replace(/_/g, " ")}</td>
                            <td><Badge status={doc.status} /></td>
                            <td className="text-[11px]">
                              <span className="badge" style={{ background: doc.char_count > 0 ? "var(--bp-success-soft, rgba(0,201,154,.12))" : "var(--bp-surface-inset)", color: doc.char_count > 0 ? "var(--bp-success)" : "var(--bp-muted)" }}>{doc.char_count > 0 ? "Processed" : "Uploaded"}</span>
                              <span className="ml-1 muted">{doc.char_count > 0 ? `${doc.char_count.toLocaleString()} chars` : ""}</span>
                            </td>
                            <td>v{doc.version}</td>
                            <td className="text-[11.5px] muted">{fmtDate(doc.review_date)}</td>
                            <td>
                              <div className="flex justify-end gap-1">
                                {doc.status !== "approved" && doc.status !== "archived" && (
                                  <button className="btn btn-ghost btn-sm" onClick={() => approveDocument(doc)} title="Approve for evidence use">Approve</button>
                                )}
                                {doc.status === "approved" && (
                                  <button className="btn btn-ghost btn-icon" onClick={() => archiveDocument(doc)} aria-label="Archive document" title="Archive"><Archive size={14} /></button>
                                )}
                                <button className="btn btn-ghost btn-icon" onClick={() => setRemoveDoc(doc)} aria-label="Remove document" title="Remove"><Trash2 size={14} /></button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              <div className="card overflow-hidden">
                <div className="border-b px-4 py-3" style={{ borderColor: "var(--bp-border)" }}>
                  <h2 className="section-title flex items-center gap-2"><Layers size={15} /> Approved facts used by verification</h2>
                  <p className="mt-0.5 text-[11px] muted">These key/value records are retrieved during analysis. Retiring a fact removes it from evidence.</p>
                </div>
                {facts.length === 0 ? (
                  <p className="p-5 text-[12.5px] muted">No approved facts recorded.</p>
                ) : (
                  <div className="table-wrap">
                    <table className="table">
                      <thead><tr><th>Fact</th><th>Approved value</th><th>Product</th><th>Source</th><th>Status</th><th>Review</th></tr></thead>
                      <tbody>
                        {facts.map((fact) => (
                          <tr key={fact.id}>
                            <td className="primary-cell">{fact.key}</td>
                            <td>{fact.value}</td>
                            <td>{fact.product || "—"}</td>
                            <td className="max-w-[220px] truncate text-[11.5px]">{fact.document_title || fact.source_locator || "No document"}</td>
                            <td><Badge status={fact.status} /></td>
                            <td className="text-[11.5px] muted">{fmtDate(fact.review_date)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </section>
          )}

          {tab === "assets" && (
            <section>
              {assets.length === 0 ? (
                <Empty title="No brand assets yet" hint="Upload approved logos and imagery, or record approved palette colours for reference." action={<button className="btn btn-primary" onClick={() => setAssetForm({ name: "", asset_type: "logo", color_hex: "", notes: "", file: null })}>Add a brand asset</button>} />
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {assets.map((asset) => (
                    <article key={asset.id} className="card overflow-hidden">
                      <div className="flex h-32 items-center justify-center border-b" style={{ borderColor: "var(--bp-border)", background: "#0e1728" }}>
                        {asset.file_url ? (
                          <img src={asset.file_url.startsWith("http") ? asset.file_url : `${API_ORIGIN}${asset.file_url}`} alt={asset.name} className="max-h-28 max-w-full object-contain" />
                        ) : asset.color_hex ? (
                          <div className="text-center">
                            <div className="mx-auto h-16 w-16 rounded-xl border" style={{ background: asset.color_hex, borderColor: "rgba(255,255,255,.18)" }} />
                            <p className="mt-2 font-mono text-[10.5px] muted">{asset.color_hex}</p>
                          </div>
                        ) : (
                          <span style={{ color: "#43536e" }}>{asset.asset_type === "font" ? <BookOpen size={30} /> : <ImageIcon size={30} />}</span>
                        )}
                      </div>
                      <div className="p-3.5">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <p className="text-[12.5px] font-semibold">{asset.name}</p>
                            <p className="text-[10.5px] capitalize muted">{asset.asset_type}{asset.notes ? ` · ${asset.notes}` : ""}</p>
                          </div>
                          <button className="btn btn-ghost btn-icon" onClick={() => setDeleteTarget({ kind: "asset", id: asset.id, label: asset.name })} aria-label="Delete asset"><Trash2 size={14} /></button>
                        </div>
                        <div className="mt-2 flex items-center gap-2">
                          <Badge status={asset.is_approved ? "approved" : "draft"} label={asset.is_approved ? "Approved" : "Unverified"} />
                          {asset.file_url && <a href={asset.file_url.startsWith("http") ? asset.file_url : `${API_ORIGIN}${asset.file_url}`} target="_blank" rel="noreferrer" className="text-[10.5px]" style={{ color: "var(--bp-cyan)" }}>Open file</a>}
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </section>
          )}

          {tab === "assistant" && (
            <section className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
              <div className="card card-pad">
                <h2 className="section-title flex items-center gap-2"><Sparkles size={15} style={{ color: "#b9a5ff" }} /> AI Brand Knowledge Assistant</h2>
                <p className="mt-1 text-[11.5px] muted">Ask questions about the centralised brand knowledge repository. Answers use approved documents and cite sources. If information is missing, the assistant will state that clearly and never invent details.</p>
                <div className="mt-4 flex gap-2">
                  <input className="input" value={askQ} onChange={(e) => setAskQ(e.target.value)} placeholder="e.g. What are our official brand colours? Summarise brand guidelines." onKeyDown={(e) => e.key === "Enter" && void askAssistant()} />
                  <button className="btn btn-primary" onClick={() => void askAssistant()} disabled={askBusy}>{askBusy ? "Asking…" : "Ask"}</button>
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {["What are our official brand colours?", "Which fonts are approved?", "What claims are permitted in advertisements?", "Summarise our brand guidelines.", "What language should freelancers avoid?"].map((q) => (
                    <button key={q} className="pill-tab" onClick={() => setAskQ(q)}>{q}</button>
                  ))}
                </div>
                {askRes && (
                  <div className="mt-4 rounded-xl border p-4" style={{ borderColor: "var(--bp-border)", background: "var(--bp-surface-inset)" }}>
                    <div className="flex items-center gap-2 mb-2">
                      <MessageSquare size={14} style={{ color: "var(--bp-cyan)" }} />
                      <span className="eyebrow">Grounded answer</span>
                      <span className="text-[10px] muted ml-auto">{askRes.mode === "ai" ? "AI-assisted" : "Deterministic retrieval"}</span>
                    </div>
                    <div className="text-[12.5px] leading-relaxed whitespace-pre-wrap">{askRes.answer}</div>
                    {askRes.sources?.length > 0 && (
                      <div className="mt-3 border-t pt-2.5" style={{ borderColor: "var(--bp-border)" }}>
                        <p className="eyebrow mb-1.5">Source documents / sections</p>
                        <ul className="space-y-1">
                          {askRes.sources.map((s, i) => <li key={i} className="text-[11px] flex gap-1.5"><FileText size={12} className="mt-0.5 shrink-0" style={{ color: "var(--bp-muted)" }} /><span>{s.title}{s.locator ? ` — ${s.locator}` : ""}</span></li>)}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
              <div className="card card-pad">
                <h3 className="section-title">Repository status</h3>
                <p className="mt-1 text-[11.5px] muted">Uploaded → Processed (text extracted) → Approved (authoritative). Only approved knowledge is used as evidence for freelancer scanning.</p>
                <dl className="mt-3 space-y-2 text-[12px]">
                  <Row label="Approved documents" value={`${approvedDocs.length}`} />
                  <Row label="Draft/unapproved docs" value={`${unapprovedDocs.length}`} />
                  <Row label="Approved facts" value={`${facts.filter((f) => f.status === "approved").length}`} />
                  <Row label="Approved claims" value={`${claims.filter((c) => c.status === "approved").length}`} />
                  <Row label="Prohibited claims" value={`${claims.filter((c) => c.status === "prohibited").length}`} />
                  <Row label="Guidelines" value={`${guidelines.filter((g) => g.status === "approved").length} approved`} />
                </dl>
                <div className="mt-4 rounded-lg border p-3 text-[11px]" style={{ borderColor: "rgba(255,181,71,.25)", background: "rgba(255,181,71,.05)" }}>
                  To find conflicting information across documents, ask the assistant and review cited sources. Final resolution requires administrator judgment.
                </div>
              </div>
            </section>
          )}
        </>
      )}

      {/* ---------- claim modal ---------- */}
      <Modal
        open={!!claimForm}
        onClose={() => setClaimForm(null)}
        title={claimForm?.id ? "Edit approved claim" : "Add approved claim"}
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setClaimForm(null)}>Cancel</button>
            <button className="btn btn-primary" onClick={saveClaim} disabled={saving}>{saving ? "Saving…" : "Save claim"}</button>
          </>
        }
      >
        {claimForm && (
          <div className="grid gap-3">
            <Field label="Claim statement">
              <textarea className="textarea" rows={3} value={claimForm.claim_text || ""} onChange={(e) => setClaimForm({ ...claimForm, claim_text: e.target.value })} placeholder="e.g. NovaTech X1 has a 5000 mAh battery." />
            </Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Category">
                <select className="select" value={claimForm.category || "product"} onChange={(e) => setClaimForm({ ...claimForm, category: e.target.value })}>
                  {["product", "promotional", "warranty", "pricing", "comparative", "compliance"].map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </Field>
              <Field label="Status">
                <select className="select" value={claimForm.status || "approved"} onChange={(e) => setClaimForm({ ...claimForm, status: e.target.value as ApprovedClaim["status"] })}>
                  <option value="approved">Approved — may be used as evidence</option>
                  <option value="draft">Draft — unverified, not evidence</option>
                  <option value="prohibited">Prohibited — must be flagged</option>
                </select>
              </Field>
            </div>
            <Field label="Supporting evidence" hint="Only documents marked approved are used as evidence. A claim without a source remains unverifiable.">
              <select className="select" value={claimForm.evidence_document_id || ""} onChange={(e) => setClaimForm({ ...claimForm, evidence_document_id: e.target.value || null })}>
                <option value="">No evidence attached</option>
                {documents.map((doc) => (
                  <option key={doc.id} value={doc.id}>{doc.title} ({doc.status})</option>
                ))}
              </select>
            </Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Review date">
                <input type="date" className="input" value={(claimForm.review_date || "").slice(0, 10)} onChange={(e) => setClaimForm({ ...claimForm, review_date: e.target.value })} />
              </Field>
              <Field label="Expiry date">
                <input type="date" className="input" value={(claimForm.expiry_date || "").slice(0, 10)} onChange={(e) => setClaimForm({ ...claimForm, expiry_date: e.target.value })} />
              </Field>
            </div>
          </div>
        )}
      </Modal>

      {/* ---------- guideline modal ---------- */}
      <Modal
        open={!!guidelineForm}
        onClose={() => setGuidelineForm(null)}
        title={guidelineForm?.id ? "Edit guideline" : "Add brand guideline"}
        wide
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setGuidelineForm(null)}>Cancel</button>
            <button className="btn btn-primary" onClick={saveGuideline} disabled={saving}>{saving ? "Saving…" : "Save guideline"}</button>
          </>
        }
      >
        {guidelineForm && (
          <div className="grid gap-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Title">
                <input className="input" value={guidelineForm.title || ""} onChange={(e) => setGuidelineForm({ ...guidelineForm, title: e.target.value })} placeholder="e.g. Brand tone and voice" />
              </Field>
              <Field label="Category">
                <input className="input" value={guidelineForm.category || ""} onChange={(e) => setGuidelineForm({ ...guidelineForm, category: e.target.value })} placeholder="tone, claims, terminology…" />
              </Field>
            </div>
            <Field label="Summary">
              <input className="input" value={guidelineForm.summary || ""} onChange={(e) => setGuidelineForm({ ...guidelineForm, summary: e.target.value })} />
            </Field>
            <Field label="Guideline content" hint="State the rule precisely. Verification compares submitted wording against this text.">
              <textarea className="textarea" rows={8} value={guidelineForm.content || ""} onChange={(e) => setGuidelineForm({ ...guidelineForm, content: e.target.value })} />
            </Field>
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Status">
                <select className="select" value={guidelineForm.status || "draft"} onChange={(e) => setGuidelineForm({ ...guidelineForm, status: e.target.value })}>
                  <option value="approved">Approved</option>
                  <option value="draft">Draft</option>
                </select>
              </Field>
              <Field label="Effective date">
                <input type="date" className="input" value={(guidelineForm.effective_date || "").slice(0, 10)} onChange={(e) => setGuidelineForm({ ...guidelineForm, effective_date: e.target.value })} />
              </Field>
              <Field label="Review date">
                <input type="date" className="input" value={(guidelineForm.review_date || "").slice(0, 10)} onChange={(e) => setGuidelineForm({ ...guidelineForm, review_date: e.target.value })} />
              </Field>
            </div>
          </div>
        )}
      </Modal>

      {/* ---------- document create ---------- */}
      <Modal
        open={!!documentForm}
        onClose={() => setDocumentForm(null)}
        title="Add knowledge document"
        wide
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setDocumentForm(null)}>Cancel</button>
            <button className="btn btn-primary" onClick={saveDocument} disabled={saving}>{saving ? "Saving…" : "Save document"}</button>
          </>
        }
      >
        {documentForm && (
          <div className="grid gap-3">
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Title" className="sm:col-span-2">
                <input className="input" value={documentForm.title} onChange={(e) => setDocumentForm({ ...documentForm, title: e.target.value })} />
              </Field>
              <Field label="Status">
                <select className="select" value={documentForm.status} onChange={(e) => setDocumentForm({ ...documentForm, status: e.target.value })}>
                  <option value="approved">Approved evidence</option>
                  <option value="draft">Draft / unverified</option>
                </select>
              </Field>
              <Field label="Document type">
                <select className="select" value={documentForm.doc_type} onChange={(e) => setDocumentForm({ ...documentForm, doc_type: e.target.value })}>
                  {DOC_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </Field>
              <Field label="Category">
                <input className="input" value={documentForm.category} onChange={(e) => setDocumentForm({ ...documentForm, category: e.target.value })} />
              </Field>
              <Field label="Review date">
                <input type="date" className="input" value={documentForm.review_date} onChange={(e) => setDocumentForm({ ...documentForm, review_date: e.target.value })} />
              </Field>
            </div>
            <Field label="Document text" hint="This text is extracted and retrieved during verification. Nothing is inferred beyond what you enter.">
              <textarea className="textarea" rows={10} value={documentForm.text} onChange={(e) => setDocumentForm({ ...documentForm, text: e.target.value })} />
            </Field>
          </div>
        )}
      </Modal>

      {/* ---------- document upload ---------- */}
      <Modal
        open={!!uploadForm}
        onClose={() => setUploadForm(null)}
        title="Upload brand document"
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setUploadForm(null)}>Cancel</button>
            <button className="btn btn-primary" onClick={uploadDocument} disabled={saving}>{saving ? "Uploading…" : "Upload & extract"}</button>
          </>
        }
      >
        {uploadForm && (
          <div className="grid gap-3">
            <div className="rounded-lg border p-3 text-[11.5px] muted" style={{ borderColor: "var(--bp-border)" }}>
              PDF, DOCX, TXT and MD files are supported and their real text is extracted. Images require OCR,
              which is only used when the OCR engine is available on the server; otherwise the upload is rejected
              rather than pretending it was read.
            </div>
            <Field label="File">
              <input
                type="file"
                accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg"
                className="input"
                onChange={(e) => setUploadForm({ ...uploadForm, file: e.target.files?.[0] || null, title: uploadForm.title || e.target.files?.[0]?.name || "" })}
              />
            </Field>
            <Field label="Display title">
              <input className="input" value={uploadForm.title} onChange={(e) => setUploadForm({ ...uploadForm, title: e.target.value })} />
            </Field>
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Type">
                <select className="select" value={uploadForm.doc_type} onChange={(e) => setUploadForm({ ...uploadForm, doc_type: e.target.value })}>
                  {DOC_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </Field>
              <Field label="Category">
                <input className="input" value={uploadForm.category} onChange={(e) => setUploadForm({ ...uploadForm, category: e.target.value })} />
              </Field>
              <Field label="Status">
                <select className="select" value={uploadForm.status} onChange={(e) => setUploadForm({ ...uploadForm, status: e.target.value })}>
                  <option value="draft">Draft / unverified</option>
                  <option value="approved">Approved evidence</option>
                </select>
              </Field>
            </div>
            <Field label="Review date">
              <input type="date" className="input" value={uploadForm.review_date} onChange={(e) => setUploadForm({ ...uploadForm, review_date: e.target.value })} />
            </Field>
          </div>
        )}
      </Modal>

      {/* ---------- fact modal ---------- */}
      <Modal
        open={!!factForm}
        onClose={() => setFactForm(null)}
        title="Add approved fact"
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setFactForm(null)}>Cancel</button>
            <button className="btn btn-primary" onClick={saveFact} disabled={saving}>{saving ? "Saving…" : "Save fact"}</button>
          </>
        }
      >
        {factForm && (
          <div className="grid gap-3">
            <Field label="Fact key" hint="A specific, retrievable property, e.g. NovaTech X1 battery capacity.">
              <input className="input" value={factForm.key} onChange={(e) => setFactForm({ ...factForm, key: e.target.value })} />
            </Field>
            <Field label="Approved value">
              <input className="input" value={factForm.value} onChange={(e) => setFactForm({ ...factForm, value: e.target.value })} />
            </Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Product">
                <input className="input" value={factForm.product} onChange={(e) => setFactForm({ ...factForm, product: e.target.value })} />
              </Field>
              <Field label="Category">
                <select className="select" value={factForm.category} onChange={(e) => setFactForm({ ...factForm, category: e.target.value })}>
                  {["product", "pricing", "warranty", "compliance", "company"].map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </Field>
            </div>
            <Field label="Source document">
              <select className="select" value={factForm.document_id} onChange={(e) => setFactForm({ ...factForm, document_id: e.target.value })}>
                <option value="">No source document</option>
                {documents.map((d) => <option key={d.id} value={d.id}>{d.title} ({d.status})</option>)}
              </select>
            </Field>
            <Field label="Status">
              <select className="select" value={factForm.status} onChange={(e) => setFactForm({ ...factForm, status: e.target.value })}>
                <option value="approved">Approved</option>
                <option value="draft">Draft</option>
              </select>
            </Field>
          </div>
        )}
      </Modal>

      {/* ---------- asset modal ---------- */}
      <Modal
        open={!!assetForm}
        onClose={() => setAssetForm(null)}
        title="Add brand asset"
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setAssetForm(null)}>Cancel</button>
            <button className="btn btn-primary" onClick={saveAsset} disabled={saving}>{saving ? "Saving…" : "Save asset"}</button>
          </>
        }
      >
        {assetForm && (
          <div className="grid gap-3">
            <Field label="Name">
              <input className="input" value={assetForm.name} onChange={(e) => setAssetForm({ ...assetForm, name: e.target.value })} placeholder="e.g. Primary wordmark" />
            </Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Type">
                <select className="select" value={assetForm.asset_type} onChange={(e) => setAssetForm({ ...assetForm, asset_type: e.target.value })}>
                  {["logo", "image", "colour", "font"].map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </Field>
              <Field label="Colour hex (optional)">
                <input className="input" value={assetForm.color_hex} onChange={(e) => setAssetForm({ ...assetForm, color_hex: e.target.value })} placeholder="#0B1F3A" />
              </Field>
            </div>
            <Field label="Upload file (optional)" hint="Images and logos are stored with the workspace and shown here.">
              <input type="file" className="input" accept=".png,.jpg,.jpeg,.webp,.pdf" onChange={(e) => setAssetForm({ ...assetForm, file: e.target.files?.[0] || null })} />
            </Field>
            <Field label="Notes">
              <input className="input" value={assetForm.notes} onChange={(e) => setAssetForm({ ...assetForm, notes: e.target.value })} />
            </Field>
          </div>
        )}
      </Modal>

      {/* ---------- document preview ---------- */}
      <Modal open={!!documentPreview} onClose={() => setDocumentPreview(null)} title={documentPreview?.title || "Document"} wide>
        {documentPreview && (
          <div>
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <Badge status={documentPreview.status} />
              <span className="text-[11px] muted">{documentPreview.doc_type.replace(/_/g, " ")} · v{documentPreview.version} · {documentPreview.category}</span>
            </div>
            <pre className="whitespace-pre-wrap rounded-lg border p-4 text-[12px] leading-relaxed" style={{ borderColor: "var(--bp-border)", background: "#0e1728", maxHeight: 480, overflow: "auto" }}>
              {documentPreview.extracted_text || documentPreview.file_name || "No text preview available."}
            </pre>
          </div>
        )}
      </Modal>

      <Confirm
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={deleteItem}
        title={deleteTarget?.kind === "claim" ? "Delete claim" : "Delete brand asset"}
        body={`Remove "${deleteTarget?.label || ""}" from the workspace? This cannot be undone, and the record will no longer be used during verification.`}
        confirmLabel="Delete"
        danger
      />
      <Confirm
        open={!!removeDoc}
        onClose={() => setRemoveDoc(null)}
        onConfirm={removeDocument}
        title="Remove document"
        body={`Remove "${removeDoc?.title || ""}" from the knowledge repository? This action is audited. Linked evidence references may be detached.`}
        confirmLabel="Remove"
        danger
      />
    </div>
  );
}

function SummaryChip({ label, value, hint }: { label: string; value: number; hint: string }) {
  return (
    <div className="card flex items-center justify-between gap-3 px-4 py-3">
      <div>
        <p className="eyebrow">{label}</p>
        <p className="mt-1 text-[18px] font-bold leading-none">{value}</p>
      </div>
      <p className="text-right text-[10px] muted">{hint}</p>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="muted">{label}</dt>
      <dd className="text-right font-medium">{value}</dd>
    </div>
  );
}
