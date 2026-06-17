"""EU-4 — Annotation UI server (FastAPI). Serves the single-page annotator + persists gold records.

UI spec (README §6):
  - Primary pane: render fixture `source_text` as a single text node so browser selection
    maps directly to raw character offsets (selectionStart/End == char_offset/+length).
  - Pre-fill candidate spans from the fixture `claims[]`; the human CORRECTS (don't author).
  - Read-only reference pane (iframe / PDF.js) for layout context; highlights happen only
    in the source_text pane.
  - Document-level flags: exhaustively_annotated, lost_evidence_flag.
  - stance / strength_ordinal collected but unscored in v1.

TODO(EU-4): FastAPI app, fixture-serving + gold-record persistence endpoints, web/ assets.
"""

from __future__ import annotations

# TODO(EU-4): FastAPI() app, GET /fixtures/{id}, POST /gold, static web/ mount.
