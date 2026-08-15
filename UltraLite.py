"""
refinement_pipeline.py

Confidence-refinement pipeline for thermal human-detection.

This module handles ONLY the data-processing/control-flow logic described in
the workflow below. It does NOT implement, train, or approximate any
classification model. Wherever a model call is required, this module calls
out to a pluggable interface (`ReevaluationModel`) that you supply. A
`MockReevaluationModel` is included purely so the pipeline is runnable and
testable before the real model exists — swap it out for your trained model
by implementing the same interface.

Workflow implemented:
    1. Take a thermal image + a list of raw per-human detections
       (bbox + initial confidence) for that frame.
    2. Sort detections ascending by confidence.
    3. Any detection at/above HIGH_CONFIDENCE_THRESHOLD is immediately
       pinged as "Potential human detected, high confidence" and removed
       from the working list.
    4. For everything remaining (still ascending by confidence), take the
       lowest-confidence item first:
         a. Crop ("zoom into") the image using that detection's bbox.
         b. Re-evaluate confidence for that crop via the pluggable model.
         c. Compute percentage change between original and re-evaluated
            confidence.
         d. If the percentage change >= REEVALUATION_CHANGE_THRESHOLD,
            ping "Potential human detected, high confidence" and remove
            the item.
         e. Otherwise, discard the item as unconfirmed and remove it.
    5. Repeat step 4 until the working list is empty.
    6. Signal that the pipeline is ready for a new frame.

Integration note:
    This module expects to receive detections in the same shape your
    upstream detector/model already produces (id, bbox, confidence).
    It does not read images from disk/network itself beyond cropping
    a bbox region for the re-evaluation step — wire that up to your
    actual image object type as needed (see `image_cropper` below).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Protocol, Sequence


# ---------------------------------------------------------------------------
# Tunable thresholds — adjust once your model's real confidence distribution
# is known. These are just sane placeholder defaults.
# ---------------------------------------------------------------------------

HIGH_CONFIDENCE_THRESHOLD: float = 0.85       # immediate-accept cutoff
REEVALUATION_CHANGE_THRESHOLD: float = 0.20   # 20% relative change required


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

BBox = tuple  # (x1, y1, x2, y2) in image pixel coordinates


@dataclass
class Detection:
    """A single candidate human heat signature within one frame."""
    id: str
    bbox: BBox
    confidence: float
    frame_id: Optional[str] = None
    meta: dict = field(default_factory=dict)


@dataclass
class PingResult:
    """A confirmed 'potential human' output emitted by the pipeline."""
    detection_id: str
    bbox: BBox
    original_confidence: float
    final_confidence: float
    stage: str  # "immediate_accept" or "reevaluated_accept"
    message: str = "Potential human detected, high confidence"


@dataclass
class DiscardResult:
    """A detection that was processed but did not clear the bar."""
    detection_id: str
    bbox: BBox
    original_confidence: float
    final_confidence: float
    percent_change: float


@dataclass
class FrameProcessingLog:
    """Full audit trail for one frame's run through the pipeline."""
    pings: List[PingResult] = field(default_factory=list)
    discards: List[DiscardResult] = field(default_factory=list)
    frame_complete: bool = False


# ---------------------------------------------------------------------------
# Pluggable model interface — DO NOT implement the model itself here.
# Your trained classifier should be wrapped to satisfy this Protocol.
# ---------------------------------------------------------------------------

class ReevaluationModel(Protocol):
    """
    Interface your real, trained model should satisfy.

    `reevaluate` takes a cropped image region (whatever type your image
    pipeline uses — e.g. a PIL.Image, numpy array, tensor) and returns a
    single float confidence in [0, 1] that the crop contains a human.
    """

    def reevaluate(self, cropped_region) -> float:
        ...


class MockReevaluationModel:
    """
    Placeholder ONLY, so this module can run/be tested before your real
    model is wired in. Replace with your actual trained model — this
    class intentionally contains no real classification logic.
    """

    def reevaluate(self, cropped_region) -> float:
        raise NotImplementedError(
            "MockReevaluationModel is a placeholder. Wire in your trained "
            "confidence-classification model here via the ReevaluationModel "
            "interface — this pipeline does not implement or train that model."
        )


# ImageCropper: given a full frame image + a bbox, return whatever
# "cropped region" object your ReevaluationModel expects. Swap this
# out for your actual image library's crop call.
ImageCropper = Callable[[object, BBox], object]


