# Evidence Gold-Eval & Annotation Utility — v1 Design Note

**Status:** design, approved direction. **Canonical copy** lives here in `db8r-eval-utility/docs/` (a point-in-time snapshot is also committed under `db8r-mcts/docs/plans/` in the pipeline-planning history). See the repo [`README.md`](../README.md) for the implementation brief.
**Related:** [`EVIDENCE_PIPELINE_REFACTOR_CLAIMCHECK.md`](../../db8r-claimcheck/EVIDENCE_PIPELINE_REFACTOR_CLAIMCHECK.md) (esp. CC-5, CC-9) and [`2026-06-16-evidence-pipeline-refactor-mcts.md`](../../db8r-mcts/docs/plans/2026-06-16-evidence-pipeline-refactor-mcts.md) (esp. MC-2, MC-5).

---

## 1. Purpose

A gold dataset + scorer that measures how well the evidence pipeline **finds** germane source material and **extracts** evidence from it. It exists because today there is *no* metric for retrieval/extraction accuracy — only downstream debate outcomes, which confound everything. It is also the gate that unblocks the "blocked on gold eval set" work in both agent briefs (extraction model choice, threshold tuning, flipping verification to `delegate`) and the eventual RL-foraging reward.

It is **not** part of either production runtime.

## 2. Locked decisions

| Decision | Choice |
|---|---|
| DB access | **Neither production DB directly.** Consume exports/API responses; write to the tool's own store. |
| Tool form | **Standalone** (own repo, own store), a ClaimCheck *client*. |
| Input modes | **A** unilateral search (`POST /api/v1/search`), **B** extract-a-specific-document (`POST /api/v1/extract`, CC-9), **C** import a captured debate `/search` response. Not reliant on db8r debates. |
| v1 / v2 scope | **v1 = ClaimCheck-only metrics** (retrieval, extraction span P/R, fidelity, lost-evidence). **v2 = stance/strength + `polarity_error_rate`**, after MC-2 exposes `evidential_relation`. |
| Strength labels | **Ordinal only** (none/weak/moderate/strong). Pairwise comparison deferred. |
| Annotation surface | Annotate against the pipeline's **`source_text`** (char-offset space). Show the original PDF/HTML as a **read-only reference pane**. Add a **document-level "evidence lost in extraction" flag**. Defer layout-space annotation. |

## 3. Architecture / data flow

```
ClaimCheck (dev instance)
   │  Mode A: /search(query)        Mode B: /extract(url|text)      Mode C: import existing /search response
   ▼
Captured response  ──►  frozen FIXTURE (immutable, hashed)   ← the unit of everything
   │                         (system output + source_text)
   ▼
Annotation UI (offline)  ──►  GOLD records (reference fixture by hash)
   │   pre-filled from the fixture's extracted spans; human corrects
   ▼
Scorer (offline)  ──►  metrics report (joins gold ↔ fixture)
```

- **Live ClaimCheck is needed only to capture** (Modes A/B). Annotation and scoring are fully offline against frozen fixtures.
- A fixture is interchangeable regardless of mode (same payload shape; CC-9 returns the same shape as `/search` minus provider results).
- Fixtures are **immutable and hashed** (`source_text_hash`) so gold offsets can never silently desync from the text they were drawn against.

### 3.1 The foraging-strategy layer (retrieval is two stages, two owners)

`claim` and `query` are **not** the same thing. db8r-mcts turns one claim into a **foraging strategy** — a portfolio of queries (verified: `generate_pregame_portfolio` → ranked `PrioritizedQuery{pool,query,strategy,priority}`; `debate_service` fans out **one `/search` per query**, N per claim). Retrieval therefore splits:

```
claim ──[db8r-mcts generator: MC-5 /api/v1/foraging-strategy]──► forage_strategy (portfolio of forage_queries)
          each forage_query ──[ClaimCheck /search + providers]──► ranked docs ──► germane subset (gold)
```

