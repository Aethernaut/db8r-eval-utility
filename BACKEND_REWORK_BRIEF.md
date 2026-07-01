# db8r-eval-utility — Backend Rework Brief (multi-user + Postgres)

**Audience:** the coding agent working on `db8r-eval-utility`.
**Why now:** this is the critical-path prerequisite for both the **frontend SPA** (it must target the authed/Postgres API — see `FRONTEND_BRIEF.md`) and the **DigitalOcean deployment** (multi-user). The backend (EU-1…EU-6, 189 tests) is single-user/SQLite/no-auth; recruiting annotators requires Postgres, auth/roles, and a multi-annotator gold model.
**Authorities:** schema/metrics → `docs/gold-eval-design.md`; auth + gold-model design → `../db8r-deploy/docs/EVAL_DEPLOY_REPURPOSING_PLAN.md` §6.1.
**Prime directive:** keep the suite green (adapt tests where keys/store change; add tests for new behavior). Gate nothing behind prod-affecting defaults that aren't intended. Don't gratuitously churn the API shape — the SPA will be built against it.

> **Key enabling decision — use SQLAlchemy 2.0 for the store.** The same models then run on **SQLite (tests/local)** and **Postgres (deploy)**, so the migration doesn't force a Postgres dependency into the test suite. This makes EU-7 a model/keys change, not a rewrite, and keeps the 189 tests runnable on SQLite.

These tickets are **coupled** — EU-7/8/9 reshape the same keys and the scorer. Do them together, in order, before the SPA.

---

## EU-7 — Store → Postgres + per-annotator re-keying
- **Scope:** port `store.py` (`GoldStore`) to **SQLAlchemy 2.0** models; `DATABASE_URL` in `config.py` replaces `gold_db_path` (SQLite for tests, Postgres in deploy). **Re-key the annotation tables so multiple annotators coexist:**
  - `retrieval_judgment` PK `(claim_id, document_id, annotator_id)`
  - `claim_span_label` PK `(claim_id, span_id, annotator_id)`
  - `gold_span` stays per-author (own `span_id` + `annotator_id`) — already multi-annotator.
  Update the API routes that key on a unit (`judgments` PUT `/{claim_id}/{document_id}`, `labels` PUT `/{claim_id}/{span_id}`) to be annotator-scoped (annotator comes from the session — EU-8).
- **Schema management:** Alembic baseline (consistent with claimcheck), or `create_all` on startup if you defer Alembic — but a baseline migration is preferred for the deploy.
- **Acceptance:** store runs on Postgres in deploy and SQLite in tests via the same models; two annotators' judgments/labels for the *same* unit coexist (no overwrite); existing tests adapted and green.

## EU-8 — Auth, sessions, accounts, roles
- **Transport:** **httpOnly + Secure + SameSite=Strict session cookie** backed by a `sessions` table (revocable). CSRF check on state-changing routes.
- **Tables:** `users` (id, email, `role ∈ {admin, annotator}`, password hash via argon2/bcrypt, `disabled`, timestamps); `sessions` (token, user_id, expires).
- **Accounts — invite-only:** admin creates a user → expiring invite token → invitee sets password. Bootstrap the first admin from `EVAL_ADMIN_EMAIL` / `EVAL_ADMIN_INITIAL_PASSWORD` (env). No open signup.
- **Endpoints:** `POST /auth/login`, `POST /auth/logout`, `GET /me`; admin user-management routes.
- **Authorization:** a `current_user` dependency resolves the session; **`require_admin`** gates the capture (EU-10) + all management routes; annotator write routes require auth. **`annotator_id` is stamped from the session — never accepted from the client.**
- **CORS:** restrict to `EVAL_CORS_ORIGIN` (drop the `*`).
- **Acceptance:** invite-only login issues a revocable cookie; `GET /me` returns user+role; an annotator is server-side-blocked from capture/management; `annotator_id` on new judgments/spans/labels matches the session user.

## EU-9 — Authoritative-gold model + scorer selection + assignment/leasing
- **Assignment + leasing:** a unit can be **assigned** to an annotator (admin) and/or **leased** on open (soft-lock, TTL) to prevent accidental collision; self-serve queue otherwise.
- **Authoritative gold (default = assignment-based single annotation):** each unit's authoritative annotation is its assignee's. Most units are annotated once → that's the gold.
- **Double-annotation (admin-assigned subset):** store all annotators' records; compute an **agreement report** (Cohen's κ) on the double-annotated units (judgment relevance, label relevance/stance); an **admin adjudication** endpoint marks the authoritative record (default: primary assignee).
- **Scorer change:** `scorer.py` must select **exactly one authoritative annotation per unit** (default = assignee; adjudicated override) instead of assuming one record per unit.
- **Acceptance:** a double-annotated unit stores both annotators' records; κ is reported; admin can adjudicate; the scorer scores one gold per unit and is unaffected by the non-authoritative record.

## EU-10 — Admin capture endpoint
- **Scope:** API endpoints (admin-only) wrapping `capture.search` / `capture.extract` / `capture.capture_foraging`. Capture is slow (external APIs) → run as a **job** with status polling; the capture client writes fixtures to the fixtures volume. Powers the T1 "add germane doc by URL" and Task-0 capture.
- **Acceptance:** an admin can trigger search/extract/foraging via the API and a fixture is produced; an annotator is blocked (403).

## EU-11 — `retrieval_complete` per-claim flag
- **Scope:** a per-claim completeness marker (on the claim or a per-claim annotation-state record) — the T1 "done" signal that makes the **foraging-recall denominator** well-defined (mirrors `exhaustively_annotated` for T2). Expose get/set; the dashboard + scorer consume it.
- **Acceptance:** a claim can be marked `retrieval_complete`; foraging-recall is computed only over complete claims; the dashboard reflects it.

