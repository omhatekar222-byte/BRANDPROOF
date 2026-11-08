import { useState } from "react";
import { ArrowRight, ClipboardCheck, FileSearch, ShieldCheck, Sparkles, UserRound, Users } from "lucide-react";
import { useSession } from "../lib/session";
import { ErrorNote, Spinner } from "../components/ui";
import ThemeToggle from "../components/ThemeToggle";

type Role = "administrator" | "freelancer";

export default function EntryPage() {
  const { entry } = useSession();
  const [busy, setBusy] = useState<Role | null>(null);
  const [error, setError] = useState("");

  const choose = async (role: Role) => {
    setBusy(role);
    setError("");
    try {
      await entry(role);
      window.location.assign("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "The workspace could not be opened.");
      setBusy(null);
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden" style={{ background: "var(--bp-bg)", color: "var(--bp-ink)" }}>
      <div
        className="pointer-events-none absolute left-1/2 top-[-260px] h-[520px] w-[820px] -translate-x-1/2 rounded-full blur-[110px]"
        style={{ background: "radial-gradient(circle, color-mix(in srgb, var(--bp-violet) 22%, transparent), transparent 68%)" }}
      />
      <div
        className="pointer-events-none absolute bottom-[-240px] right-[-160px] h-[520px] w-[520px] rounded-full blur-[110px]"
        style={{ background: "radial-gradient(circle, color-mix(in srgb, var(--bp-cyan) 12%, transparent), transparent 70%)" }}
      />

      <div className="relative mx-auto flex min-h-screen w-full max-w-6xl flex-col px-5 py-7 sm:px-8">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className="brand-mark"><ShieldCheck size={19} /></span>
            <div>
              <p className="text-[15px] font-bold tracking-tight">BRANDPROOF</p>
              <p className="text-[9px] uppercase tracking-[.16em]" style={{ color: "var(--bp-muted)" }}>Brand governance</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <span className="badge b-demo">NovaTech demo workspace</span>
          </div>
        </div>

        <div className="flex flex-1 flex-col justify-center py-12">
          <div className="mx-auto w-full max-w-3xl text-center">
            <p className="eyebrow mb-3">One identity. Every platform. Every time.</p>
            <h1 className="text-[34px] font-bold leading-[1.12] tracking-[-0.03em] sm:text-[46px]">
              Verify every claim.
              <br />
              <span style={{ color: "var(--bp-violet-text)" }}>Protect the brand.</span>
            </h1>
            <p className="mx-auto mt-4 max-w-xl text-[13.5px] leading-relaxed" style={{ color: "var(--bp-text)" }}>
              BrandProof turns approved company knowledge into evidence-backed content verification.
              Choose a workspace to begin — no password is required in this demonstration.
            </p>
          </div>

          <div className="mx-auto mt-10 grid w-full max-w-4xl gap-4 sm:grid-cols-2">
            <button
              onClick={() => choose("administrator")}
              disabled={busy !== null}
              className="card card-pad hover-card group text-left disabled:opacity-60"
              style={{ padding: 26 }}
            >
              <div className="flex items-start justify-between">
                <span className="grid h-11 w-11 place-items-center rounded-xl" style={{ background: "var(--bp-violet-soft)", color: "var(--bp-violet-text)", border: "1px solid color-mix(in srgb, var(--bp-violet) 24%, transparent)" }}>
                  <Users size={20} />
                </span>
                <ArrowRight size={17} className="mt-1 transition-transform group-hover:translate-x-0.5" style={{ color: "var(--bp-muted)" }} />
              </div>
              <h2 className="mt-4 text-[18px] font-semibold tracking-tight">Administrator</h2>
              <p className="mt-2 text-[12.5px] leading-relaxed" style={{ color: "var(--bp-muted)" }}>
                Maintain brand knowledge, verify submitted content, manage campaigns, review recurring
                mistakes, and make final approval decisions.
              </p>
              <div className="mt-5 flex flex-wrap gap-x-3 gap-y-1.5 text-[10.5px]" style={{ color: "var(--bp-hint)" }}>
                <span className="flex items-center gap-1"><FileSearch size={11} /> Content review</span>
                <span className="flex items-center gap-1"><Sparkles size={11} /> Intelligence</span>
                <span className="flex items-center gap-1"><ShieldCheck size={11} /> Approvals</span>
              </div>
              <span className="mt-5 inline-flex items-center gap-1.5 text-[12px] font-semibold" style={{ color: "var(--bp-violet-text)" }}>
                {busy === "administrator" ? <><Spinner size={13} /> Opening…</> : <>Open administrator workspace <ArrowRight size={13} /></>}
              </span>
            </button>

            <button
              onClick={() => choose("freelancer")}
              disabled={busy !== null}
              className="card card-pad hover-card group text-left disabled:opacity-60"
              style={{ padding: 26 }}
            >
              <div className="flex items-start justify-between">
                <span className="grid h-11 w-11 place-items-center rounded-xl" style={{ background: "var(--bp-cyan-soft)", color: "var(--bp-cyan-text)", border: "1px solid color-mix(in srgb, var(--bp-cyan) 22%, transparent)" }}>
                  <UserRound size={20} />
                </span>
                <ArrowRight size={17} className="mt-1 transition-transform group-hover:translate-x-0.5" style={{ color: "var(--bp-muted)" }} />
              </div>
              <h2 className="mt-4 text-[18px] font-semibold tracking-tight">Freelancer</h2>
              <p className="mt-2 text-[12.5px] leading-relaxed" style={{ color: "var(--bp-muted)" }}>
                View assigned tasks, read the approved campaign brief, submit content, receive
                evidence-backed AI feedback, and correct issues before approval.
              </p>
              <div className="mt-5 flex flex-wrap gap-x-3 gap-y-1.5 text-[10.5px]" style={{ color: "var(--bp-hint)" }}>
                <span className="flex items-center gap-1"><ClipboardCheck size={11} /> Assigned tasks</span>
                <span className="flex items-center gap-1"><Sparkles size={11} /> AI feedback</span>
                <span className="flex items-center gap-1"><FileSearch size={11} /> Corrections</span>
              </div>
              <span className="mt-5 inline-flex items-center gap-1.5 text-[12px] font-semibold" style={{ color: "var(--bp-cyan-text)" }}>
                {busy === "freelancer" ? <><Spinner size={13} /> Opening…</> : <>Open freelancer workspace <ArrowRight size={13} /></>}
              </span>
            </button>
          </div>

          {error && <div className="mx-auto mt-5 w-full max-w-4xl"><ErrorNote message={error} /></div>}

          <p className="mx-auto mt-8 max-w-2xl text-center text-[10.5px] leading-relaxed" style={{ color: "var(--bp-muted)" }}>
            Demonstration mode. The verification engine runs deterministic evidence checks against the
            seeded NovaTech knowledge base and labels every result as demo output. Human approval is
            always required before content is published.
          </p>
        </div>
      </div>
    </div>
  );
}