| Sub-stage | Owner | Metric | Notes |
|---|---|---|---|
| **1a Foraging** (claim → queries) | **db8r-mcts** generator / foraging RL | **foraging recall** (per claim) | the RL reward; tagged by `generator_version` |
| **1b Retrieval** (query → docs) | **ClaimCheck** | **ClaimCheck retrieval recall** (per query) | isolates provider/ranking |

**Foraging-quality capture** uses db8r-mcts's *real* generator via a new read-only endpoint **MC-5 `POST /api/v1/foraging-strategy {claim, mode:"pregame"|"reactive", …}` → `{generator_version, queries:[{pool,query,strategy,priority,rank,providers}]}`** (the db8r-mcts analog of CC-9 — invokes `generate_pregame_portfolio`, no session/DB/ClaimCheck side effects). Flow: MC-5 → replay each query through ClaimCheck `/search` (Mode A) → fixtures linked to the query → score. *(Per-query `providers` routing is **planned** — recorded now though `gather()` currently sends a static providers list; aligns with the MC-4 RL action space.)*

### 3.2 Annotation stability (no reannotation when foraging is enriched)

**Gold labels key to durable referents only:** `claim`, `document` (**content-addressed by `source_text_hash`**), and `span` (offset into that source_text). They never key to queries, foraging strategies, or `generator_version`. Therefore:
- Enriching the foraging strategy (new generator, more queries, per-engine routing, RL policy) → **re-score only.** Same documents reuse all labels; only **newly-surfaced documents** need (additive) annotation — which is the improvement being measured, not rework.
- `retrieval_judgment` and `relevant_to_claim` are `(claim × document)` → reused across all generator versions.
- The only thing that invalidates span labels is a change to a document's `source_text` (a ClaimCheck **extraction** rebuild) → a new fixture/hash. Old labels stay valid against the old fixture; a migration pass re-locates gold spans by verbatim text-match into the new `source_text`, hand-reviewing only the misses.

## 4. v1 gold-set schema

The store has two layers: **fixtures** (captured, immutable) and **gold annotations** (reference fixtures by hash). The annotations serve **three tasks** (see §6): **T1 retrieval judgment**, **T2 span annotation**, **T3 stance/strength**. Two judgment frames matter and live at **different layers** (this is the key schema decision):

- **span-intrinsic** (claim-independent): is a span a well-formed, self-contained, verifiable statement → `gold_span.is_claim_bearing`. Annotated **once per span**, reusable across every claim the document is paired with.
- **claim-conditioned** (per claim): is a well-formed span germane to / what stance toward a *specific* claim → `claim_span_label`. Annotated per `(claim, span)`.

> **Capture mode ≠ evaluation goal.** How a document was captured (Mode A/B/C) is independent of which goals it can serve. Eligibility for T1/T3 is gated by a **`claim_document_link`** — a Mode-B claimless document serves only T2 until a claim is attached. Stance/strength fields exist but are **unscored in v1** (forward-compat for v2).

### 4.1 `fixture` (captured ClaimCheck output — immutable)
| Field | Notes |
|---|---|
| `fixture_id` | stable id |
| `capture_mode` | `search_A` \| `extract_B` \| `debate_C` |
| `query` | query used (A; optional relevance hint for B) |
| `claimcheck_version` / `job_id` | provenance |
| `documents[]` | each: `document_id`, `source_url`, `provider(s)`, `content_type`, `fetched_at`, `source_reliability`, `retrieval_rank`, `source_text`, `source_text_hash`, `source_text_char_len`, **`extraction_status`** (CC-3a: `partial_extraction`/`chunks_*`/`token_budget`/`warnings`) |
| `extracted_spans[]` | the **system output** to be scored: `char_offset`, `char_length`, `text`, `extraction_fidelity`, `match_method`, `source_assertion_opinion`, `claimset_orientation` (read from the response `claims[]` array — see Appendix A) |
| `retrieval_results[]` | ranked `(document_id, rank, provider, relevance_score)` for Mode A |

