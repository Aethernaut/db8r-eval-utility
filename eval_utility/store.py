"""EU-3 — Gold store (SQLite). Implements the design-note §4 schema.

Record types (see docs/gold-eval-design.md §4):
  - claim                (id, text, family, proof_standard, split)
  - claim_document_link  (claim_id, document_id, origin=search|manual)  -- gates T1/T3 eligibility
  - document_annotation  (document_id, fixture_id, exhaustively_annotated, lost_evidence_flag)  -- claim-independent
  - gold_span            (span_id, document_id, offsets, text, is_claim_bearing, label_source, ...)  -- span-intrinsic
  - claim_span_label     (claim_id, span_id, relevant_to_claim, [stance, strength_ordinal — v2])  -- claim-conditioned
  - retrieval_judgment   (claim_id, document_id, query, relevant, retrieval_rank)
  - dataset              (dataset_version, schema_version, annotation_guidelines_version)

Two judgment frames: span-intrinsic (`is_claim_bearing`, reusable across claims) lives on
`gold_span`; claim-conditioned (`relevant_to_claim`, stance, strength) lives on `claim_span_label`.
Gold records reference fixtures by hash. This store is the tool's OWN store — never a
production database.

TODO(EU-3): create_tables(), upsert/query helpers.
"""

from __future__ import annotations

# TODO(EU-3): SQLite schema + DAO. Keep stance/strength columns present-but-optional (v2).
