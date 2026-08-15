import { useEffect, useState, type RefObject } from 'react';

import type { Person } from '../types';

/** Natural (source) size of the media, and the size it's rendered at. */
interface Metrics {
  naturalWidth: number;
  naturalHeight: number;
  elementWidth: number;
  elementHeight: number;
}

function readMetrics(el: HTMLImageElement | HTMLVideoElement): Metrics | null {
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
 * Tracks the rendered size of the media element, so boxes stay aligned when
 * the window resizes or the source finishes loading.
 */
export function useMediaMetrics(
  ref: RefObject<HTMLImageElement | HTMLVideoElement | null>,
) {
  const [metrics, setMetrics] = useState<Metrics | null>(null);

  const measure = () => {
    if (ref.current) setMetrics(readMetrics(ref.current));
  };

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ref]);

  return { metrics, measure };
}

interface Props {
  person: Person;
  metrics: Metrics;
}

/**
 * Draws one detection box over the media.
 *
 * The media uses object-fit: contain, so the painted content is letterboxed
 * inside the element. Boxes are in source pixels, so they need the same
 * scale-and-centre transform the browser applied to the image itself.
 */
export default function BoundingBox({ person, metrics }: Props) {
  const { naturalWidth, naturalHeight, elementWidth, elementHeight } = metrics;

  const scale = Math.min(
    elementWidth / naturalWidth,
    elementHeight / naturalHeight,
  );
  const offsetX = (elementWidth - naturalWidth * scale) / 2;
  const offsetY = (elementHeight - naturalHeight * scale) / 2;

  const [x1, y1, x2, y2] = person.bbox;

  return (
    <div
      className={`bbox bbox-${person.priority}`}
      style={{
        left: offsetX + x1 * scale,
        top: offsetY + y1 * scale,
        width: (x2 - x1) * scale,
        height: (y2 - y1) * scale,
      }}
    >
      <span className='bbox-label'>
        {person.label} {Math.round(person.confidence * 100)}%
      </span>
    </div>
  );
}
