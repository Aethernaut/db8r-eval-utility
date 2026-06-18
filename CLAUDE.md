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

- `eval_utility/config.py` — Settings (ClaimCheck URL, τ=0.5, paths). Env prefix `EVAL_`.
- `eval_utility/capture.py` — Mode A/B/C capture + foraging via MC-5 (EU-2 ✓)
- `eval_utility/fixtures.py` — Fixture loading with hash/verbatim verification (EU-3 ✓)
- `eval_utility/store.py` — SQLite gold store with 9 record types (EU-3 ✓)
- `eval_utility/scorer.py` — v1 metrics computation; `char_range_iou` implemented (TODO: EU-5)
- `eval_utility/server.py` — FastAPI annotation UI (TODO: EU-4)

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

- **Span matching:** `char_range_iou(a_offset, a_len, b_offset, b_len)` — match iff IoU ≥ τ (default 0.5)
- **Partial extraction:** Fixtures with `extraction_status.partial_extraction=true` excluded from extraction-recall denominators
- **Blind annotation subset:** Small subset without pre-fill to calibrate anchoring bias

## Implementation Status

| Milestone | Status |
|-----------|--------|
| EU-1: Scaffold | ✓ Done |
| EU-2: Capture client (Mode A/B/C + foraging) | ✓ Done |
| EU-3: SQLite store + fixture loader | ✓ Done |
| EU-4: Annotation UI | TODO |
| EU-5: Scorer (v1 metrics) | TODO (IoU done) |
| EU-6: Seed 72-claim corpus | TODO |
