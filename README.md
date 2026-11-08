# BrandProof — An Adaptive Brand Intelligence Platform

**Tagline: "One Identity. Every Platform. Every Time."**

BrandProof is an AI-powered brand governance platform that helps organisations protect their identity, verify marketing claims against approved evidence, keep humans in control of approvals, and turn reviewer feedback into clearer guidelines.

The journey: **Approved brand knowledge → Content submission → Analysis → Evidence verification (Proof Passport) → Correction → Human approval → Feedback learning → Guideline improvement → Change impact analysis.**

---

## 1. Quick start (local)

### Backend (FastAPI + PostgreSQL/SQLite fallback)

```bash
cd backend
python -m pip install -r requirements.txt
cp .env.example .env        # adjust secrets; defaults work for local dev
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- API docs (Swagger/OpenAPI): http://localhost:8000/docs
- Health: http://localhost:8000/api/health
- On first start the demo workspace **NovaTech** is seeded automatically (`SEED_DEMO_DATA=true`).

### Frontend (React + Vite + TypeScript)

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173  (proxies /api to the backend)
```

Visit **http://localhost:5173** and sign in (see Demo accounts below).

### Docker (optional)

```bash
docker compose up --build
# Frontend: http://localhost:4173  ·  Backend: http://localhost:8000
```

---

## 2. Demo accounts (NovaTech workspace)

Password for all demo accounts: **`BrandProof123!`**

| Role | Email | Use it to test |
|---|---|---|
| Administrator | `admin@novatech.demo` | Add facts/guidelines, invite team, approve knowledge |
| Content Creator | `creator@novatech.demo` | Submit content, apply corrections, resubmit |
| Reviewer | `reviewer@novatech.demo` | Accept/reject/modify suggestions, add comments |
| Approver | `approver@novatech.demo` | Final content approval, guideline proposal decisions |

A second isolated workspace (Helios Foods, `admin@helios.demo`) demonstrates organisation-level data isolation.

**Try the four Proof Passport cases** (Content Reviewer → "+ Submit content", or paste in the form):

| Case | Paste | Expected verdict |
|---|---|---|
| 1 — Correct spec | `The NovaTech X1 features a 5000 mAh battery. Battery life varies with usage.` | **SUPPORTED** |
| 2 — Wrong spec | `NovaTech offers a 7000 mAh battery. Battery life varies with usage.` | **CONTRADICTED** |
| 3 — Unsupported superlative | `NovaTech X1 is India's fastest smartphone. Battery life varies with usage.` | **UNSUPPORTED / NEEDS REVIEW** |
| 4 — Stale evidence | `NovaTech X1 supports 45W fast charging. Battery life varies with usage.` | **INCONCLUSIVE** (source past review date) |

