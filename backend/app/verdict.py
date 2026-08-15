"""Roll per-detection outcomes up into one answer for the whole input.

The flowchart flags individual regions as "potential human". This turns that
pile of flags into the single statement the system exists to make about an
image or clip: is there a human in this, and how sure are we?

Precedence is deliberate — one detection the model was outright confident
about outranks any number of low-confidence ones that only survived
re-evaluation, and those in turn outrank detections that failed both checks.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence

from flask import current_app

from .confidence_loop import Status

# Ordered strongest first; the first rule that matches wins.
HIGH = "high"
POSSIBLE = "possible"
UNLIKELY = "unlikely"
NONE = "none"

LABELS = {
    HIGH: "High probability of human presence",
    POSSIBLE: "Possible human presence",
    UNLIKELY: "Unlikely human presence",
    NONE: "No human presence detected",
}


@dataclass
class Verdict:
    level: str
    label: str
    detail: str
    total: int
    confident: int
    rescued: int
    unconfirmed: int
    max_confidence: float | None

    def to_dict(self) -> dict:
        return asdict(self)


def _plural(count: int, noun: str = "person") -> str:
    if noun == "person":
        return f"{count} person" if count == 1 else f"{count} people"
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def summarise(detections: Sequence) -> Verdict:
    """Produce the overall verdict for one upload."""
    total = len(detections)
    max_confidence = (
        round(max(d.confidence for d in detections), 4) if detections else None
    )

    # When the re-evaluation loop is switched off, statuses are absent — fall
    # back to the flowchart's own "flag outright" gate so a verdict is still
    # produced. Note this is REEVAL_CONF_THRESHOLD, not CONFIDENCE_THRESHOLD:
    # the latter sets review priority, which is a different question.
    threshold = current_app.config["REEVAL_CONF_THRESHOLD"]
    has_status = any(getattr(d, "status", None) for d in detections)

    if has_status:
        confident = sum(
            1 for d in detections if d.status == Status.FLAGGED_HIGH_CONF.value
        )
        rescued = sum(
            1 for d in detections if d.status == Status.FLAGGED_REEVAL.value
        )
        unconfirmed = sum(
            1 for d in detections if d.status == Status.NOT_CONFIRMED.value
        )
    else:
        confident = sum(1 for d in detections if d.confidence >= threshold)
        rescued = 0
        unconfirmed = total - confident

    if confident:
        level = HIGH
        detail = f"{_plural(confident)} detected with high confidence."
    elif rescued:
        level = POSSIBLE
        detail = (
            f"{_plural(rescued)} flagged after re-evaluating the region up close."
        )
    elif total:
        level = UNLIKELY
        noun = "region" if total == 1 else "regions"
        detail = (
            f"{total} candidate {noun} found, but none held up on re-evaluation."
            if has_status
            else f"{total} candidate {noun} found, none above the "
            f"{threshold:.0%} confidence gate."
        )
    else:
        level = NONE
        detail = "Nothing resembling a person was found."

    return Verdict(
        level=level,
        label=LABELS[level],
        detail=detail,
        total=total,
        confident=confident,
        rescued=rescued,
        unconfirmed=unconfirmed,
        max_confidence=max_confidence,
    )
