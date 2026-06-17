"""EU-3 — Gold store (SQLite). Implements the design-note §4 schema.

Record types (see ../db8r-mcts/docs/plans/2026-06-16-gold-eval-utility-design.md §4):
  - claim                (id, text, family, proof_standard, split)
  - document_annotation  (document_id, fixture_id, claim_id, exhaustively_annotated, lost_evidence_flag)
  - gold_span            (offsets, is_evidence, [stance, strength_ordinal — v2], label_source, ...)
  - retrieval_judgment   (claim_id, document_id, query, relevant, retrieval_rank)
  - dataset              (dataset_version, schema_version, annotation_guidelines_version)

Gold records reference fixtures by hash. This store is the tool's OWN store — never a
production database.

TODO(EU-3): create_tables(), upsert/query helpers.
"""

from __future__ import annotations

# TODO(EU-3): SQLite schema + DAO. Keep stance/strength columns present-but-optional (v2).
