# db8r-eval-utility — Evidence Gold-Eval & Annotation Tool

**Audience:** the coding agent building this tool. This is a **new, standalone project** at `~/projects/db8r-system/db8r-eval-utility/`.
**It is not part of any production runtime.** It is an offline harness that measures how well the DB8R evidence pipeline **finds** germane source material and **extracts** evidence from it.

**Canonical design** (read first): `../db8r-mcts/docs/plans/2026-06-16-gold-eval-utility-design.md` — this README is the implementation brief; that note is the authority on schema/metrics/decisions. Related context: `../db8r-claimcheck/EVIDENCE_PIPELINE_REFACTOR_CLAIMCHECK.md` and `../db8r-mcts/docs/plans/2026-06-16-evidence-pipeline-refactor-mcts.md`.

---

## 1. Why this exists

Today there is **no metric for retrieval/extraction accuracy** — only downstream debate outcomes, which confound everything. This tool produces a **gold dataset** and a **scorer** so the team can measure (and then improve) the evidence pipeline, and so the "blocked on gold eval set" work in both pipeline briefs (extraction model choice, threshold tuning, flipping db8r-mcts verification to `delegate`) becomes unblocked.

The system's headline safety metric is **`polarity_error_rate`** — the fraction of admitted evidence assigned to the wrong side (a wrong polarity corrupts the debate graph; a miss only lowers recall). That metric is **v2** (needs db8r-mcts stance output); **v1 measures the ClaimCheck half**: retrieval + extraction + fidelity.

## 2. Hard architectural rules (do not violate)

1. **Touch neither production database.** The tool consumes ClaimCheck **API responses** and writes to its **own** store. No connection to the ClaimCheck or db8r-mcts Postgres.
2. **The tool is a ClaimCheck *client*.** It calls ClaimCheck's HTTP API to *capture*; annotation and scoring then run **fully offline** against captured fixtures.
3. **Fixtures are immutable and hashed.** A captured response is frozen with a `source_text_hash`; gold offsets reference that text. A pipeline change produces a *new* fixture, never mutates an old one. This is what makes the gold set a durable asset.
4. **Annotate against `source_text`, not the rendered document.** Gold span offsets must live in the same character space as the pipeline's `statement_offset`/`statement_length`. (Reasoning in §6.)

## 3. Inputs: three capture modes

The tool is **not** reliant on db8r debates. It drives ClaimCheck directly. ClaimCheck base URL is configurable (default `http://127.0.0.1:8001`).

| Mode | ClaimCheck call | Purpose |
|---|---|---|
| **A — unilateral search** | `POST /api/v1/search` `{query, providers?}` | retrieval metrics; deliberately issue CON-framed and `filetype:pdf`/site-filtered queries to over-sample hard cases |
| **B — direct document** | `POST /api/v1/extract` `{url \| raw_text, query?}` | extraction scored **independent of retrieval**; guarantee specific PDFs/long/contradictory docs are in the set |
| **C — debate import** | load a previously captured `/search` response | distribution realism; bridge to v2 stance scoring |

All three return the same `SearchJobResponse` shape, so a captured response from any mode is an interchangeable **fixture**.

### Verified ClaimCheck integration facts (2026-06-16 live build)
- **Read offsets from the `claims[]` array.** In `SearchJobResponse`, `statement_offset`/`statement_length` are populated only on canonical `claims[]`. The `unified_results[]` and `evidence_documents[].extracted_claims[]` projections carry `extraction_fidelity`/`match_method`/`source_assertion_opinion` but return `statement_offset: null`. **Join spans by `claims[]` for offset-based matching.**
- **`/extract` is synchronous-complete** (returns `status:"completed"` with results inline; `providers:["direct"]`, `search_scope:"extract"`, no provider search).
- **Contract fields per claim:** `extraction_fidelity` (float), `match_method` (`exact|normalized|fuzzy`), `source_assertion_opinion` (raw frame, disbelief≈0), emitted alongside legacy `subjective_logic_opinion`, plus `claimset_oriented_subjective_logic_opinion` + orientation meta, `source_reliability`.
- **Partial-extraction status (CC-3a — verified live 2026-06-16).** When `FULL_DOCUMENT_EXTRACTION_ENABLED=true` and a document exceeds the chunk/token budget, ClaimCheck surfaces partial-extraction status in **three places** (confirmed shape):
  - an **`extraction_status`** object at **both job level and per `evidence_documents[]`**: `{partial_extraction: bool, chunks_processed: int, chunks_total: int, tokens_used: int, token_budget: int, warnings: [str]}` (e.g. `warnings: ["max_chunks_exceeded"]`);
  - job-level **`warnings`**: e.g. `["partial_extraction", "partial_extraction_chunk_budget"]`;
  - evidence-document **`validation_warnings`**: includes `partial_extraction` and `partial_extraction_chunk_budget` (token-budget path: `partial_extraction_token_budget`) alongside generic doc-quality warnings.
  **Capture `extraction_status` onto the fixture** and have the scorer exclude `partial_extraction:true` fixtures from extraction-recall denominators (a truncated doc is not a fair recall target).
