/** Natural (source) size of a media element, and the size it renders at. */
export interface Metrics {
  naturalWidth: number;
  naturalHeight: number;
  elementWidth: number;
  elementHeight: number;
}

export function readMetrics(
  el: HTMLImageElement | HTMLVideoElement,
): Metrics | null {
  const naturalWidth =
    el instanceof HTMLVideoElement ? el.videoWidth : el.naturalWidth;
  const naturalHeight =
    el instanceof HTMLVideoElement ? el.videoHeight : el.naturalHeight;

  if (!naturalWidth || !naturalHeight) return null;

  return {
    naturalWidth,
    naturalHeight,
    elementWidth: el.clientWidth,
    elementHeight: el.clientHeight,
  };
}

/**
 * Map a box in source pixels onto the rendered element.
 *
 * The media uses object-fit: contain, so the painted content is letterboxed
 * inside the element. Boxes need the same scale-and-centre transform the
 * browser applied to the image itself.
 */
export function projectBox(
  bbox: readonly [number, number, number, number],
  metrics: Metrics,
) {
  const { naturalWidth, naturalHeight, elementWidth, elementHeight } = metrics;

  const scale = Math.min(
    elementWidth / naturalWidth,
    elementHeight / naturalHeight,
  );
  const offsetX = (elementWidth - naturalWidth * scale) / 2;
  const offsetY = (elementHeight - naturalHeight * scale) / 2;

  const [x1, y1, x2, y2] = bbox;

  return {
    left: offsetX + x1 * scale,
    top: offsetY + y1 * scale,
    width: (x2 - x1) * scale,
    height: (y2 - y1) * scale,
  };
}