- **Case 5 (Guideline Intelligence):** open *Guideline Intelligence* — 10 drafts with exaggerated wording are grouped as "Unclear guideline" with a pending clarification proposal (approve/reject/edit as Approver/Admin).
- **Case 6 (Change Impact):** in *Knowledge Vault → Approved facts*, edit `NovaTech X1 battery capacity` from `5000 mAh` to `5500 mAh` → existing registered content is flagged in *Change Impact Simulator*. (Use the simulator's own form to undo afterwards, or restore the value to `5000 mAh`.)

---

## 3. Architecture

```
frontend/  React 18 + Vite + TypeScript + Tailwind CSS v4 + Recharts + Lucide
backend/   Python + FastAPI + Pydantic + SQLAlchemy 2.0 + Alembic
           SQLite locally, PostgreSQL in production (same models/migrations)
```

- **Backend is the source of truth.** Deterministic rules (exact terms, dates, values, restricted phrases, required statements, terminology, colour/alt-text checks) + local evidence index (embeddings + cosine retrieval over *approved* records only, every chunk carrying its real database ID) always run. When an OpenAI-compatible provider is configured (`AI_PROVIDER`, `AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL`), it only assists claim extraction; statuses are always computed against the database and demo/AI results are explicitly labelled (`analysis_mode: demo | ai`).
- **Proof Passport:** each claim gets one of **Supported / Contradicted / Unsupported-Needs review / Inconclusive** with the verbatim source passage, document name and locator. Missing evidence is never reported as false; no fake pages or quotations are generated.
- **Guideline Intelligence:** reviewer decisions are stored structurally and grouped by category/title similarity; root causes are transparent rule-based hypotheses (**not** model retraining). Guidelines change only through human-approved proposals.
- **Security:** pbkdf2 password hashing, JWT sessions, role-based access (admin / content_creator / reviewer / approver), org isolation on every query, upload validation (type, size, sanitised storage), full audit trail, secrets via environment variables.

### Key API areas (`/api`)

`auth` (signup/login/me/profile/passwords/demo-accounts) · `knowledge` (documents/upload, facts, claims, guidelines+versions, assets, search, overview) · `content` (submissions, upload, analyze, corrections, status/decisions, comments) · `review` (queue, findings, decisions, feedback) · `intelligence` (groups, proposals, what-if) · `impact` · `analytics/dashboard` (drift radar, expiry radar, gap detector, heatmap, activity, trend) · `analytics/health` (transparent brand-health categories) · `analytics/network` (Brand Knowledge Network) · `admin` (members, roles, organisation, audit) · `notifications` · `health` · `meta/options`.

### Risk-based approval policy

Every analysis computes a **rule-based risk level** (never an AI score):
- **HIGH** — any contradicted claim or high/critical severity finding → escalated to an authorised human.
- **MEDIUM** — high-risk unsupported claims or inconclusive evidence → human review / request more evidence.
- **LOW** — all claims supported, no severe findings → status becomes `cleared_by_policy`, retained in the audit trail, **never auto-published**.

### Brand Health (transparent, measurable)

`GET /analytics/health` computes five categories over the last 90 days with published formulas: claim accuracy (supported/all claims), guideline compliance (resolved/all findings), recurring-issue frequency (1 − groups/10), outdated information (1 − overdue facts/all facts), review resolution. Overall = mean of available categories. No AI-generated score.

### Spatial workspace UI

- **Floating navigation dock** (desktop) + **bottom navigation** (mobile) replace the permanent sidebar; "More" holds secondary modules. Labels appear on hover/expand.
- **Command palette (Ctrl+K):** search modules, records and actions with keyboard navigation.
- **Evidence Trace:** animated SVG connection from a selected claim to its approved source with a highlighted excerpt; unsupported claims explicitly show "no approved evidence found".
- **Before/After:** original vs suggested correction side-by-side; originals update only after acceptance.
- **Brand Knowledge Network** (Knowledge Vault tab): SVG graph of real relationships (fact→source, finding→guideline, claim→evidence, group→content).
- Reduced-motion preferences are respected; light/dark themes are fully implemented.

---

## 4. Deployment

### Backend (e.g. Render, Railway, fly.io, any Docker host)

1. Set `ENV=production`, a strong `JWT_SECRET`, `CORS_ORIGINS` with your frontend domain, and `DATABASE_URL` pointing at managed PostgreSQL (`postgresql+psycopg://…`). The Docker image runs migrations on the SQLite/Postgres schema created by SQLAlchemy `create_all` on startup; use `alembic upgrade head` for managed migrations.
2. Deploy `backend/Dockerfile`. Postgres data persists via the managed DB; uploads via a volume (`UPLOAD_DIR`).

### Frontend (e.g. Vercel, Netlify, Cloudflare Pages, nginx image)

- Build command: `npm run build`, output: `dist`. The repo inlines `VITE_API_URL` at build time — set it to the public backend `/api` URL (the Vite dev proxy only applies locally).
- Or run `frontend/Dockerfile` (nginx serves the SPA and reverse-proxies `/api`).

### URLs after deployment

- Frontend URL: `<your-frontend-domain>`
- Backend API URL: `<your-backend-domain>/api` · docs at `<your-backend-domain>/docs`

---

## 5. Supported formats & known limitations

- **Supported:** plain text, PDF (embedded text layer), TXT/MD. Original of every upload is preserved.
- **Not supported in this deployment:** OCR for scanned PDFs (explained clearly in the UI instead of fabricating results), video/image full compliance (only measurable checks: off-palette hex colours, missing alt text, capitalised blocks), speaker templates. PDF uploads that are password-protected or scanned fail with a clear error and no partial results.
- The platform never claims to find content that was never uploaded; Change Impact only searches registered content.
- Proof scores are an **internal review summary, not a certified compliance score**.

---

## 6. Acceptance-tested flows

Sign-in & workspace isolation · admin adds approved facts/guidelines · PDF/text upload + claim extraction + all four Proof Passport statuses · source inspection per finding · correction suggestions · reviewer accept/reject/modify with stored feedback · recurring group + proposal approval applying a new guideline version · fact change triggering impact across saved content · audit trail for sensitive actions · role blocks on approvals · light/dark themes · responsive layout · full-stack running locally (and containerised).

```
BRANDPROOF/
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI app, lifespan, health, meta/options
│   │   ├── models.py          20+ tables: users, orgs, memberships, guidelines,
│   │   │                      documents, facts, claims, assets, submissions,
│   │   │                      claims, findings, feedback, groups, proposals,
│   │   │                      approvals, impacts, audit, notifications
│   │   ├── core/              config, security (JWT + hashing), deps (RBAC)
│   │   ├── db/                SQLAlchemy session
│   │   ├── routers/           auth, knowledge, content, review,
│   │   │                      intelligence, impact, analytics, admin, notifications
│   │   └── services/          analysis (rules+verification), knowledge_index
│   │                          (approved-only evidence), intelligence,
│   │                          impact, ai (provider-agnostic), pdf, audit
│   ├── alembic/               migrations
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.tsx            shell, router, auth/theme context
│   │   ├── lib/api.ts         typed API client, session handling
│   │   ├── components/ui.tsx  badges, modals, cards, avatars
│   │   └── pages/             Auth, Overview, Knowledge, Content (Reviewer +
│   │                          Proof Passport detail), Passport, Intelligence,
│   │                          Impact, Consistency, Approval, Analytics,
│   │                          Audit, Team, Settings
│   └── package.json / Dockerfile / nginx.conf
├── docker-compose.yml
└── README.md
```
