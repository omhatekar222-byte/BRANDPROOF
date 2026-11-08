import { AlertTriangle, CheckCircle2, Info, Loader2, X } from "lucide-react";
import type { ReactNode } from "react";

const LABELS: Record<string, string> = {
  supported: "Supported",
  contradicted: "Contradicted",
  unsupported: "Unsupported",
  inconclusive: "Inconclusive",
  pending: "Pending",
  approved: "Approved",
  submitted: "Submitted",
  under_review: "Under review",
  changes_requested: "Changes requested",
  rejected: "Rejected",
  draft: "Draft",
  archived: "Archived",
  outdated: "Outdated",
  prohibited: "Prohibited",
  open: "Open",
  accepted: "Accepted",
  modified: "Modified",
  resolved: "Resolved",
  low: "Low",
  medium: "Medium",
  high: "High",
  critical: "Critical",
  assigned: "Assigned",
  accepted_task: "Accepted",
  in_progress: "In progress",
  submitted_task: "Submitted",
  resubmitted: "Resubmitted",
  awaiting_manager_approval: "Awaiting approval",
  completed: "Completed",
  active: "Active",
  paused: "Paused",
  cancelled: "Cancelled",
  logo: "Logo",
  colour: "Colour",
  font: "Font",
  image: "Image",
  needs_evidence: "Needs evidence",
  demo: "Demo data",
  ai: "AI analysed",
  rule: "Rule check",
};

export function statusLabel(status: string): string {
  return LABELS[status] || status.replace(/_/g, " ");
}

export function Badge({ status, label }: { status: string; label?: string }) {
  return <span className={`badge b-${status}`}>{label || statusLabel(status)}</span>;
}

export function Avatar({ name, color, size = 30 }: { name: string; color?: string | null; size?: number }) {
  const initials = name
    .split(" ")
    .filter(Boolean)
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  return (
    <span
      className="avatar"
      style={{ width: size, height: size, background: color || "#8b5cf6", fontSize: Math.max(9, size * 0.33) }}
      title={name}
    >
      {initials || "?"}
    </span>
  );
}

export function PageHeader({
  title,
  subtitle,
  actions,
  eyebrow,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  eyebrow?: string;
}) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div>
        {eyebrow && <p className="eyebrow mb-1.5">{eyebrow}</p>}
        <h1 className="page-title">{title}</h1>
        {subtitle && <p className="page-sub">{subtitle}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Stat({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: ReactNode;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="card card-pad">
      <p className="eyebrow">{label}</p>
      <p className="mt-1.5 text-[26px] font-bold leading-none tracking-tight" style={{ color: color || "var(--bp-ink)" }}>
        {value}
      </p>
      {sub && <p className="mt-1.5 text-[11px] muted">{sub}</p>}
    </div>
  );
}

export function Empty({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      {hint && <p className="mx-auto max-w-md text-[12.5px]">{hint}</p>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div
      className="flex items-start gap-2 rounded-xl border p-3 text-[12.5px]"
      style={{ borderColor: "var(--bp-danger-note-border)", background: "var(--bp-danger-note-bg)", color: "var(--bp-danger-note-text)" }}
    >
      <AlertTriangle size={15} className="mt-0.5 shrink-0" />
      <span>{message}</span>
    </div>
  );
}

export function InfoNote({ children }: { children: ReactNode }) {
  return (
    <div
      className="flex items-start gap-2 rounded-xl border p-3 text-[12.5px]"
      style={{ borderColor: "var(--bp-info-note-border)", background: "var(--bp-info-note-bg)", color: "var(--bp-info-note-text)" }}
    >
      <Info size={15} className="mt-0.5 shrink-0" />
      <span>{children}</span>
    </div>
  );
}

export function SuccessNote({ children }: { children: ReactNode }) {
  return (
    <div
      className="flex items-start gap-2 rounded-xl border p-3 text-[12.5px]"
      style={{ borderColor: "var(--bp-success-note-border)", background: "var(--bp-success-note-bg)", color: "var(--bp-success-note-text)" }}
    >
      <CheckCircle2 size={15} className="mt-0.5 shrink-0" />
      <span>{children}</span>
    </div>
  );
}

export function Spinner({ size = 16 }: { size?: number }) {
  return <Loader2 size={size} className="spin" />;
}

export function LoadingBlock({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2.5 py-10 text-[13px] muted">
      <Spinner /> {label}
    </div>
  );
}

export function Field({
  label,
  hint,
  children,
  className,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={`block ${className || ""}`}>
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint block">{hint}</span>}
    </label>
  );
}

export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  wide,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  if (!open) return null;
  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div
        className="modal-panel"
        style={wide ? { maxWidth: 820 } : undefined}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="modal-head">
          <h2 className="section-title">{title}</h2>
          <button onClick={onClose} className="btn btn-ghost btn-icon" aria-label="Close dialog">
            <X size={17} />
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && (
          <div className="flex flex-wrap justify-end gap-2 border-t px-5 py-3.5" style={{ borderColor: "var(--bp-border)" }}>
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

export function Confirm({
  open,
  onClose,
  onConfirm,
  title,
  body,
  confirmLabel = "Confirm",
  danger,
  error,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  body: string;
  confirmLabel?: string;
  danger?: boolean;
  error?: string;
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      footer={
        <>
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button className={`btn ${danger ? "btn-danger" : "btn-primary"}`} onClick={onConfirm}>{confirmLabel}</button>
        </>
      }
    >
      <p className="text-[13px] text-secondary">{body}</p>
      {error && <div className="mt-3"><ErrorNote message={error} /></div>}
    </Modal>
  );
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toLocaleString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 16).replace("T", " ");
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  if (Number.isNaN(diff)) return "—";
  const minutes = Math.round(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return fmtDate(iso);
}

export function confidenceLabel(value: number): string {
  if (value >= 0.8) return "High confidence";
  if (value >= 0.55) return "Medium confidence";
  return "Low confidence";
}
