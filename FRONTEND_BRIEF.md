# db8r-eval-utility — Frontend SPA Brief

**Audience:** the agent building the annotation frontend. Lives in `db8r-eval-utility/frontend/`.
**Reads:** [`README.md`](README.md), [`docs/gold-eval-design.md`](docs/gold-eval-design.md) (tasks/schema/metrics), and the deploy/auth model in `../db8r-deploy/docs/EVAL_DEPLOY_REPURPOSING_PLAN.md` (§6.1).

**Prerequisite (do not start against the current API):** the SPA targets the **authed, Postgres-backed** `eval-api` — i.e. after the store→Postgres migration, per-annotator re-keying, and cookie-session auth land (deploy plan §6/§6.1). Build against that API + its OpenAPI schema, not the current single-user SQLite one.

---

## 1. What this is

A multi-user annotation UI for the gold-eval set: three tasks over one shared dataset, plus a dashboard, scorer report, and admin tools. It is a **pure client** of `eval-api` (FastAPI). Auth is a same-origin **httpOnly session cookie**; roles are `admin` | `annotator`.

## 2. Stack (decided)

- **React 19 + Vite + TypeScript** (matches db8r-mcts).
- **TanStack Query (React Query)** for all server state — caching + **mutation→invalidation** (e.g. create span → invalidate that document's spans + the progress rollup). No Redux; ephemeral UI state is local component state / small reducers.
- **Typed API client generated from the eval-api OpenAPI schema** (openapi-typescript or orval), wrapped in React Query hooks. Keeps the ~35 endpoints honest.
- **react-router**. `fetch`/client with `credentials: 'include'`; a 401 interceptor → redirect to `/login`.

## 3. App shell & routes (role-aware)

```
/login                       Login (unauth only)
/                            Dashboard (task queues + corpus status)     [shell]
/queue/t1  /queue/t2         task-batched entry points (serve next unit) — DEFAULT work mode
/claims/:id                  Claim detail (status + drill-in)
/t1/:claimId                 Retrieval Judgment (claim-centric)
/t2/:documentId              Span Annotation (document-centric)
/t3/:claimId                 Stance/strength — route + seam, FEATURE-FLAGGED OFF (v2)
/report                      Scorer report (read-only)
/admin/{users,capture,assignments,adjudication}   admin-only
```
- `AuthProvider` hydrated from `GET /me`; `ProtectedRoute` gates the shell; nav is role-aware.
- **Role-gating in the UI is UX only — the server enforces.** Never send `annotator_id` from the client; the server stamps it from the session.

## 4. Views → API

| View | Reads | Writes |
|---|---|---|
| Dashboard | `progress` rollup, `dataset`, last `report` | — |
| **T1 Retrieval** | claim + candidate docs (fixtures/`retrieval_results`) | `judgments` (+`/batch`), `claim_document_link`, `retrieval_complete` |
| **T2 Span** | `fixtures/{id}/documents/{doc}` (source_text + prefill spans) | `spans` (CRUD + `/prefill`), `documents` (doc-flags) |
| T3 Stance *(deferred)* | claim + relevant spans + context | `labels` (+`/batch`) |
| Report | scorer output | — |
| Admin | users, capture jobs, assignments, double-annotation pairs | capture endpoint (admin), user mgmt, assignment, adjudication |

Default work rhythm is **task-batched** (queues serve the next unit), with claim-by-claim available via claim detail.

## 5. The span editor — build & de-risk this FIRST

Isolate it as a pure, controlled, API-agnostic component:
```
<SpanAnnotator sourceText spans mode onCreate onResize onDelete onToggle />
```
The T2 view wires its callbacks to React Query mutations. Internals (all decided):
- **Render `source_text` as a plain text layer; draw highlights as an absolute overlay computed from `Range.getClientRects()`** — never nested `<span>`s. This is what survives **overlapping** spans (translucent stacked boxes + a chip menu to disambiguate clicks on overlaps).
- **Mouse interactions:** click-drag to **create**; **drag-handles** on span edges to **resize**; click → popover to **delete** / toggle `is_claim_bearing`. Prefilled extractor spans render as "unreviewed" (dashed) → accept/adjust/delete.
- **Word-snap by default; Alt-drag for char-precise.** (IoU≥0.5 tolerates minor edges, so word-snap costs nothing on scoring and improves speed + inter-annotator agreement.)
- **Virtualize the overlay** for large docs (we've seen 69k chars): only compute/draw highlight rects for spans in the viewport (+buffer); recompute on scroll/resize.
- Offsets always index into raw `source_text`. `label_source` is set automatically by operation (`human_authored` | `pipeline_prefill_corrected` | `pipeline_prefill`).
- Same component renders **read-only** to show context in T1/T3.

## 6. Cross-cutting (v1 posture: start simple, harden later)

- **Writes: synchronous** in v1 (no optimistic updates, no local buffer). Harden later (optimistic + buffer) as an as-built iteration. **One early guard worth keeping:** warn before navigating away from a document with unsaved edits, so a session never silently loses a doc's worth of spans.
- **Leasing/soft-lock:** v1 minimal — acquire a lease on opening a unit, release on unmount, show "locked by X" if taken. Heartbeat-renew can come with the hardening pass.
- **Keyboard accelerators** complement the mouse: next-unit, complete/flag, claim-bearing toggle.
- Standard loading/empty/error states; capture jobs (admin) are async → poll/progress.

## 7. Build & deploy

- Vite build → `dist/` → served by nginx with SPA fallback (`frontend/Dockerfile` + `frontend/nginx.conf`, already written).
- **Same-origin in prod:** API at `/api/` (relative paths — no base URL needed). Dev: Vite proxy `/api` → `http://127.0.0.1:8000`.
- The edge nginx (db8r-deploy) routes `/` → this container, `/api/` → eval-api.

## 8. v1 scope vs deferred

- **v1:** Login, Dashboard, **T1**, **T2** (+ span editor), Report, and the admin **capture** + **users** views; task-batched queues; minimal leasing; synchronous writes.
- **Deferred:** **T3 stance UI** (route/seam only, flag off — unblocks when v2 stance scoring / MC-2 `evidential_relation` lands); admin **adjudication** view can be minimal first; write-hardening (optimistic/buffer/heartbeat).

## 9. Definition of done (v1)
- Auth (login/logout, role-aware nav) against cookie sessions; 401 → login.
- A claim can be taken through **T1 → T2** end-to-end; gold persists; `retrieval_complete` / `exhaustively_annotated` flags set.
- Span editor supports create / resize (drag-handles) / delete / accept-prefill, word-snap default, on a 50k+ char doc without lag.
- Dashboard shows per-claim/task progress + calibration subsets; Report renders scorer metrics.
- Admin can capture (search/extract/foraging) and manage users; annotators cannot.
- Builds to the frontend image; works same-origin behind the edge nginx.
