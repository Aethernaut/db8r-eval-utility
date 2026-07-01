# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**db8r-eval-utility** is an offline gold-dataset evaluation harness for the DB8R evidence pipeline. It measures how well ClaimCheck **retrieves** germane source material and **extracts** evidence from it. The tool is a ClaimCheck *client* — it never touches production databases.

**Canonical design:** `docs/gold-eval-design.md` is the authority on schema/metrics/decisions.

## Commands

```bash
# Install dependencies
poetry install

# Run tests
poetry run pytest

# Run a single test
poetry run pytest tests/test_scorer.py::test_char_range_iou_exact_match

# Lint
poetry run ruff check eval_utility/ tests/

# Format
poetry run ruff format eval_utility/ tests/

# Run the annotation server (when implemented)
poetry run uvicorn eval_utility.server:app --reload
```

## Architecture

### Four Components
```
ClaimCheck (dev instance :8001)
  │  capture (Mode A/B/C)
  ▼
[capture client] ──► fixtures/<hash>.json   (immutable, content-addressed)
  │
  ▼
[annotation UI] ──► gold/ (SQLite)          (gold spans/judgments reference fixture by hash)
  │
  ▼
[scorer] ──► metrics report (HTML/JSON)     (joins gold ↔ fixture, offline)
```

### Three Capture Modes
| Mode | Endpoint | Purpose |
|------|----------|---------|
| **A** | `POST /api/v1/search` | Retrieval metrics (unilateral search) |
| **B** | `POST /api/v1/extract` | Extraction scored independent of retrieval |
| **C** | Load existing response | Distribution realism; bridge to v2 stance |

### Two-Layer Judgment Framework
- **Span-intrinsic** (`gold_span.is_claim_bearing`): claim-independent, reusable — "is this a well-formed statement?"
- **Claim-conditioned** (`claim_span_label.relevant_to_claim`, stance, strength): per `(claim, span)` pair

### Foraging vs. Retrieval
db8r-mcts turns one **claim** into a **foraging strategy** (portfolio of queries). Two stages, two owners:
- **Foraging** (claim → queries, db8r-mcts) → foraging recall (RL reward), tagged by `generator_version`
- **Retrieval** (query → docs, ClaimCheck) → ClaimCheck retrieval recall

Foraging capture uses MC-5 `POST /api/v1/foraging-strategy` (port 8000).

## Hard Rules (Do Not Violate)

1. **Touch neither production database.** Consume ClaimCheck API responses only; write to own store.
2. **Fixtures are immutable and content-addressed.** Never mutate; use `source_text_hash` (SHA-256).
3. **Annotate against `source_text`, not rendered layout.** Gold offsets live in flat text space (same as pipeline's `statement_offset`/`statement_length`).
4. **Gold labels key to durable referents only:** `claim`, `document` (content-addressed), `span`. Never to queries or `generator_version`.

## Key Modules

- `eval_utility/config.py` — Settings (ClaimCheck URL, τ=0.5, DATABASE_URL, auth). Env prefix `EVAL_`.
- `eval_utility/capture.py` — Mode A/B/C capture + foraging via MC-5 (EU-2 ✓)
- `eval_utility/fixtures.py` — Fixture loading with hash/verbatim verification (EU-3 ✓)
- `eval_utility/store.py` — SQLAlchemy 2.0 gold store (EU-3, EU-7 ✓)
- `eval_utility/models.py` — ORM models for all tables including auth (EU-7 ✓)
- `eval_utility/database.py` — Engine factory, session management, SQLite/Postgres support (EU-7 ✓)
- `eval_utility/scorer.py` — v1 metrics computation (EU-5 ✓): retrieval/extraction/fidelity/coverage metrics + JSON/HTML reports
- `eval_utility/server.py` — FastAPI annotation API (EU-4 ✓): REST endpoints for fixtures, claims, spans, labels, judgments
- `eval_utility/api/` — API routers and schemas (EU-4 ✓)
- `eval_utility/api/auth.py` — Password hashing (argon2), session management, CSRF (EU-8 ✓)
- `eval_utility/api/auth_routes.py` — Login/logout/me endpoints, invite acceptance (EU-8 ✓)
- `eval_utility/api/users.py` — Admin-only user management, invite creation (EU-8 ✓)
- `eval_utility/corpus.py` — 72-claim pre-RL stress corpus (EU-6 ✓): seed claims with family balance and split assignment

## External Service Contracts

**ClaimCheck** (`:8001`):
- `POST /api/v1/search` — returns `SearchJobResponse` with `claims[]` (has offsets) and `unified_results[]` (no offsets)
- `POST /api/v1/extract` — synchronous, same response shape
- **Read offsets from `claims[]` array, not projections**
- **Mode A requires** ClaimCheck started with `FULL_DOCUMENT_EXTRACTION_ENABLED=true` to capture `source_text` for span annotation. The capture client sends `include_evidence_documents=true` in the request to opt in.

**db8r-mcts** (`:8000`):
- `POST /api/v1/foraging-strategy` — MC-5 endpoint, `mode="pregame"` only (501 otherwise)
- `perspective` is required: `supports_claim` | `contradicts_claim` (one call per polarity)

## Scorer Details

### v1 Metrics (docs/gold-eval-design.md §5)

**Retrieval:**
- `recall@k`, `precision@k` per query/claim
- `claim_coverage` — % claims with ≥1 germane doc
- `primary_source_coverage` — % claims with high-reliability doc in top-k

**Extraction:**
- `well_formedness_precision` — extracted matching `is_claim_bearing` gold span / total extracted
- `targeting_precision` — extracted matching `relevant_to_claim` gold span / total extracted (per claim)
- `germane_recall` — matched (`is_claim_bearing` ∧ `relevant_to_claim`) / all such gold spans
- `well_formed_recall` — matched `is_claim_bearing` / all `is_claim_bearing` gold spans
- `f1_germane` — F1 on germane set
- Breakouts by content_type, document length bucket, capture_mode

**Fidelity:**
- `match_method_distribution` — exact/normalized/fuzzy proportions
- `mean_extraction_fidelity`
- `verbatim_locatability_rate` — % spans found verbatim in source_text

**Coverage:**
- `lost_evidence_rate` — % docs with `lost_evidence_flag=true`

### Key Rules
- **Span matching:** `char_range_iou(a_offset, a_len, b_offset, b_len)` — match iff IoU ≥ τ (default 0.5)
- **Partial extraction:** Fixtures with `extraction_status.partial_extraction=true` excluded from extraction-recall denominators
- **Blind annotation subset:** Small subset without pre-fill to calibrate anchoring bias

### Usage
```python
from eval_utility.scorer import Scorer
scorer = Scorer()
report = scorer.score_all()
scorer.export_json(report, Path("report.json"))
scorer.export_html(report, Path("report.html"))
```

## Implementation Status

| Milestone | Status |
|-----------|--------|
| EU-1: Scaffold | ✓ Done |
| EU-2: Capture client (Mode A/B/C + foraging) | ✓ Done |
| EU-3: SQLite store + fixture loader | ✓ Done |
| EU-4: Annotation API | ✓ Done |
| EU-5: Scorer (v1 metrics) | ✓ Done |
| EU-6: Seed 72-claim corpus | ✓ Done |
| EU-7: SQLAlchemy 2.0 + multi-annotator re-keying | ✓ Done |
| EU-8: Cookie-session auth + invite-only accounts | ✓ Done |
