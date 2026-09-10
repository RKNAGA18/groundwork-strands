"""Confidence-status decision table.

Maps verification verdict + top similarity score to a confidence status
for the review UI, following the exact decision table from AGENTS.md:

| Verdict      | Top similarity  | Status |
|--------------|-----------------|--------|
| grounded     | >= 0.85         | green  |
| grounded     | 0.75 - 0.85     | yellow |
| partial      | any             | yellow |
| unsupported  | any             | red    |
| (no evidence)| --              | red    |
"""

import logging

logger = logging.getLogger(__name__)


def compute_status(verdict: str, top_similarity: float) -> str:
    """Compute the confidence status from verdict and similarity score.

    Args:
        verdict: The verification verdict ("grounded", "partial", or "unsupported").
        top_similarity: The highest similarity score among cited chunks.
            Use 0.0 if no evidence was retrieved.

    Returns:
        One of "green", "yellow", or "red".
    """
    if verdict == "grounded":
        if top_similarity >= 0.85:
            status = "green"
        else:
            # 0.75 - 0.85 or below: technically grounded but marginal
            status = "yellow"
    elif verdict == "partial":
        status = "yellow"
    else:
        # "unsupported" or any unexpected value
        status = "red"

    logger.debug(
        "compute_status(verdict=%s, top_similarity=%.3f) -> %s",
        verdict,
        top_similarity,
        status,
    )
    return status
