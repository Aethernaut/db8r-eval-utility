"""EU-3 (part) — Fixture load/validate. Fixtures are immutable and hashed.

A fixture wraps a captured ClaimCheck SearchJobResponse plus integrity metadata.
Key invariants (README §2, §3):
  - `source_text_hash` pins the exact text gold offsets reference; never mutate a fixture.
  - Read span offsets from the response `claims[]` array only (projections carry null offsets).
  - Capture each document's `extraction_status` (CC-3a) so partial fixtures can be excluded
    from extraction-recall denominators.

TODO(EU-3): implement hashing, schema validation, and accessors.
"""

from __future__ import annotations

import hashlib


def source_text_hash(source_text: str) -> str:
    return hashlib.sha256(source_text.encode("utf-8")).hexdigest()


# TODO(EU-3): Fixture dataclass + loader:
#   - documents[]: source_url, content_type, source_reliability, retrieval_rank,
#                  source_text, source_text_hash, extraction_status
#   - claims[]:    char_offset, char_length, text, extraction_fidelity, match_method,
#                  source_assertion_opinion, claimset_oriented_subjective_logic_opinion