def default_image_cropper(image, bbox: BBox):
    """
    Default cropper stub. Replace with real cropping logic for your image
    type (e.g. PIL: image.crop(bbox); numpy: image[y1:y2, x1:x2]).
    """
    raise NotImplementedError(
        "Provide an image_cropper function matching your image object type."
    )


# ---------------------------------------------------------------------------
# Core pipeline logic
# ---------------------------------------------------------------------------

def _percent_change(original: float, updated: float) -> float:
    """
    Relative percentage change from original to updated confidence.
    Guards against divide-by-zero when original confidence is 0.
    """
    if original == 0:
        return float("inf") if updated > 0 else 0.0
    return abs(updated - original) / original


def process_frame(
    image,
    detections: Sequence[Detection],
    model: ReevaluationModel,
    image_cropper: ImageCropper = default_image_cropper,
    high_confidence_threshold: float = HIGH_CONFIDENCE_THRESHOLD,
    reevaluation_change_threshold: float = REEVALUATION_CHANGE_THRESHOLD,
) -> FrameProcessingLog:
    """
    Run the full ping/re-evaluate/discard workflow over one frame's
    detections until the working list is empty.

    Args:
        image: the full thermal frame (whatever type your cropper expects).
        detections: raw per-human detections for this frame (bbox + confidence).
        model: your trained ReevaluationModel implementation. Required —
               this function will not fabricate confidence values.
        image_cropper: function to crop `image` to a detection's bbox.
        high_confidence_threshold: immediate-accept cutoff (0-1).
        reevaluation_change_threshold: required relative confidence swing
               (0-1) after re-evaluation to accept a low-confidence detection.

    Returns:
        FrameProcessingLog with every ping and discard, in the order
        they were processed. The working list is guaranteed empty when
        this returns (every input detection is accounted for).
    """
    log = FrameProcessingLog()

    # Step 2: sort ascending by confidence.
    working_list: List[Detection] = sorted(detections, key=lambda d: d.confidence)

    # Step 3: immediate accept for anything already high-confidence.
    remaining: List[Detection] = []
    for det in working_list:
        if det.confidence >= high_confidence_threshold:
            log.pings.append(
                PingResult(
                    detection_id=det.id,
                    bbox=det.bbox,
                    original_confidence=det.confidence,
                    final_confidence=det.confidence,
                    stage="immediate_accept",
                )
            )
        else:
            remaining.append(det)

    # remaining is still ascending-confidence order since working_list was sorted.

    # Step 4: work through the remaining list, lowest confidence first,
    # zooming + re-evaluating each one until the list is empty.
    for det in remaining:
        cropped_region = image_cropper(image, det.bbox)
        updated_confidence = model.reevaluate(cropped_region)

        change = _percent_change(det.confidence, updated_confidence)

        if change >= reevaluation_change_threshold:
            log.pings.append(
                PingResult(
                    detection_id=det.id,
                    bbox=det.bbox,
                    original_confidence=det.confidence,
                    final_confidence=updated_confidence,
                    stage="reevaluated_accept",
                )
            )
        else:
            log.discards.append(
                DiscardResult(
                    detection_id=det.id,
                    bbox=det.bbox,
                    original_confidence=det.confidence,
                    final_confidence=updated_confidence,
                    percent_change=change,
                )
            )
        # Item is now removed from the working list by virtue of not being
        # carried forward — no further reprocessing occurs for this item.

    log.frame_complete = True
    return log


def request_new_frame() -> str:
    """
    Called once a frame's working list is empty. Hook this up to your
    actual frame-acquisition source (camera feed, next file in queue, etc.).
    This stub just signals readiness.
    """
    return "READY_FOR_NEXT_FRAME"


# ---------------------------------------------------------------------------
# Example usage (illustrative only — requires a real model + cropper)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    example_detections = [
        Detection(id="det-1", bbox=(10, 10, 60, 90), confidence=0.91),
        Detection(id="det-2", bbox=(120, 40, 170, 130), confidence=0.42),
        Detection(id="det-3", bbox=(200, 60, 250, 150), confidence=0.30),
    ]

    print("This module defines the pipeline but requires a real")
    print("ReevaluationModel + image_cropper to actually run process_frame().")
    print(f"Example working list (sorted ascending) would be:")
    for d in sorted(example_detections, key=lambda d: d.confidence):
        print(f"  {d.id}: confidence={d.confidence}")
