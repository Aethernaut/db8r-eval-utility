"""EU-5 — Scorer. Computes v1 metrics by joining gold records to fixtures (offline).

v1 metrics (README §7; docs/gold-eval-design.md §5). Stance/strength/polarity_error_rate are v2.
  - Retrieval:   recall@k, precision@k, coverage, primary-source coverage
  - Extraction:  TWO precisions (decompose the failure) + germane recall, char-range IoU >= tau (0.5):
                   * well-formedness precision = extracted matching an is_claim_bearing gold span / total extracted
                   * targeting precision (per claim) = extracted matching a relevant_to_claim gold span / total extracted
                   * germane recall (per claim) = matched (is_claim_bearing AND relevant_to_claim) / all such
                 broken out by document-length bucket, content_type, capture_mode
  - Fidelity:    match_method distribution, mean extraction_fidelity, verbatim-locatability rate
  - Coverage:    lost-evidence rate (separate from extractor recall)
  - Exclude fixtures with extraction_status.partial_extraction == true from extraction-recall
    denominators (a truncated doc is not a fair recall target).

TODO(EU-5): implement metrics + JSON/HTML report.
"""

from __future__ import annotations


def char_range_iou(a_offset: int, a_len: int, b_offset: int, b_len: int) -> float:
    """Intersection-over-union of two character ranges. Used for gold↔extracted span matching."""
    a0, a1 = a_offset, a_offset + a_len
    b0, b1 = b_offset, b_offset + b_len
    inter = max(0, min(a1, b1) - max(a0, b0))
    union = (a1 - a0) + (b1 - b0) - inter
    return inter / union if union > 0 else 0.0


# TODO(EU-5): retrieval / extraction / fidelity / coverage metrics + report emitter.