### 4.2 `claim` (debate proposition)
| Field | Notes |
|---|---|
| `claim_id`, `text` | |
| `family` | policy \| factual \| comparative \| predictive \| causal \| existence |
| `proof_standard` | PE \| CCE \| BRD \| DV (used in v2) |
| `split` | `train` \| `dev` \| **`test` (frozen holdout, never used for tuning)** |
| `notes` | |

### 4.3 `claim_document_link` (first-class; gates T1/T3 eligibility)
| Field | Notes |
|---|---|
| `claim_id`, `document_id` | |
| `origin` | `search` (Mode A — created implicitly) \| `manual` (attach any document, incl. Mode B, to any claim) |
| `notes` | |

### 4.4 `document_annotation` (per document — claim-independent)
| Field | Notes |
|---|---|
| `document_id`, `fixture_id` | |
| `exhaustively_annotated` | **bool** — every claim-bearing span in the doc was marked (required for extraction *recall* to be defined) |
| `lost_evidence_flag` | **bool** + `note` — material evidence present in the original document but absent from `source_text` (text-extraction-layer coverage signal; no offset) |

### 4.5 `gold_span` (span-intrinsic; claim-independent; reusable)
| Field | Notes |
|---|---|
| `span_id`, `document_id` | (no `claim_id` — claim-conditioned judgments live in `claim_span_label`) |
| `char_offset`, `char_length` | indices into the fixture's `source_text` (same space as `extracted_spans`) |
| `text` | verbatim copy (integrity check against `source_text_hash`) |
| `is_claim_bearing` | **bool** — well-formed, self-contained, verifiable statement (vs. chrome/opinion-fragment/half-sentence). Replaces the old ambiguous `is_evidence`. |
| `label_source` | `pipeline_prefill_corrected` \| `human_authored` |
| `annotator_id`, `timestamp`, `notes` | |

### 4.6 `claim_span_label` (claim-conditioned: germaneness + stance/strength)
| Field | Notes |
|---|---|
| `claim_id`, `span_id` | references a `gold_span` and a `claim` |
| `relevant_to_claim` | **bool** or graded — is this well-formed span germane to **this** claim (the v1 claim-conditioned target) |
| `stance` | PRO \| CON \| NEUTRAL — **optional, unscored in v1** (v2) |
| `strength_ordinal` | none \| weak \| moderate \| strong — **optional, unscored in v1** (v2) |
| `annotator_id`, `timestamp`, `notes` | |

### 4.7 `retrieval_judgment` (T1; claim × document)
| Field | Notes |
|---|---|
| `claim_id`, `document_id` | `document_id` is **content-addressed** (`source_text_hash`) so a doc re-retrieved by any future strategy reuses this judgment |
| `forage_query_id` | which query surfaced it (attributes a hit/miss to a specific query); null for manual/Mode-B |
| `relevant` | bool or graded 0–3 |
| `retrieval_rank` | rank in the captured results |
| `annotator_id` | |

### 4.7a `forage_strategy` (db8r-mcts generator output; captured via MC-5 or Mode C)
| Field | Notes |
|---|---|
| `forage_strategy_id`, `claim_id` | |
| `mode` | `pregame` \| `reactive` |
| `generator_version` | model/heuristic + config provenance — **the key for before/after foraging-recall comparison** |
| `context` | reactive only: role, proof_standard, target, move that conditioned it |
| `source` | `mc5_endpoint` \| `debate_trace` |

### 4.7b `forage_query` (one query in a strategy)
| Field | Notes |
|---|---|
| `forage_query_id`, `forage_strategy_id` | |
| `pool` | PRO \| CON |
| `query`, `strategy`, `priority`, `rank` | from the `PrioritizedQuery` |
| `providers` | recorded for future per-engine routing (static today) |
| `fixture_id` | the ClaimCheck `/search` fixture produced by replaying this query |

### 4.8 `dataset` (metadata)
`dataset_version`, `schema_version`, `created_at`, `annotation_guidelines_version`, split definitions.

