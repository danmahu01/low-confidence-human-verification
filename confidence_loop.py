"""
Confidence tagging, structured as the explicit loop drawn in the workflow sketch.

Flow:
    start
      -> input image, bounding boxes, confidences
      -> sort confidences ascending
      -> point at first (lowest-confidence) item
      -> LOOP:
             is everything done?  yes -> stop
             confidence > 0.5?
                 yes -> flag output           -> move onto next confidence
                 no  -> crop region, send to model for re-evaluation
                        delta re-eval (%) > 20?
                            yes -> flag output -> move onto next confidence
                            no  ->                move onto next confidence

The termination condition is the `while cursor < len(queue)` check, which is the
"is everything done?" diamond on the left of the sketch. Every item is visited
exactly once; nothing is deleted from the list and nothing is re-checked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Protocol, Sequence


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------

class Status(str, Enum):
    """Outcome for a single detection."""

    FLAGGED_HIGH_CONF = "flagged_high_confidence"   # passed the 0.5 gate outright
    FLAGGED_REEVAL = "flagged_reeval_jump"          # rescued by the re-evaluation
    NOT_CONFIRMED = "not_confirmed"                 # failed both checks


@dataclass
class Detection:
    """One box from the detector."""

    bbox: tuple[float, float, float, float]  # (x1, y1, x2, y2) in absolute pixels
    confidence: float
    label: str | None = None
    source_index: int | None = None          # position in the original, unsorted input


@dataclass
class TagResult:
    """What the loop decided about one detection, and why."""

    detection: Detection
    status: Status
    original_confidence: float
    reeval_confidence: float | None = None
    delta_pct: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def flagged(self) -> bool:
        return self.status is not Status.NOT_CONFIRMED


class ReEvaluator(Protocol):
    """Anything that can score a cropped region and return a fresh confidence."""

    def __call__(self, crop: Any, detection: Detection) -> float: ...


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def pil_crop(image: Any, detection: Detection) -> Any:
    """Default cropper: assumes a PIL.Image and pixel-space xyxy boxes."""
    x1, y1, x2, y2 = detection.bbox
    return image.crop((int(x1), int(y1), int(x2), int(y2)))


def delta_percent(
    original: float,
    updated: float,
    *,
    mode: str = "relative",
    signed: bool = True,
) -> float:
    """
    Percentage change between the original and re-evaluated confidence.

    mode="relative": (updated - original) / original * 100
        0.20 -> 0.30 is +50.0
    mode="points":   (updated - original) * 100
        0.20 -> 0.30 is +10.0

    signed=True  -> only an *increase* can clear the threshold (a collapse in
                    confidence is evidence against the detection, not for it).
    signed=False -> any movement of sufficient size counts.
    """
    if mode == "points":
        delta = (updated - original) * 100.0
    elif mode == "relative":
        if original == 0.0:
            # Undefined relative change from zero; treat any lift as decisive.
            delta = float("inf") if updated > 0.0 else 0.0
        else:
            delta = (updated - original) / original * 100.0
    else:
        raise ValueError(f"unknown delta mode: {mode!r}")

    return delta if signed else abs(delta)


# --------------------------------------------------------------------------
# The loop
# --------------------------------------------------------------------------

def tag_detections(
    image: Any,
    detections: Sequence[Detection],
    reevaluate: ReEvaluator,
    *,
    conf_threshold: float = 0.5,
    reeval_delta_pct: float = 20.0,
    delta_mode: str = "relative",
    signed_delta: bool = True,
    crop_fn: Callable[[Any, Detection], Any] = pil_crop,
) -> list[TagResult]:
    """
    Walk every detection once, lowest confidence first, and tag it.

    Returns one TagResult per input detection, in ascending-confidence order.
    The input sequence is never mutated.
    """
    if not 0.0 <= conf_threshold <= 1.0:
        raise ValueError("conf_threshold must be in [0, 1]")

    # Sort confidence levels in ascending order, remembering where each came from.
    queue: list[Detection] = sorted(
        (
            Detection(
                bbox=d.bbox,
                confidence=d.confidence,
                label=d.label,
                source_index=d.source_index if d.source_index is not None else i,
            )
            for i, d in enumerate(detections)
        ),
        key=lambda d: d.confidence,
    )

    results: list[TagResult] = []
    cursor = 0  # points at the item currently being processed

    # "is everything done?"  No -> keep going.  Yes -> fall out and stop.
    while cursor < len(queue):
        det = queue[cursor]

        # --- confidence > 0.5? -------------------------------------------
        if det.confidence > conf_threshold:
            results.append(
                TagResult(
                    detection=det,
                    status=Status.FLAGGED_HIGH_CONF,
                    original_confidence=det.confidence,
                )
            )
            cursor += 1  # move onto next confidence
            continue

        # --- no: identify image and send to model for re-evaluation ------
        crop = crop_fn(image, det)
        reeval_conf = float(reevaluate(crop, det))
        delta = delta_percent(
            det.confidence,
            reeval_conf,
            mode=delta_mode,
            signed=signed_delta,
        )

        # --- delta re-eval (%) > 20? -------------------------------------
        status = (
            Status.FLAGGED_REEVAL if delta > reeval_delta_pct else Status.NOT_CONFIRMED
        )
        results.append(
            TagResult(
                detection=det,
                status=status,
                original_confidence=det.confidence,
                reeval_confidence=reeval_conf,
                delta_pct=delta,
            )
        )

        cursor += 1  # move onto next confidence

    return results


def flagged_only(results: Sequence[TagResult]) -> list[TagResult]:
    """Convenience filter for the flagged outputs."""
    return [r for r in results if r.flagged]


# --------------------------------------------------------------------------
# Smoke test
# --------------------------------------------------------------------------

if __name__ == "__main__":
    dets = [
        Detection(bbox=(0, 0, 10, 10), confidence=0.82, label="person"),
        Detection(bbox=(10, 10, 20, 20), confidence=0.31, label="person"),
        Detection(bbox=(20, 20, 30, 30), confidence=0.12, label="person"),
        Detection(bbox=(30, 30, 40, 40), confidence=0.55, label="person"),
    ]

    # Stand-in model: the 0.31 box firms up on a closer look, the 0.12 one doesn't.
    def fake_model(crop, detection):
        return {0.31: 0.47, 0.12: 0.13}[round(detection.confidence, 2)]

    out = tag_detections(
        image=None,
        detections=dets,
        reevaluate=fake_model,
        crop_fn=lambda img, det: det.bbox,  # no PIL needed for the test
    )

    for r in out:
        delta = f"{r.delta_pct:+.1f}%" if r.delta_pct is not None else "—"
        print(f"conf={r.original_confidence:.2f}  delta={delta:>8}  {r.status.value}")

    print(f"\n{len(flagged_only(out))} of {len(out)} flagged")
