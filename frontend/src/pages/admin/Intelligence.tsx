import { useCallback, useEffect, useState } from "react";
import { BrainCircuit, CheckCircle2, Lightbulb, RefreshCw, XCircle } from "lucide-react";
import { api, ApiError } from "../../lib/api";
import { useSession } from "../../lib/session";
import type { GuidelineProposal, Page, RecurringGroup } from "../../lib/types";
import {
  Badge,
  Confirm,
  Empty,
  ErrorNote,
  Field,
  InfoNote,
  LoadingBlock,
  Modal,
  PageHeader,
  SuccessNote,
  fmtDateTime,
  timeAgo,
} from "../../components/ui";

interface AffectedContent {
  id: string;
  title: string;
  status: string;
  content_type?: string;
  campaign?: string;
}

interface GroupDetail extends RecurringGroup {
  root_cause_label?: string;
  affected_content: AffectedContent[];
  proposals: GuidelineProposal[];
  guideline?: { id: string; title: string; category: string; content: string; version: number; status: string } | null;
}

export default function IntelligencePage() {
  const { toast } = useSession();
  const [groups, setGroups] = useState<RecurringGroup[]>([]);
  const [proposals, setProposals] = useState<GuidelineProposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [detail, setDetail] = useState<GroupDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [proposalFor, setProposalFor] = useState<GroupDetail | null>(null);
  const [creatingProposal, setCreatingProposal] = useState(false);

  const [decisionFor, setDecisionFor] = useState<{ proposal: GuidelineProposal; decision: "approved" | "rejected" | "modified" } | null>(null);
  const [decisionNotes, setDecisionNotes] = useState("");
  const [deciding, setDeciding] = useState(false);

  const flash = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 5000);
  };

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [groupPage, proposalPage] = await Promise.all([
        api<Page<RecurringGroup>>("/intelligence/groups?page_size=100"),
        api<Page<GuidelineProposal>>("/intelligence/proposals?page_size=100"),
      ]);
      setGroups(groupPage.items);
      setProposals(proposalPage.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Guideline intelligence could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const openGroup = async (groupId: string) => {
    setDetail(null);
    setDetailLoading(true);
    try {
      const data = await api<GroupDetail>(`/intelligence/groups/${groupId}`);
      setDetail(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The pattern details could not be loaded.");
    } finally {
      setDetailLoading(false);
    }
  };

  const analyze = async () => {
    setAnalyzing(true);
    setError("");
    try {
      const result = await api<{ total: number }>("/intelligence/analyze", {
        method: "POST",
        body: { rebuild: true },
      });
      await load();
      flash(`Feedback analysis complete. ${result.total} recurring pattern(s) identified from stored reviewer feedback.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Feedback analysis could not be completed.");
    } finally {
      setAnalyzing(false);
    }
  };

  const createProposal = async () => {
    if (!proposalFor) return;
    setCreatingProposal(true);
    setError("");
    try {
      await api(`/intelligence/groups/${proposalFor.id}/proposal`, { method: "POST" });
      toast("ok", "Guideline proposal created and queued for a decision.");
      setProposalFor(null);
      await load();
      if (detail?.id === proposalFor.id) await openGroup(proposalFor.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The proposal could not be created.");
    } finally {
      setCreatingProposal(false);
    }
  };

  const decideProposal = async () => {
    if (!decisionFor) return;
    setDeciding(true);
    setError("");
    try {
      await api(`/intelligence/proposals/${decisionFor.proposal.id}/decision`, {
        method: "POST",
        body: { decision: decisionFor.decision, notes: decisionNotes.trim() || undefined },
      });
      const label = decisionFor.decision === "approved" ? "approved" : decisionFor.decision === "rejected" ? "rejected" : "modified";
      flash(`Proposal ${label}. ${decisionFor.decision === "approved" ? "If linked to a guideline, the approved clarification has been applied and versioned." : "No guideline changes were applied."}`);
      setDecisionFor(null);
      setDecisionNotes("");
      await load();
      if (detail) await openGroup(detail.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The proposal decision could not be saved.");
    } finally {
      setDeciding(false);
    }
  };

  return (
    <div className="fade-in">
      <PageHeader
        eyebrow="Reviewer feedback patterns · advisory only"
        title="Guideline Intelligence"
        subtitle="Recurring issues are grouped from stored reviewer feedback. Root causes and proposals are transparent, rule-based hypotheses — nothing is applied to guidelines without an explicit human decision."
        actions={
          <button className="btn btn-primary" onClick={analyze} disabled={analyzing}>
            <RefreshCw size={14} className={analyzing ? "spin" : ""} /> {analyzing ? "Analyzing…" : "Analyze feedback"}
          </button>
        }
      />

      <InfoNote>
        This workspace does not train or fine-tune a model on your feedback. Patterns are derived from structured review records so every suggestion can be inspected and audited.
      </InfoNote>

      {notice && <div className="mt-4"><SuccessNote>{notice}</SuccessNote></div>}
      {error && <div className="mt-4"><ErrorNote message={error} /></div>}

      {loading ? (
        <div className="mt-4"><LoadingBlock label="Loading guideline intelligence…" /></div>
      ) : (
        <div className="mt-5 space-y-5">
          <section className="card overflow-hidden">
            <div className="border-b px-4 py-3" style={{ borderColor: "var(--bp-border)" }}>
              <h2 className="section-title flex items-center gap-2"><BrainCircuit size={15} /> Recurring patterns</h2>
              <p className="text-[11px] muted">{groups.length} group{groups.length === 1 ? "" : "s"} found from reviewer feedback</p>
            </div>
            {groups.length === 0 ? (
              <div className="p-4">
                <Empty
                  title="No recurring patterns yet"
                  hint="Patterns appear after reviewers leave structured feedback on findings. Run analysis once feedback has been recorded."
                  action={<button className="btn btn-secondary" onClick={analyze} disabled={analyzing}><RefreshCw size={14} /> Analyze feedback</button>}
                />
              </div>
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr><th>Pattern</th><th>Category</th><th>Possible cause</th><th>Findings</th><th>Status</th><th>Last seen</th></tr>
                  </thead>
                  <tbody>
                    {groups.map((g) => (
                      <tr key={g.id} className="cursor-pointer" onClick={() => void openGroup(g.id)}>
                        <td className="primary-cell max-w-[360px]">
                          <button className="text-left hover:underline" onClick={(e) => { e.stopPropagation(); void openGroup(g.id); }}>
                            {g.title}
                          </button>
                          <div className="mt-0.5 line-clamp-1 text-[10.5px] muted">{g.suggested_improvement}</div>
                        </td>
                        <td className="capitalize">{g.category.replace(/_/g, " ")}</td>
                        <td className="max-w-[220px] truncate text-[11.5px]">{(g as RecurringGroup & { root_cause_label?: string }).root_cause_label || g.possible_root_cause?.replace(/_/g, " ") || "—"}</td>
                        <td>{g.finding_count} · {(g.affected_submission_ids || []).length} submission(s)</td>
                        <td><Badge status={g.status} /></td>
                        <td className="text-[11px] muted">{timeAgo(g.last_seen)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="card overflow-hidden">
            <div className="border-b px-4 py-3" style={{ borderColor: "var(--bp-border)" }}>
              <h2 className="section-title flex items-center gap-2"><Lightbulb size={15} /> Guideline proposals</h2>
              <p className="text-[11px] muted">Proposals require an explicit approval decision before any guideline is created or changed.</p>
            </div>
            {proposals.length === 0 ? (
              <p className="p-4 text-[12.5px] muted">No proposals yet. Open a recurring pattern and create a proposal when the evidence supports a guideline clarification.</p>
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr><th>Proposal</th><th>Root cause</th><th>Status</th><th>Created</th><th /></tr>
                  </thead>
                  <tbody>
                    {proposals.map((p) => (
                      <tr key={p.id}>
                        <td className="primary-cell max-w-[420px]">
                          <p className="font-semibold">{p.title}</p>
                          <p className="mt-0.5 line-clamp-2 text-[10.5px] muted">{p.proposed_rule}</p>
                        </td>
                        <td className="capitalize text-[11.5px]">{(p.root_cause || "—").replace(/_/g, " ")}</td>
                        <td><Badge status={p.status} /></td>
                        <td className="text-[11px] muted">{fmtDateTime(p.created_at)}</td>
                        <td>
                          {p.status === "pending" ? (
                            <div className="flex justify-end gap-1.5">
                              <button className="btn btn-ghost btn-sm" onClick={() => { setDecisionNotes(""); setDecisionFor({ proposal: p, decision: "approved" }); }} title="Approve proposal">
                                <CheckCircle2 size={13} /> Approve
                              </button>
                              <button className="btn btn-ghost btn-sm" onClick={() => { setDecisionNotes(""); setDecisionFor({ proposal: p, decision: "rejected" }); }} title="Reject proposal">
                                <XCircle size={13} /> Reject
                              </button>
                            </div>
                          ) : (
                            <span className="text-[10.5px] muted">{p.decided_at ? `Decided ${timeAgo(p.decided_at)}` : "—"}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      )}

      {/* group detail */}
      <Modal open={!!detail || detailLoading} onClose={() => { setDetail(null); setDetailLoading(false); }} title={detail?.title || "Recurring pattern"} wide>
        {detailLoading && <LoadingBlock label="Loading pattern evidence…" />}
        {detail && !detailLoading && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge status={detail.status} />
              <span className="text-[11px] muted">{detail.finding_count} findings · {detail.affected_content.length} submissions</span>
            </div>
            <div className="rounded-lg border p-3" style={{ borderColor: "var(--bp-border)", background: "var(--bp-surface-inset)" }}>
              <p className="eyebrow">Possible cause</p>
              <p className="mt-1 text-[12px]">{detail.root_cause_note}</p>
              <p className="mt-2 text-[11.5px] leading-relaxed" style={{ color: "#a7dfe9" }}>{detail.suggested_improvement}</p>
            </div>
            <div>
              <h3 className="section-title mb-2">Affected submissions</h3>
              {detail.affected_content.length === 0 ? (
                <p className="text-[12px] muted">No affected submissions recorded for this pattern.</p>
              ) : (
                <ul className="space-y-1.5">
                  {detail.affected_content.map((item) => (
                    <li key={item.id} className="flex items-center justify-between gap-2 rounded-lg border px-3 py-2" style={{ borderColor: "var(--bp-border)" }}>
                      <span className="min-w-0 truncate text-[12px]">{item.title}</span>
                      <span className="flex items-center gap-2"><span className="text-[10.5px] muted">{item.campaign}</span><Badge status={item.status} /></span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            {detail.proposals.length > 0 && (
              <div>
                <h3 className="section-title mb-2">Proposals for this pattern</h3>
                {detail.proposals.map((p) => (
                  <div key={p.id} className="mb-2 rounded-lg border p-3" style={{ borderColor: "var(--bp-border)" }}>
                    <div className="flex items-center justify-between gap-2"><p className="text-[12px] font-semibold">{p.title}</p><Badge status={p.status} /></div>
                    <p className="mt-1 text-[11.5px] muted">{p.proposed_rule}</p>
                  </div>
                ))}
              </div>
            )}
            <div className="flex justify-end gap-2">
              {detail.status === "open" && (
                <button className="btn btn-primary" onClick={() => { setProposalFor(detail); setDetail(null); }}>
                  <Lightbulb size={14} /> Create proposal
                </button>
              )}
              <button className="btn btn-secondary" onClick={() => setDetail(null)}>Close</button>
            </div>
          </div>
        )}
      </Modal>

      <Confirm
        open={!!proposalFor}
        onClose={() => setProposalFor(null)}
        onConfirm={createProposal}
        title="Create a guideline proposal?"
        body={`This creates a pending proposal from “${proposalFor?.title || "this pattern"}” using the stored reviewer feedback as evidence. No guideline will be changed until the proposal is explicitly approved.`}
        confirmLabel={creatingProposal ? "Creating…" : "Create proposal"}
        error={error && proposalFor ? error : undefined}
      />

      <Modal
        open={!!decisionFor}
        onClose={() => { setDecisionFor(null); setDecisionNotes(""); }}
        title={decisionFor?.decision === "approved" ? "Approve proposal" : decisionFor?.decision === "rejected" ? "Reject proposal" : "Modify proposal"}
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => { setDecisionFor(null); setDecisionNotes(""); }}>Cancel</button>
            <button
              className={`btn ${decisionFor?.decision === "rejected" ? "btn-danger" : "btn-primary"}`}
              onClick={decideProposal}
              disabled={deciding}
            >
              {deciding ? "Saving…" : decisionFor?.decision === "approved" ? "Approve" : decisionFor?.decision === "rejected" ? "Reject" : "Record decision"}
            </button>
          </>
        }
      >
        {decisionFor && (
          <div className="space-y-3">
            <p className="text-[12.5px] font-semibold">{decisionFor.proposal.title}</p>
            <p className="text-[12px] text-secondary">{decisionFor.proposal.proposed_rule}</p>
            {decisionFor.decision === "approved" && (
              <InfoNote>Approving applies the clarification only through the governed guideline/proposal flow. If a guideline is linked or created, the change is versioned and audited.</InfoNote>
            )}
            <Field label="Decision notes (optional)">
              <textarea className="textarea" rows={3} value={decisionNotes} onChange={(e) => setDecisionNotes(e.target.value)} placeholder="Record why this proposal was approved or rejected." />
            </Field>
            {error && <ErrorNote message={error} />}
          </div>
        )}
      </Modal>
    </div>
  );
}
