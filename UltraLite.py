"""
confidence_tagging.py

Plug-in module for the larger RubbleScan workflow.

Takes the confidence levels produced by your detection model for a single
frame (one confidence value per detected heat signature), and works
through EACH one exactly once via a for-loop:

    - If a signature's confidence is already >= HIGH_CONFIDENCE_THRESHOLD,
      it is tagged immediately: "Potential human detected, high confidence".
    - Otherwise, its region is zoomed/cropped and re-evaluated (via your
      real model, plugged in through `reevaluate_confidence`). If the
      percentage change from the re-evaluation clears
      REEVALUATION_CHANGE_THRESHOLD, it is tagged the same way.
    - If neither condition is met, it is left untagged (logged as
      "not confirmed").

No items are ever deleted/removed from the input list. Every signature
in the input is visited once and ends up with a tag or a not-confirmed
status. Sorting ascending by confidence only affects processing ORDER,
not membership in the list.

INTEGRATION POINTS (marked below with # >>> INTEGRATE):
  1. `signatures` — replace the example data with the real output from
     your detection model for the current frame.
  2. `reevaluate_confidence()` — replace the manual-input placeholder
     with a call to your trained re-evaluation model.
  3. `crop_region()` — replace with your actual image-cropping call
     (PIL/numpy/etc.) once you're passing real image + bbox data.
"""

# ---------------------------------------------------------------------------
# Tunable thresholds
# ---------------------------------------------------------------------------
HIGH_CONFIDENCE_THRESHOLD = 0.6        # immediate-tag cutoff
REEVALUATION_CHANGE_THRESHOLD = 0.2    # 20% relative change required to tag


# ---------------------------------------------------------------------------
# >>> INTEGRATE (1): confidence levels for each heat signature in this frame.
# Replace this example list with the real output from your detection model,
# e.g. signatures = model.get_detections(frame)
# Each entry: (signature_id, confidence, bbox)
# ---------------------------------------------------------------------------
signatures = [
    ("sig-1", 0.91, (10, 10, 60, 90)),
    ("sig-2", 0.30, (120, 40, 170, 130)),
    ("sig-3", 0.42, (200, 60, 250, 150)),
    ("sig-4", 0.15, (260, 80, 310, 170)),
]


def crop_region(image, bbox):
    """
    >>> INTEGRATE (3): replace with real cropping logic for your image type.
    e.g. PIL:    return image.crop(bbox)
         numpy:  x1, y1, x2, y2 = bbox; return image[y1:y2, x1:x2]
    For now this just passes bbox through, since no real image is wired in.
    """
    return bbox


def reevaluate_confidence(signature_id, cropped_region):
    """
    >>> INTEGRATE (2): replace with a call to your trained model, e.g.
        return your_model.predict(cropped_region)

    Placeholder below just prompts you for a number so you can manually
    test the workflow before the real model is ready.
    """
    while True:
        raw = input(
            f"    Re-evaluate '{signature_id}' -> enter new confidence [0-1]: "
        ).strip()
        try:
            value = float(raw)
        except ValueError:
            print("    Please enter a number between 0 and 1.")
            continue
        if 0.0 <= value <= 1.0:
            return value
        print("    Please enter a number between 0 and 1.")


def percent_change(original, updated):
    if original == 0:
        return float("inf") if updated > 0 else 0.0
    return abs(updated - original) / original


def process_signatures(image, signatures):
    """
    Works through every signature in the input exactly once, in ascending
    confidence order. Nothing is removed from `signatures` — this just
    controls processing order and produces a tag/no-tag result per item.
    """
    ordered = sorted(signatures, key=lambda s: s[1])  # ascending by confidence

    for signature_id, confidence, bbox in ordered:

        if confidence >= HIGH_CONFIDENCE_THRESHOLD:
            print(
                f"[TAG] {signature_id}: confidence {confidence:.2f} >= "
                f"{HIGH_CONFIDENCE_THRESHOLD:.2f} -> "
                f"Potential human detected, high confidence"
            )
            continue

        print(f"[ZOOM] {signature_id}: re-evaluating (original confidence {confidence:.2f})...")
        cropped = crop_region(image, bbox)
        updated_confidence = reevaluate_confidence(signature_id, cropped)
        change = percent_change(confidence, updated_confidence)
        print(f"       new confidence={updated_confidence:.2f}, change={change * 100:.1f}%")

        if change >= REEVALUATION_CHANGE_THRESHOLD:
            print(
                f"[TAG] {signature_id}: change >= "
                f"{REEVALUATION_CHANGE_THRESHOLD * 100:.0f}% -> "
                f"Potential human detected, high confidence"
            )
        else:
            print(f"[NOT CONFIRMED] {signature_id}: change below threshold")

        print()


if __name__ == "__main__":
    # >>> INTEGRATE: replace `image=None` with your actual frame object.
    process_signatures(image=None, signatures=signatures)