import { AlertTriangle, CheckCircle2, CircleHelp, FileText, Quote, ShieldQuestion, Sparkles } from "lucide-react";
import type { ExtractedClaim, Finding } from "../lib/types";
import { Badge, confidenceLabel } from "./ui";

const ICONS: Record<string, typeof CheckCircle2> = {
  supported: CheckCircle2,
  contradicted: AlertTriangle,
  unsupported: ShieldQuestion,
  inconclusive: CircleHelp,
  pending: CircleHelp,
};

export function ClaimList({ claims }: { claims: ExtractedClaim[] }) {
  if (claims.length === 0) {
    return (
      <p className="rounded-xl border border-dashed p-5 text-[12.5px] muted" style={{ borderColor: "#34435f" }}>
        No individual claims were identified in this content. Run a new analysis after the approved knowledge base changes.
      </p>
    );
  }
  return (
    <div className="space-y-3">
      {claims.map((claim) => {
        const Icon = ICONS[claim.status] || CircleHelp;
        return (
          <article key={claim.id} className="card-soft p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="flex min-w-0 items-start gap-2.5">
                <Icon
                  size={17}
                  className="mt-0.5 shrink-0"
                  style={{
                    color:
                      claim.status === "supported" ? "var(--bp-success)"
                      : claim.status === "contradicted" ? "var(--bp-danger)"
                      : claim.status === "unsupported" ? "var(--bp-warning)"
                      : "var(--bp-cyan)",
                  }}
                />
                <div className="min-w-0">
                  <p className="text-[13px] font-medium leading-snug">{claim.claim_text}</p>
                  <p className="mt-0.5 text-[10.5px] uppercase tracking-wide muted">
                    {claim.category} · {confidenceLabel(claim.confidence)} ({Math.round(claim.confidence * 100)}%)
                  </p>
                </div>
              </div>
              <Badge status={claim.status} />
            </div>

            {claim.explanation && (
              <p className="mt-3 text-[12px] leading-relaxed text-secondary">{claim.explanation}</p>
            )}

            {(claim.evidence_source_label || claim.evidence_passage) && (
              <div className="mt-3 rounded-lg border p-3" style={{ borderColor: "var(--bp-border)", background: "var(--bp-surface-inset)" }}>
                <p className="eyebrow flex items-center gap-1.5"><FileText size={11} /> Evidence</p>
                {claim.evidence_source_label && (
                  <p className="mt-1 text-[11.5px] font-semibold">{claim.evidence_source_label}</p>
                )}
                {claim.evidence_passage && (
                  <p className="mt-1 flex gap-1.5 text-[11.5px] leading-relaxed muted">
                    <Quote size={12} className="mt-0.5 shrink-0" />
                    <span>{claim.evidence_passage}</span>
                  </p>
                )}
                {claim.evidence_locator && (
                  <p className="mt-1 font-mono text-[10px] muted">{claim.evidence_locator}</p>
                )}
              </div>
            )}

            {!claim.evidence_source_label && claim.status !== "supported" && (
              <p className="mt-2 text-[11px] muted">
                No approved evidence source was available for this statement.
              </p>
            )}

            {claim.correction && (
              <div className="mt-3 rounded-lg border p-3" style={{ borderColor: "rgba(0,201,154,.22)", background: "rgba(0,201,154,.05)" }}>
                <p className="eyebrow flex items-center gap-1.5" style={{ color: "#62ddc0" }}><Sparkles size={11} /> Suggested correction</p>
                <p className="mt-1 text-[12px] leading-relaxed">{claim.correction}</p>
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}

export function FindingList({
  findings,
  claims,
  onDecide,
  busyId,
}: {
  findings: Finding[];
  claims: ExtractedClaim[];
  onDecide?: (finding: Finding, decision: "accepted" | "rejected" | "investigate") => void;
  busyId?: string | null;
}) {
  if (findings.length === 0) {
    return (
      <p className="rounded-xl border border-dashed p-5 text-[12.5px] muted" style={{ borderColor: "#34435f" }}>
        No separate guideline findings were recorded. Claim-level findings are shown above.
      </p>
    );
  }
  return (
    <div className="space-y-3">
      {findings.map((finding) => {
        const claim = claims.find((c) => c.id === finding.claim_id);
        const classification = claim?.status;
        return (
          <article key={finding.id} className="card-soft p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="text-[13px] font-semibold">{finding.title}</p>
                <p className="mt-0.5 text-[10.5px] uppercase tracking-wide muted">
                  {finding.category.replace(/_/g, " ")} · {finding.detector === "ai" ? "AI-assisted" : "Rule-based"} · {confidenceLabel(finding.confidence)}
                </p>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {classification && <Badge status={classification} />}
                <Badge status={finding.severity} />
                <Badge status={finding.status} />
              </div>
            </div>

            {finding.original_text && (
              <p className="mt-3 border-l-2 pl-3 text-[12.5px] italic leading-relaxed" style={{ borderColor: "#405478", color: "var(--bp-text)" }}>
                “{finding.original_text}”
              </p>
            )}
            <p className="mt-2.5 text-[12px] leading-relaxed text-secondary">{finding.explanation}</p>

            {(finding.source_passage || finding.guideline_ref || finding.source_locator) && (
              <div className="mt-3 rounded-lg border p-3" style={{ borderColor: "var(--bp-border)", background: "var(--bp-surface-inset)" }}>
                <p className="eyebrow">Reference</p>
                {finding.guideline_ref && <p className="mt-1 text-[11.5px]">{finding.guideline_ref}</p>}
                {finding.source_passage && <p className="mt-1 text-[11.5px] leading-relaxed muted">{finding.source_passage}</p>}
                {finding.source_locator && <p className="mt-1 font-mono text-[10px] muted">{finding.source_locator}</p>}
              </div>
            )}

            {finding.suggested_correction && (
              <div className="mt-3 rounded-lg border p-3" style={{ borderColor: "rgba(0,201,154,.22)", background: "rgba(0,201,154,.05)" }}>
                <p className="eyebrow" style={{ color: "#62ddc0" }}>Suggested correction</p>
                <p className="mt-1 text-[12px] leading-relaxed">{finding.suggested_correction}</p>
              </div>
            )}

            {onDecide && ["open", "accepted", "modified"].includes(finding.status) && (
              <div className="mt-3 flex flex-wrap gap-2">
                <button className="btn btn-sm btn-primary" disabled={busyId === finding.id} onClick={() => onDecide(finding, "accepted")}>
                  Accept correction
                </button>
                <button className="btn btn-sm btn-secondary" disabled={busyId === finding.id} onClick={() => onDecide(finding, "rejected")}>
                  Reject
                </button>
                <button className="btn btn-sm btn-secondary" disabled={busyId === finding.id} onClick={() => onDecide(finding, "investigate")}>
                  Mark for investigation
                </button>
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}