### 4.9 Claim seeding & hard-case sampling
- **Reuse the existing 72-claim pre-RL stress corpus** ([`2026-05-20-pre-rl-stress-claim-corpus.md`](../../db8r-mcts/docs/plans/2026-05-20-pre-rl-stress-claim-corpus.md)) as the v1 claim set: 60 primary-family claims (10 each across `policy`, `factual`, `comparative`, `predictive`, `causal`, `existence` — including the polarity-reversed partners) plus the 12 hybrid claims. Reusing it means the gold set and the stress runner share claim vocabulary, families, evidence-density tiers, and expected-tendency labels, so eval results and stress traces are directly comparable.
- **Claim selection ≠ document selection.** The *claims* come from the corpus and stay family-balanced. The **hard-case over-sampling happens at the document layer**, via the input modes, not by adding exotic claims:
  - **Mode A (unilateral search):** for each claim, deliberately issue **CON-framed** and **PDF/primary-source-targeted** queries (e.g. `filetype:pdf`, agency/site filters) — not just the PRO-framed queries db8r's current generator would produce — so the judged document pool includes the evidence the pipeline is *worst* at surfacing.
  - **Mode B (extract-by-document, CC-9):** directly ingest known **PDFs, long reports, table/number-bearing sources, and documents containing contradictory evidence**, guaranteeing they are in the set regardless of whether retrieval would find them. This is what makes the §5.2 content-type / length breakouts and the §5.4 lost-evidence rate meaningful.
- **Holdout discipline:** reserve a frozen `test` split of claims (mirror the family balance) that is **never** used for threshold tuning or model selection, per the `claim.split` field. Headline numbers (esp. the v2 `polarity_error_rate`) are reported on that holdout only.

## 5. v1 metric definitions

All v1 metrics are computed by the scorer joining `gold_*` to the referenced `fixture`. **Stance/strength/`polarity_error_rate` are v2** (need MC-2 `evidential_relation`); the schema carries the fields but the v1 scorer ignores them.

### 5.1 Retrieval — two metrics, two owners (needs `retrieval_judgment` + foraging entities)
- **1b · ClaimCheck retrieval recall@k / precision@k** (per `forage_query`, owner = ClaimCheck): of the germane docs findable by query Q, how many did ClaimCheck return in top-k? Isolates provider/ranking. Denominator approximated by the pooled judged set for Q.
- **1a · Foraging recall** (per `claim`, owner = db8r-mcts generator — **the RL reward**): of all gold germane docs that *exist for the claim*, how many did the **entire generated strategy** surface across its N queries? `= |germane found by ∪ queries| / |all gold germane for claim|`, computed **per `generator_version`** for before/after comparison. **Denominator must be generator-independent** — built from the gold germane pool (independent search + **Mode B** direct-ingest of known-germane docs), never from the generator's own output, or it is circular.
  - *Per-query attribution:* which queries contributed *unique* germane docs vs. redundant/empty — feeds RL credit assignment.
- **coverage** = % claims with ≥1 germane doc retrieved.
- **primary-source coverage** = % claims where a high-`source_reliability`/PDF/primary doc appears in top-k. *(Payoff of provider expansion + CC-1a.)*

### 5.2 Extraction spans (needs `gold_span` + offsets; doc must be `exhaustively_annotated` for recall)
- **Match criterion:** a gold span and an extracted span match iff same document and character-range **IoU ≥ τ** (default τ = 0.5). `IoU = |overlap| / |union|` on char ranges.
- **Well-formedness precision** = (extracted spans matching a gold span with `is_claim_bearing=true`) / total extracted spans. *Claim-independent; measures "did the extractor pull usable units vs. garbage."*
- **Targeting precision** (per claim; needs a `claim_document_link`) = (extracted spans matching a gold span that is `relevant_to_claim` for that claim) / total extracted spans. *Measures "did the extractor pull on-topic units" — separates a query/targeting failure from a junk-extraction failure.*
- **Germane recall** (per claim — the recall that matters for debate) = (matched gold spans that are `is_claim_bearing ∧ relevant_to_claim`) / (all such gold spans). Needs exhaustive claim-bearing annotation + `relevant_to_claim` labels.
- **Well-formed recall** (claim-independent, secondary) = matched `is_claim_bearing` gold spans / all `is_claim_bearing` gold spans.
- **F1** on the germane set.
- **Breakouts (the diagnostic value):** report recall by **document-length bucket** (exposes truncation → CC-3), by **`content_type`** (HTML vs PDF → CC-1a), and by `capture_mode`.

