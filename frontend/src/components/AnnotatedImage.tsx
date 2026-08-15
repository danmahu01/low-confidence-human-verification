import { useEffect, useRef, useState } from 'react';

import { projectBox, readMetrics, type Metrics } from '../lib/geometry';

export interface Annotation {
  id: string;
  bbox: [number, number, number, number];
  /** Drives the box colour via a `box-<variant>` class. */
  variant: string;
  label?: string;
}

interface Props {
  src: string;
  alt: string;
  annotations: Annotation[];
}

/** An image with boxes drawn over it, kept aligned as the element resizes. */
export default function AnnotatedImage({ src, alt, annotations }: Props) {
  const ref = useRef<HTMLImageElement>(null);
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
  }, []);

  return (
    <div className='annotated'>
      <img ref={ref} src={src} alt={alt} onLoad={measure} className='annotated-img' />

      {metrics &&
        annotations.map((a) => (
          <div
            key={a.id}
            className={`box box-${a.variant}`}
            style={projectBox(a.bbox, metrics)}
          >
            {a.label && <span className='box-label'>{a.label}</span>}
          </div>
        ))}
    </div>
  );
}