- **Live model key is configured** (`gpt-4.1-nano`, mock off), so `/extract` exercises the real extractor.

## 4. Components & data flow

```
ClaimCheck (dev instance)
  │  capture (Mode A/B/C)
  ▼
[capture client] ──► fixtures/<hash>.json   (immutable, hashed: system output + source_text)
  │
  ▼
[annotation UI] ──► gold store (SQLite)      (gold spans/judgments reference fixture by hash)
  │   pre-filled from fixture claims[]; human corrects
  ▼
[scorer] ──► metrics report (HTML/JSON)      (joins gold ↔ fixture, offline)
```

Four components: **capture client**, **fixture store**, **annotation UI**, **scorer**.

## 5. Recommended stack & repo layout

Python (matches ClaimCheck/db8r; easy `httpx` calls + metric computation). Minimal custom web UI for precise span selection (Gradio/Streamlit make exact character-offset highlighting awkward — avoid).

```
db8r-eval-utility/
├── README.md                  # this brief
├── pyproject.toml
├── eval_utility/
│   ├── config.py              # CLAIMCHECK_BASE_URL, paths, IoU threshold τ
│   ├── capture.py             # Mode A/B/C → fixture (hash, freeze)
│   ├── fixtures.py            # load/validate fixtures; source_text_hash integrity
│   ├── store.py               # SQLite gold store (schema §4 of design note)
│   ├── scorer.py              # v1 metrics (§5 of design note)
│   ├── server.py              # FastAPI: serves annotation UI + persists gold records
│   └── web/                   # single-page UI: source_text pane + reference pane + JS span selector
├── fixtures/                  # immutable captured responses (gitignored if large; keep a small seed set)
├── gold/                      # SQLite db + exports
└── tests/
```
Store gold records in **SQLite** (queryable); store fixtures as **JSON files** named by hash. Both portable, no server dependency for annotation/scoring.

## 6. Annotation UI spec

- **Primary pane:** render the fixture's `source_text` as a **single text node** (e.g. `<pre>`) so a browser text selection maps directly to raw character offsets (`selectionStart`/`selectionEnd` == `char_offset`/`char_offset+char_length`). Avoid any markup inside that node that would shift offsets.
- **Pre-fill, don't author:** on load, highlight the fixture's `claims[]` spans as candidate gold spans. The human **corrects** — adjust a span, toggle `is_evidence`, add a missed span, delete a bad one. Every correction is both a gold label and a measured error of the current pipeline; record `label_source = pipeline_prefill_corrected | human_authored`.
- **Per-span controls:** `is_evidence` (bool); `stance` (PRO/CON/NEUTRAL) and `strength_ordinal` (none/weak/moderate/strong) are **present but optional/unscored in v1** (v2 fields — collect if cheap, ignore in v1 scoring).
- **Keyboard-driven** for speed (highlight → key for is_evidence, etc.).
- **Read-only reference pane:** render the original document beside the text pane (iframe for the `source_url`; PDF.js for PDFs) so the human sees true layout/tables to judge meaning — **but highlights happen only in the `source_text` pane.** This recovers layout context without incurring layout↔offset mapping.
- **Document-level flags:** `exhaustively_annotated` (bool — required for extraction *recall* to be defined on this doc) and `lost_evidence_flag` (bool + note — material evidence present in the original but absent from `source_text`; no offset). The latter is its own coverage metric (§7).
- **Why `source_text` not layout:** the pipeline's offsets live in flat `source_text`; annotating in the rendered layout would require mapping bounding boxes back to char ranges (lossy). v1 measures the current pipeline, which can only extract from `source_text`; layout-space annotation is deferred to v2.

## 7. Scorer — v1 metrics (compute by joining gold ↔ fixture)

