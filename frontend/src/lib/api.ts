const BASE = import.meta.env.VITE_API_URL || "/api";
export const API_ORIGIN = BASE.replace(/\/api\/?$/, "");

let token: string | null = localStorage.getItem("bp_token");
let orgId: string | null = localStorage.getItem("bp_org");

export function setToken(t: string | null) {
  token = t;
  if (t) localStorage.setItem("bp_token", t);
  else localStorage.removeItem("bp_token");
}
export function getToken() {
  return token;
}
export function setOrg(id: string | null) {
  orgId = id;
  if (id) localStorage.setItem("bp_org", id);
  else localStorage.removeItem("bp_org");
}
export function getOrg() {
  return orgId;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function parse(data: string): unknown {
  try {
    return data ? JSON.parse(data) : null;
  } catch {
    return data;
  }
}

function messageFrom(data: unknown, fallback: string): string {
  if (typeof data === "object" && data !== null && "detail" in data) {
    const detail = (data as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0] && typeof detail[0] === "object" && "msg" in detail[0]) {
      return String((detail[0] as { msg: unknown }).msg);
    }
  }
  return fallback;
}

export async function api<T>(
  path: string,
  options: { method?: string; body?: unknown; headers?: Record<string, string> } = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (orgId) headers["X-Organisation-Id"] = orgId;
  if (options.headers) Object.assign(headers, options.headers);
  const body = options.body;
  if (body && typeof body === "object" && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      method: options.method || (body ? "POST" : "GET"),
      headers,
      body:
        body && typeof body === "object" && !(body instanceof FormData)
          ? JSON.stringify(body)
          : (body as BodyInit | null | undefined),
    });
  } catch {
    throw new ApiError("Unable to reach the BrandProof API. Check that the backend is running.", 0);
  }
  const text = await res.text();
  const data = parse(text);
  if (!res.ok) {
    throw new ApiError(messageFrom(data, res.statusText || `Request failed (${res.status})`), res.status);
  }
  return data as T;
}

export function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}