### 5.3 Extraction fidelity (needs fixture `extraction_fidelity`/`match_method`, post-CC-5)
- **match-method distribution** across extracted spans (`exact`/`normalized`/`fuzzy`).
- **mean `extraction_fidelity`**.
- **verbatim-locatability rate** = % extracted spans whose `text` is found in `source_text` (sanity; should be ≈100% given the verbatim guard — a drop signals a guard regression).

### 5.4 Text-extraction coverage (needs `document_annotation.lost_evidence_flag`)
- **lost-evidence rate** = % documents where material evidence was absent from `source_text`. This is the **text-extraction-layer** failure, kept separate from extractor recall so the two owners (CC-1a/CC-3 vs. the extractor) aren't conflated. The number CC-1a/CC-3 must drive down.

### 5.5 Deferred to v2 (need MC-2)
- **stance accuracy** + macro-F1, confusion matrix highlighting PRO↔CON.
- **strength** agreement (quadratic-weighted kappa / Spearman on ordinal).
- **`polarity_error_rate`** — the headline system safety metric (fraction of admitted evidence on the wrong side).

## 6. Annotation tasks, UIs, and workflow

The tool has **multiple goals, each a distinct annotation task with its own screen** — but they share **one dataset and substrate** (one tool, three screens, not three tools). A fixture's eligibility for a task depends on whether it carries the needed context (a `claim_document_link`), **not** on how it was captured.

| Task (screen) | Measures (issues) | Unit annotated | Needs a claim? | UI requirements | Data produced |
|---|---|---|---|---|---|
| **T1 — Retrieval judgment** | retrieval (§5.1) | (claim, ranked doc list) | **Yes** | claim + ranked results (title/snippet/url); mark each relevant/not. List-based, fast; no `source_text`/spans | `retrieval_judgment` |
| **T2 — Span annotation** (+ lost-evidence) | extraction (§5.2) + text-loss (§5.4) | (document / `source_text`) | **No** (topic-light) | `source_text` pane (single text node) + pre-filled pipeline spans + correct/add/delete + reference pane + doc-level `exhaustively_annotated` / `lost_evidence_flag` | `gold_span` (`is_claim_bearing`), `document_annotation` |
| **T3 — Stance/strength** | stance (§5.5, v2) | (claim, span) | **Yes** | proposition + one span (with context) → `relevant_to_claim`, and (v2) stance + strength + abstain | `claim_span_label` |