---

## Sequencing
1. **EU-7 ∥ EU-8** — largely independent (store/Postgres/re-key vs. auth); build in parallel. Join point: EU-7's re-keyed routes populate `annotator_id` from EU-8's session (stub a fixed annotator until EU-8 lands).
2. **EU-9** (gold model + scorer) — depends on both.
3. **EU-10** (capture endpoint) + **EU-11** (`retrieval_complete`) — smaller, follow.
4. Then the **SPA** (`FRONTEND_BRIEF.md`) against this authed/Postgres API, then image-build CI, then the deploy-time wiring (deploy plan §3).

## Definition of done
- Store on Postgres (deploy) / SQLite (tests) via SQLAlchemy; annotation tables re-keyed per-annotator; suite green.
- Cookie-session auth; invite-only accounts; `admin`/`annotator` enforced server-side; `annotator_id` from session; CORS restricted.
- Double-annotation stored + κ report + admin adjudication; scorer selects one authoritative gold per unit.
- Admin capture endpoint (job-based); `retrieval_complete` flag.
- No client-supplied `annotator_id`; no open signup; capture/management admin-only.

---

## Addenda — eval-agent review incorporated (2026-06-18)

Accepted nearly all of the review. Deltas by ticket:

**EU-7**
- **No legacy annotation data to migrate** — annotation hasn't started (no UI yet); the store is greenfield. Only the seeded *corpus* (claims, no annotator dimension) carries over. If any dev/test rows exist, stamp a `system` annotator. **Do not build a migration path.**
- **`gold_span` is per-annotator by authorship:** two annotators marking the same range create **separate** `gold_span`s (distinct `span_id`, each `annotator_id`); never shared/merged. Span-level agreement is by **span-set comparison** (IoU between annotators' sets), not a shared row.
- **Batch routes too:** `POST /judgments/batch` and `POST /labels/batch` are annotator-scoped from the session, same as the single-record routes.

**EU-8**
- **CSRF:** SameSite=Strict + same-origin is the baseline; add a **synchronizer token** issued at login (returned by `/me`, required as a header on state-changing requests).
- **Session cleanup:** expire-on-access + a periodic sweep of the `sessions` table.
- **Login hardening:** min password length + **rate-limit login attempts** per account/IP.
- **`GET /me` unauthenticated → 401** (the SPA uses this to detect auth state).
- **Invite-token storage:** a dedicated **`auth_tokens` table** (`token`, `email`, `role`, `purpose ∈ {invite, password_reset}`, `expires_at`, `used_at`) — *not* reused `sessions`. Serves invites now and password reset later.

**EU-9**
- **Adjudication is per-unit** (one `(claim,document)` judgment / one `(claim,span)` label), not per-claim.
- **Agreement scope (MVP vs. defer) — re: the "span-set IoU is non-trivial" concern:** it's cheaper than it looks because **`scorer.py` already has the IoU matcher (`find_span_matches`)** — reuse it annotator-A-spans vs annotator-B-spans. Note: only the **retrieval judgment** is matching-free (both annotators judge the *same* document); everything span-conditioned needs the match step first because spans are per-annotator.
  - **MVP:** **Cohen's κ on retrieval judgments** (claim×document) + **span agreement via `find_span_matches`** (Jaccard/F1 of the two span sets, and **`is_claim_bearing` / `relevant_to_claim` agreement on matched pairs**).
  - **Defer:** **stance** agreement (T3/v2) and fancier set-agreement statistics.
- **Authoritative precedence:** `adjudicated_override > assignee > earliest by created_at`. **Unassigned + multiple annotators → flag for admin** (don't silently pick).
- **`assignment_lease` table (new):** `(unit_type, unit_key, annotator_id, status, leased_at, expires_at)` — holds assignment + soft-lock TTL. (Name standardized as `assignment_lease` everywhere.)

**EU-10**
- **Job storage = `capture_jobs` table** (Postgres) — not in-memory (lost on restart), not Redis (no new dependency).
- **Capture wiring:** a completed capture **registers its fixture(s)** so the API/SPA see them; **claim-targeted** captures (T1 "add germane doc", foraging) **auto-link** documents to the claim (`claim_document_link`, `origin=manual|search`). `document_annotation` rows created **lazily** on first T2 open.
- **Concurrency cap** on in-flight capture jobs (bounds cost/load on ClaimCheck/mcts).

**EU-11**
- **New `claim_annotation_state` table** (`claim_id`, `retrieval_complete`, `by`, `at`) — keeps the `claim` record unchanged; allows per-annotator completion later.
- **Who marks complete:** the **assigned annotator** marks their own T1 complete; **admin** can override/unset.

**Cross-cutting (accepted)**
- **`/health` reports DB connectivity** (deploy readiness probe).
- **`audit_log` table** for admin/security actions (user create/disable, adjudication, capture trigger). Columns: `(id, timestamp, user_id, action, target_type, target_id, details_json)`.
- **Test auth:** a pytest fixture creating a test user + session (or FastAPI `dependency_overrides` for `current_user`) so authed endpoints are testable.

**Rejected — API versioning:** no `/api/v2`. There is **no external consumer**; the only client is the not-yet-built SPA. Evolve `/api/v1` in place — a parallel v2 is maintenance overhead with no client to protect.

**New tables introduced:** `users`, `sessions`, `auth_tokens`, `capture_jobs`, `assignment_lease`, `claim_annotation_state`, `audit_log` (+ re-keyed `retrieval_judgment` / `claim_span_label`).
