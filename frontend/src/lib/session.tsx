import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Loader2, X } from "lucide-react";
import { api, ApiError, getOrg, getToken, setOrg, setToken } from "./api";
import type { Organisation, SessionPayload, User } from "./types";

interface Toast {
  id: number;
  kind: "ok" | "err";
  message: string;
}

interface SessionValue {
  user: User | null;
  org: Organisation | null;
  orgs: Organisation[];
  role: string | null;
  permissions: string[];
  loading: boolean;
  isAdmin: boolean;
  isFreelancer: boolean;
  entry: (role: "administrator" | "freelancer") => Promise<SessionPayload>;
  signOut: () => void;
  refresh: () => Promise<void>;
  toast: (kind: "ok" | "err", message: string) => void;
}

const SessionContext = createContext<SessionValue | null>(null);

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("Session context is missing");
  return value;
}

function Toasts({ toasts, dismiss }: { toasts: Toast[]; dismiss: (id: number) => void }) {
  return (
    <div className="fixed bottom-5 right-4 z-[100] flex w-[calc(100vw-2rem)] max-w-sm flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className="fade-in flex items-start gap-2.5 rounded-xl border px-3.5 py-3 text-[13px] shadow-2xl"
          style={{
            background: t.kind === "ok" ? "rgba(15,42,39,.97)" : "rgba(47,21,29,.97)",
            borderColor: t.kind === "ok" ? "rgba(0,201,154,.4)" : "rgba(255,91,112,.4)",
            color: t.kind === "ok" ? "#a4f7e2" : "#ffb7c0",
          }}
          role="status"
        >
          {t.kind === "ok" ? <CheckCircle2 size={16} className="mt-0.5 shrink-0" /> : <AlertTriangle size={16} className="mt-0.5 shrink-0" />}
          <span className="flex-1">{t.message}</span>
          <button onClick={() => dismiss(t.id)} className="opacity-60 hover:opacity-100" aria-label="Dismiss message">
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [org, setOrgState] = useState<Organisation | null>(null);
  const [orgs, setOrgs] = useState<Organisation[]>([]);
  const [role, setRole] = useState<string | null>(null);
  const [permissions, setPermissions] = useState<string[]>([]);
  const [loading, setLoading] = useState(Boolean(getToken()));
  const [toasts, setToasts] = useState<Toast[]>([]);

  const toast = useCallback((kind: "ok" | "err", message: string) => {
    const id = Date.now() + Math.random();
    setToasts((current) => [...current, { id, kind, message }]);
    window.setTimeout(() => setToasts((current) => current.filter((t) => t.id !== id)), 4600);
  }, []);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((t) => t.id !== id));
  }, []);

  const apply = useCallback((payload: SessionPayload) => {
    setToken(payload.access_token);
    const stored = getOrg();
    const active =
      payload.organisations.find((o) => o.id === stored) ||
      payload.organisations.find((o) => o.id === payload.active_organisation_id) ||
      payload.organisations[0] ||
      null;
    setOrg(active?.id || null);
    setOrgState(active);
    setOrgs(payload.organisations);
    setUser(payload.user);
    setRole(payload.role);
    setPermissions(payload.permissions || []);
    if (payload.entry_role) localStorage.setItem("bp_entry_role", payload.entry_role);
  }, []);

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const me = await api<Omit<SessionPayload, "access_token" | "token_type">>("/auth/me");
      const stored = getOrg();
      const active =
        me.organisations.find((o) => o.id === stored) ||
        me.organisations.find((o) => o.id === me.active_organisation_id) ||
        me.organisations[0] ||
        null;
      if (active) setOrg(active.id);
      setOrgState(active);
      setOrgs(me.organisations);
      setUser(me.user);
      setRole(me.role);
      setPermissions(me.permissions || []);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        setToken(null);
        setOrg(null);
        localStorage.removeItem("bp_entry_role");
        setUser(null);
        setOrgState(null);
        setRole(null);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const entry = useCallback(
    async (selected: "administrator" | "freelancer") => {
      const payload = await api<SessionPayload>("/auth/entry", {
        method: "POST",
        body: { role: selected },
      });
      apply(payload);
      return payload;
    },
    [apply],
  );

  const signOut = useCallback(() => {
    setToken(null);
    setOrg(null);
    localStorage.removeItem("bp_entry_role");
    setUser(null);
    setOrgState(null);
    setOrgs([]);
    setRole(null);
    window.location.assign("/");
  }, []);

  const value = useMemo<SessionValue>(
    () => ({
      user,
      org,
      orgs,
      role,
      permissions,
      loading,
      isAdmin: role === "admin" || role === "reviewer" || role === "approver",
      isFreelancer: role === "content_creator",
      entry,
      signOut,
      refresh,
      toast,
    }),
    [user, org, orgs, role, permissions, loading, entry, signOut, refresh, toast],
  );

  if (loading && !user) {
    return (
      <div className="flex min-h-screen items-center justify-center gap-3 text-sm" style={{ color: "var(--bp-muted)" }}>
        <Loader2 size={18} className="spin" /> Opening your workspace…
      </div>
    );
  }

  return (
    <SessionContext.Provider value={value}>
      {children}
      <Toasts toasts={toasts} dismiss={dismiss} />
    </SessionContext.Provider>
  );
}