**Overlap & flow (why it's one shared dataset):**
- `gold_span` is the **bridge** between T2 and T3 — T3 labels stance on the *very spans T2 produced*, so T2 precedes T3 for a given doc.
- `claim` is the join key for T1 and T3; the `claim_document_link` gates their eligibility.
- Natural pipeline-order workflow on one fixture: **T1 → T2 → T3**, each screen adding its layer; documents/fixtures shared across all.
- A Mode-A search fixture (carries a query+claim) is eligible for all three; a Mode-B claimless document is T2-only until you attach a claim.

**Shared workflow principles (all screens):**
- **Pre-fill, don't author.** Seed candidates from the fixture's `extracted_spans`; the human **corrects** (adjust offsets, toggle `is_claim_bearing`/`relevant_to_claim`, add missed spans, set doc-level flags). Every correction is both a gold label and a measured pipeline error; `label_source` records which.
- **Blind subset:** annotate a small subset **without** pre-fill (find spans cold) to calibrate the anchoring effect on recall; keep the gap as a correction factor on pre-filled bulk.
- **Read-only reference pane** renders the original PDF/HTML for context; highlights happen only in the `source_text` pane.
- **Exhaustiveness** is explicit per document (`exhaustively_annotated`) so the scorer knows where recall is defined.

## 7. Dependencies & sequencing
- **CC-9** (`/extract`) — required for Mode B (extraction scored independent of retrieval, and the foraging-recall denominator).
- **CC-5** (`extraction_fidelity`/`match_method` in payload + persisted) — required for §5.3.
- **MC-5** (db8r-mcts `POST /api/v1/foraging-strategy`) — required for foraging-quality capture (§3.1, §5.1 metric 1a). Read-only; `pregame` mode first.
- **CC-10a / CC-10b — ✓ LIVE (verified 2026-06-17).** CC-10a: opt-in full `source_text` on evidence documents + per-claim `statement_offset/length` + `verbatim_span` on `EvidenceExtractedClaim`. CC-10b: per-request `full_document_extraction` (no shared-server flag). The capture client now captures full `source_text` for **all** fetched docs (Mode A async-poll with `include_evidence_documents`+`include_source_text`; `/extract`-by-URL via POST flags), with `source_text[offset:offset+length] == verbatim_span` verified 25/25. **Score against `verbatim_span`, not the possibly-normalized `claim.statement`.** (Earlier "blocked until CC-10a / raw_text-only" status is resolved.)
- **v2** stance/strength scoring — blocked on **MC-2** exposing per-span `evidential_relation` via an export (extension of the existing evidence-trace export).
- Tool build itself (UI + scorer + store) is independent and can start now against captured fixtures; only **capturing** needs a dev ClaimCheck instance.

## 8. Out of scope for v1 (deferred, with triggers)
- Pairwise strength annotation → if ordinal agreement (kappa) is too low.
- Layout-space (PDF bounding-box) annotation + coordinate mapping → v2, once CC-1a/CC-3 improve what lands in `source_text`.
- Stance/strength/`polarity_error_rate` scoring → v2, on MC-2.
- Active-learning loop / human escalation tier feeding new labels → later.

---

## Appendix A — Verified integration notes (2026-06-16, live build)

Verified against the running ClaimCheck container (CC-5/CC-9 build) via live `/api/v1/extract` calls. Record for the harness implementer.

1. **Read offsets/fidelity from the `claims` array, not the projections.** In the `/extract` (and `/search`) `SearchJobResponse`, `statement_offset`/`statement_length` are populated only on the canonical **`claims[]`** records. The `unified_results[]` and `evidence_documents[].extracted_claims[]` projections carry `extraction_fidelity`/`match_method`/`source_assertion_opinion` but return `statement_offset: null`. The gold-eval scorer must join spans by the `claims[]` array for offset-based span matching.
2. **Live model key is configured; `/extract` exercises the real extractor.** Container runs `GENERAL_LLM=gpt-4.1-nano`, `MOCK_EXTRACTION_ENABLED=false`, real `OPENAI_API_KEY`. A verified raw-text extract returned two verbatim spans with `extraction_fidelity=1.0`, `match_method="exact"`, correct offsets, and `source_assertion_opinion` (disbelief 0.0) emitted alongside legacy `subjective_logic_opinion`. (Low raw belief ≈0.25 on unknown-domain raw text is source-reliability discounting, **not** a mock signal.)
3. **CC-3 partial-result reporting — initially a gap, RESOLVED by CC-3a (re-verified 2026-06-16).** The first test (build before CC-3a) showed a truncated 25.7k-char doc returning no partial signal. After CC-3a (`Propagate partial extraction status`), the same repro surfaces partial status in **three places**: a job-level and per-`evidence_documents[]` **`extraction_status`** object `{partial_extraction, chunks_processed, chunks_total, tokens_used, token_budget, warnings:["max_chunks_exceeded"]}`; job-level **`warnings`** `["partial_extraction","partial_extraction_chunk_budget"]`; and evidence-document **`validation_warnings`** entries `partial_extraction`/`partial_extraction_chunk_budget` (token path: `partial_extraction_token_budget`). **Harness consequence:** capture `extraction_status` onto the fixture and exclude `partial_extraction:true` fixtures from extraction-recall denominators.