**Stance/strength/`polarity_error_rate` are v2** (need db8r-mcts `evidential_relation`); v1 ignores the stance/strength fields.

- **Retrieval** (needs `retrieval_judgment`): `recall@k`, `precision@k`, `coverage` (% claims with ≥1 relevant doc in top-k), **`primary-source coverage`** (% claims where a high-`source_reliability`/PDF doc appears in top-k — measures provider-expansion + CC-1a payoff). Report recall as *pooled* (relevant set = pooled judged docs).
- **Extraction spans** (needs `gold_span.is_evidence` + offsets; doc must be `exhaustively_annotated` for recall): match a gold span to an extracted span iff same document and **char-range IoU ≥ τ** (default 0.5). `precision` = matched_extracted/total_extracted; `recall` = matched_gold/total_gold; `F1`. **Break out recall by document-length bucket, `content_type` (HTML vs PDF), and capture_mode** — this is the diagnostic that shows whether truncation (CC-3) and PDF ingestion (CC-1a) help.
- **Extraction fidelity** (needs fixture `extraction_fidelity`/`match_method`): match-method distribution; mean fidelity; **verbatim-locatability rate** (% extracted spans whose text is found in `source_text` — should be ≈100%; a drop signals a verbatim-guard regression).
- **Text-extraction coverage** (needs `lost_evidence_flag`): **lost-evidence rate** = % docs where material evidence was absent from `source_text`. Kept **separate** from extractor recall so "extractor missed it" ≠ "text layer dropped it before extraction."
- **Partial-extraction awareness:** if a fixture is flagged partial (CC-3a), the scorer must **exclude it from extraction-recall denominators** (or report separately) — a truncated document is not a fair recall target.

Output: a single metrics report (JSON + human-readable HTML), sliceable by claim family and content_type.

## 8. Claim seeding

Reuse the existing **72-claim pre-RL stress corpus** (`../db8r-mcts/docs/plans/2026-05-20-pre-rl-stress-claim-corpus.md`): 60 primary-family claims (policy/factual/comparative/predictive/causal/existence, incl. polarity-reversed partners) + 12 hybrid. **Claim selection ≠ document selection:** keep claims family-balanced; do hard-case over-sampling at the *document* layer via Mode A (CON-framed, PDF-targeted queries) and Mode B (directly ingest known PDFs/long/contradictory docs). Reserve a frozen `test` split of claims never used for tuning; report headline numbers on it only.

## 9. Milestones

| ID | Deliverable |
|---|---|
| **EU-1** | Scaffold: repo, `pyproject`, `config.py` (ClaimCheck base URL, τ, paths), CI (ruff + pytest). |
| **EU-2** | Capture client: Modes A/B/C → frozen hashed fixtures; record partial-extraction status + source provenance. |
| **EU-3** | Gold store (SQLite) implementing the design-note §4 schema; fixture loader with `source_text_hash` integrity check. |
| **EU-4** | Annotation UI (§6): `source_text` pane + reference pane + JS span selector + pre-fill + keyboard + doc-level flags. |
| **EU-5** | Scorer (§7 v1 metrics) → JSON + HTML report, sliceable by family/content_type. |
| **EU-6** | Seed the 72-claim set; capture an initial hard-case batch (Mode A CON/PDF queries + Mode B known PDFs); produce a first baseline report. |
| **v2 (later)** | Import db8r-mcts `evidential_relation` exports → stance/strength scoring + `polarity_error_rate`; pairwise strength; layout-space annotation. |

## 10. Out of scope for v1 (deferred, with triggers)
- Pairwise strength annotation → if ordinal agreement (kappa) is too noisy.
- Layout-space (PDF bounding-box) annotation + coordinate mapping → v2, after CC-1a/CC-3 improve what lands in `source_text`.
- Stance/strength/`polarity_error_rate` scoring → v2, on db8r-mcts MC-2 `evidential_relation`.
- Active-learning loop / human escalation tier feeding new labels → later.

## 11. Definition of done (v1)
- Capture produces immutable, hashed fixtures for all three modes against a live ClaimCheck.
- Annotation UI loads a fixture, pre-fills pipeline spans, supports correction + doc-level flags, persists gold records to SQLite.
- Scorer emits the §7 v1 metrics from gold + fixtures, offline, with the family/content_type/length breakouts.
- A first baseline report exists over a seed batch.
- Tool connects to **no** production database; fixtures are reproducible and integrity-checked.
