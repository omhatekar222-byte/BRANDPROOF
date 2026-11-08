import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  Bell, BookOpenCheck, BrainCircuit, BriefcaseBusiness, CheckCheck, ChevronRight,
  ClipboardList, Database, FileSearch, LayoutDashboard, LogOut, Menu, RefreshCw, ScanSearch, Search,
  Send, ShieldCheck, Sparkles, Wallet, X, MessageSquareWarning,
} from "lucide-react";
import { api, qs } from "../lib/api";
import { useSession } from "../lib/session";
import type { Member, NotificationItem, Page, Submission, Task } from "../lib/types";
import ThemeToggle from "./ThemeToggle";
import { Avatar, Badge, Confirm, Spinner, timeAgo } from "./ui";

interface NavItem {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  end?: boolean;
  badge?: number;
}

interface SearchResult {
  label: string;
  hint: string;
  to: string;
}

const ADMIN_NAV: NavItem[] = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/knowledge", label: "Brand Knowledge", icon: Database },
  { to: "/review", label: "Content Review", icon: FileSearch },
  { to: "/campaigns", label: "Campaigns", icon: BriefcaseBusiness },
  { to: "/intelligence", label: "Intelligence", icon: BrainCircuit },
  { to: "/approvals", label: "Approval Centre", icon: ShieldCheck },
];

const FREELANCER_NAV: NavItem[] = [
  { to: "/", label: "My Dashboard", icon: LayoutDashboard, end: true },
  { to: "/wallet", label: "Knowledge Wallet", icon: Wallet },
  { to: "/scanner", label: "Campaign Scanner", icon: ScanSearch },
  { to: "/tasks", label: "Assigned Tasks", icon: ClipboardList },
  { to: "/submit", label: "Submit Content", icon: Send },
  { to: "/submissions", label: "My Submissions", icon: BookOpenCheck },
  { to: "/feedback", label: "Feedback & Corrections", icon: MessageSquareWarning },
];

function BrandMark() {
  return (
    <Link to="/" className="brand-block">
      <span className="brand-mark">
        <ShieldCheck size={19} />
      </span>
      <span>
        <span className="brand-name block">BrandProof</span>
        <span className="brand-tag block">One Identity · Every Platform</span>
      </span>
    </Link>
  );
}

function SearchPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { isAdmin } = useSession();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) {
      setQuery("");
      setResults([]);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const term = query.trim();
    if (term.length < 2) {
      setResults([]);
      return;
    }
    let cancelled = false;
    setBusy(true);
    const timer = window.setTimeout(async () => {
      const found: SearchResult[] = [];
      try {
        const subs = await api<Page<Submission>>(`/content/submissions${qs({ q: term, page_size: 6 })}`);
        for (const s of subs.items) {
          found.push({
            label: s.title,
            hint: `${isAdmin ? "Submission" : "My submission"} · ${s.status.replace(/_/g, " ")}`,
            to: isAdmin ? `/review/${s.id}` : `/submissions/${s.id}`,
          });
        }
      } catch { /* search is best-effort */ }
      if (isAdmin) {
        try {
          const knowledge = await api<{ items: { title: string; text: string }[] }>(
            `/knowledge/search${qs({ q: term, limit: 5 })}`,
          );
          for (const k of knowledge.items) {
            found.push({ label: k.title, hint: "Knowledge evidence", to: "/knowledge" });
          }
        } catch { /* optional */ }
      }
      try {
        const tasks = await api<{ items: Task[] }>("/tasks");
        for (const t of tasks.items.filter((item) =>
          (item.title + " " + item.campaign_name).toLowerCase().includes(term.toLowerCase()),
        ).slice(0, 4)) {
          found.push({
            label: t.title,
            hint: `Task · ${t.campaign_name}`,
            to: isAdmin ? "/campaigns" : `/tasks/${t.id}`,
          });
        }
      } catch { /* optional */ }
      if (!cancelled) {
        setResults(found.slice(0, 12));
        setBusy(false);
      }
    }, 260);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query, open, isAdmin]);

  if (!open) return null;
  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div className="modal-panel" style={{ maxWidth: 620 }} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2.5 border-b px-4 py-3" style={{ borderColor: "var(--bp-border)" }}>
          <Search size={17} style={{ color: "var(--bp-muted)" }} />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={isAdmin ? "Search submissions, knowledge, tasks…" : "Search your submissions and tasks…"}
            className="w-full bg-transparent text-[13.5px] outline-none"
            style={{ color: "var(--bp-ink)" }}
          />
          <button onClick={onClose} className="btn btn-ghost btn-icon" aria-label="Close search">
            <X size={16} />
          </button>
        </div>
        <div className="max-h-[55vh] overflow-y-auto p-2">
          {query.trim().length < 2 && (
            <p className="px-3 py-8 text-center text-[12.5px] muted">
              Type at least two characters to search workspace records.
            </p>
          )}
          {busy && <p className="flex items-center gap-2 px-3 py-6 text-[12.5px] muted"><Spinner /> Searching…</p>}
          {!busy && query.trim().length >= 2 && results.length === 0 && (
            <p className="px-3 py-8 text-center text-[12.5px] muted">No matching records found.</p>
          )}
          {results.map((r, i) => (
            <button
              key={`${r.to}-${i}`}
              onClick={() => { onClose(); navigate(r.to); }}
              className="flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2.5 text-left text-[12.5px] hover:bg-[var(--bp-hover)]"
            >
              <span className="truncate" style={{ color: "var(--bp-ink)" }}>{r.label}</span>
              <span className="shrink-0 text-[10.5px] muted">{r.hint}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const { user, org, role, isAdmin, signOut, toast } = useSession();
  const [resetOpen, setResetOpen] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unread, setUnread] = useState(0);
  const [queueCount, setQueueCount] = useState(0);
  const location = useLocation();
  const navigate = useNavigate();
  const notifRef = useRef<HTMLDivElement | null>(null);
  const profileRef = useRef<HTMLDivElement | null>(null);

  const nav = isAdmin ? ADMIN_NAV : FREELANCER_NAV;

  const loadNotifications = useCallback(async () => {
    try {
      const [list, count] = await Promise.all([
        api<Page<NotificationItem>>("/notifications?page_size=8"),
        api<{ unread_count: number }>("/notifications/unread-count"),
      ]);
      setNotifications(list.items);
      setUnread(count.unread_count);
    } catch { /* notifications are non-critical */ }
  }, []);

  useEffect(() => {
    setMobileOpen(false);
    setNotifOpen(false);
    setProfileOpen(false);
    void loadNotifications();
  }, [location.pathname, loadNotifications]);

  useEffect(() => {
    if (!isAdmin) { setQueueCount(0); return; }
    api<{ queue: Record<string, number> }>("/review/stats")
      .then((s) => setQueueCount((s.queue?.submitted || 0) + (s.queue?.under_review || 0)))
      .catch(() => setQueueCount(0));
  }, [isAdmin, location.pathname]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen(true);
      }
      if (e.key === "Escape") {
        setSearchOpen(false);
        setNotifOpen(false);
        setProfileOpen(false);
      }
    };
    const onClick = (e: MouseEvent) => {
      const target = e.target as Node;
      if (notifRef.current && !notifRef.current.contains(target)) setNotifOpen(false);
      if (profileRef.current && !profileRef.current.contains(target)) setProfileOpen(false);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onClick);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onClick);
    };
  }, []);

  const roleLabel = role === "admin" ? "Administrator" : role === "content_creator" ? "Freelancer" : role || "Member";
  const pageLabel = useMemo(() => {
    const active = [...ADMIN_NAV, ...FREELANCER_NAV]
      .filter((n) => (n.end ? location.pathname === n.to : location.pathname.startsWith(n.to)))
      .sort((a, b) => b.to.length - a.to.length)[0];
    return active?.label || "BrandProof";
  }, [location.pathname]);

  const resetDemo = async () => {
    setResetting(true);
    try {
      await api("/admin/demo/reset", { method: "POST" });
      toast("ok", "Demonstration workspace rebuilt from the original seed data.");
      setResetOpen(false);
      window.setTimeout(() => window.location.assign("/"), 700);
    } catch (err) {
      toast("err", err instanceof Error ? err.message : "The demo workspace could not be reset.");
    } finally {
      setResetting(false);
    }
  };

  const markAllRead = async () => {
    try {
      await api("/notifications/mark-read", { method: "POST", body: { all: true } });
      setUnread(0);
      setNotifications((items) => items.map((n) => ({ ...n, is_read: true })));
    } catch { /* ignore */ }
  };

  return (
    <div className="shell">
      {mobileOpen && <div className="sidebar-overlay" onClick={() => setMobileOpen(false)} />}
      <aside className={`sidebar ${mobileOpen ? "open" : ""}`}>
        <BrandMark />
        <div className="sidebar-scroll">
          <p className="nav-group-label">{isAdmin ? "Governance" : "Creator workspace"}</p>
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
            >
              <item.icon size={16} />
              <span>{item.label}</span>
              {isAdmin && item.to === "/review" && queueCount > 0 && (
                <span className="nav-badge">{queueCount}</span>
              )}
            </NavLink>
          ))}

          {isAdmin && (
            <>
              <p className="nav-group-label">Reference</p>
              <Link to="/knowledge?tab=guidelines" className="nav-link">
                <Sparkles size={16} /> Brand guidelines
              </Link>
              <Link to="/knowledge?tab=claims" className="nav-link">
                <ShieldCheck size={16} /> Approved claims
              </Link>
            </>
          )}
        </div>

        <div className="sidebar-foot">
          <div className="workspace-card">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-[12px] font-semibold">{org?.name || "Workspace"}</span>
              {org?.is_demo && <Badge status="demo" label="Demo" />}
            </div>
            <div className="mt-1.5 flex items-center justify-between gap-2">
              <span className="text-[10.5px] muted">{org?.industry || "Brand workspace"}</span>
              <span className="role-chip">{roleLabel}</span>
            </div>
            <div className="mt-2.5 flex gap-1.5">
              <button
                onClick={signOut}
                className="btn btn-ghost btn-sm flex-1"
                title="Return to the administrator / freelancer selection screen"
              >
                <LogOut size={12} /> Switch role
              </button>
              {isAdmin && org?.is_demo && (
                <button
                  onClick={() => { setProfileOpen(false); setResetOpen(true); }}
                  className="btn btn-ghost btn-sm flex-1"
                  title="Delete the seeded NovaTech demo records and rebuild them from the original seed. Your session will reload."
                >
                  <RefreshCw size={12} /> Reset demo data
                </button>
              )}
            </div>
          </div>
        </div>
      </aside>

      <div className="main-col">
        <header className="topbar">
          <button className="btn btn-ghost btn-icon mobile-only" onClick={() => setMobileOpen(true)} aria-label="Open navigation">
            <Menu size={19} />
          </button>
          <div className="flex min-w-0 items-center gap-1.5 text-[12.5px]">
            <span className="hide-mobile muted">{isAdmin ? "Administrator" : "Freelancer"}</span>
            <ChevronRight size={13} className="hide-mobile muted" />
            <span className="truncate font-semibold">{pageLabel}</span>
          </div>

          <div className="ml-auto flex flex-1 justify-end">
            <button className="search-btn" onClick={() => setSearchOpen(true)}>
              <Search size={14} />
              <span className="truncate">Search workspace…</span>
              <span className="kbd ml-auto hide-mobile">Ctrl K</span>
            </button>
          </div>

          <ThemeToggle />

          <div className="relative" ref={notifRef}>
            <button
              className="btn btn-secondary btn-icon relative"
              onClick={() => { setNotifOpen((v) => !v); setProfileOpen(false); }}
              aria-label="Notifications"
            >
              <Bell size={16} />
              {unread > 0 && (
                <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#ff5b70] px-1 text-[9px] font-bold text-white">
                  {unread > 9 ? "9+" : unread}
                </span>
              )}
            </button>
            {notifOpen && (
              <div className="notif-panel">
                <div className="flex items-center justify-between border-b px-3.5 py-2.5" style={{ borderColor: "var(--bp-border)" }}>
                  <span className="text-[12px] font-semibold">Notifications</span>
                  <button onClick={markAllRead} className="flex items-center gap-1 text-[10.5px]" style={{ color: "var(--bp-cyan)" }}>
                    <CheckCheck size={12} /> Mark all read
                  </button>
                </div>
                <div className="max-h-[340px] overflow-y-auto">
                  {notifications.length === 0 && (
                    <p className="px-4 py-8 text-center text-[12px] muted">No notifications yet.</p>
                  )}
                  {notifications.map((n) => (
                    <button
                      key={n.id}
                      onClick={() => {
                        setNotifOpen(false);
                        if (n.link) navigate(n.link.replace("/content/", "/review/"));
                      }}
                      className="notif-item block w-full text-left hover:bg-[var(--bp-hover-notif)]"
                    >
                      <div className="flex items-center gap-2">
                        {!n.is_read && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[#06d6f0]" />}
                        <span className="text-[11.5px] font-semibold" style={{ color: "var(--bp-ink)" }}>{n.title}</span>
                        <span className="ml-auto shrink-0 text-[9.5px] muted">{timeAgo(n.created_at)}</span>
                      </div>
                      <p className="mt-0.5 line-clamp-2 text-[11px] muted">{n.message}</p>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="relative" ref={profileRef}>
            <button
              onClick={() => { setProfileOpen((v) => !v); setNotifOpen(false); }}
              className="flex items-center gap-2 rounded-full border px-1.5 py-1"
              style={{ borderColor: "var(--bp-border)", background: "var(--bp-card)" }}
              aria-label="Account menu"
            >
              <Avatar name={user?.full_name || "User"} color={user?.avatar_color} size={26} />
              <span className="hide-mobile pr-1 text-left">
                <span className="block text-[11.5px] font-semibold leading-tight">{user?.full_name}</span>
                <span className="block text-[9.5px] leading-tight muted">{roleLabel}</span>
              </span>
            </button>
            {profileOpen && (
              <div className="notif-panel p-1.5">
                <div className="px-3 py-2">
                  <p className="text-[12px] font-semibold">{user?.full_name}</p>
                  <p className="truncate text-[10.5px] muted">{user?.email}</p>
                </div>
                <div className="divider my-1" />
                <button className="nav-link" onClick={() => { setProfileOpen(false); signOut(); }}>
                  <LogOut size={14} /> Sign out
                </button>
                {isAdmin && (
                  <button className="nav-link" onClick={() => { setProfileOpen(false); navigate("/knowledge?tab=profile"); }}>
                    <Database size={14} /> Company profile
                  </button>
                )}
                {isAdmin && org?.is_demo && (
                  <button className="nav-link" onClick={() => { setProfileOpen(false); setResetOpen(true); }}>
                    <RefreshCw size={14} /> Reset demo workspace
                  </button>
                )}
              </div>
            )}
          </div>
        </header>

        <main className="content">{children}</main>
      </div>

      <SearchPalette open={searchOpen} onClose={() => setSearchOpen(false)} />

      <Confirm
        open={resetOpen}
        onClose={() => setResetOpen(false)}
        onConfirm={resetDemo}
        title="Reset demonstration workspace"
        body="This removes the seeded NovaTech demonstration records and rebuilds them from the original seed. Real workspaces are untouched. Your current session will reload."
        confirmLabel={resetting ? "Resetting…" : "Reset demo data"}
        danger
      />
    </div>
  );
}
