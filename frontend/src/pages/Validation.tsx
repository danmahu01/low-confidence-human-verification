import { useState } from 'react';

import { api } from '../api/client';
import AnnotatedImage, { type Annotation } from '../components/AnnotatedImage';
import type { ValidationResponse } from '../types';

export default function Validation() {
  const [image, setImage] = useState<File | null>(null);
  const [labels, setLabels] = useState<File | null>(null);
  const [result, setResult] = useState<ValidationResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    if (!image || !labels) return;

    setRunning(true);
    setError(null);
    try {
      const body = new FormData();
      body.append('image', image);
      body.append('labels', labels);
      setResult(await api.upload<ValidationResponse>('/validate', body));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Validation failed.');
      setResult(null);
    } finally {
      setRunning(false);
    }
  }

  const mediaUrl = result ? `/api/upload/${result.upload.id}/file` : null;

  // A prediction that matched a ground-truth box is a hit; one that didn't is
  // a false positive. A ground-truth box nothing matched is a miss.
  const predictionBoxes: Annotation[] =
    result?.predictions.map((p) => ({
      id: p.id,
      bbox: p.bbox,
      variant: p.matched ? 'hit' : 'false-positive',
      label: `${Math.round(p.confidence * 100)}%`,
    })) ?? [];

  const truthBoxes: Annotation[] =
    result?.ground_truth.map((g) => ({
      id: g.id,
      bbox: g.bbox,
      variant: g.matched ? 'hit' : 'missed',
      label: g.matched ? undefined : 'missed',
    })) ?? [];

  return (
    <section>
      <h2>Validation</h2>
      <p className='muted'>
        Score the model against ground truth. Upload a test image and its YOLO
        label file (<code>class x_center y_center width height</code>, one line
        per object, values normalised 0–1).
      </p>

      <form onSubmit={run} className='validate-form'>
        <label>
          Test image
          <input
            type='file'
            accept='image/*'
            onChange={(e) => setImage(e.target.files?.[0] ?? null)}
          />
        </label>

        <label>
          Ground truth (.txt)
          <input
            type='file'
            accept='.txt,text/plain'
            onChange={(e) => setLabels(e.target.files?.[0] ?? null)}
          />
        </label>

        <button type='submit' disabled={!image || !labels || running}>
          {running ? 'Scoring…' : 'Run validation'}
        </button>
      </form>

      {error && <p className='error'>{error}</p>}

      {result && mediaUrl && (
        <>
          <div className='compare'>
            <figure>
              <figcaption>
                Predicted — {result.predictions.length}{' '}
                {result.predictions.length === 1 ? 'box' : 'boxes'}
              </figcaption>
              <AnnotatedImage
                src={mediaUrl}
                alt='Model predictions'
                annotations={predictionBoxes}
              />
            </figure>

            <figure>
              <figcaption>
                Ground truth — {result.ground_truth.length}{' '}
                {result.ground_truth.length === 1 ? 'box' : 'boxes'}
              </figcaption>
              <AnnotatedImage
                src={mediaUrl}
                alt='Ground truth'
                annotations={truthBoxes}
              />
            </figure>
          </div>

          <dl className='metrics'>
            <div>
              <dt>Precision</dt>
              <dd>{(result.metrics.precision * 100).toFixed(1)}%</dd>
            </div>
            <div>
              <dt>Recall</dt>
              <dd>{(result.metrics.recall * 100).toFixed(1)}%</dd>
            </div>
            <div>
              <dt>F1</dt>
              <dd>{(result.metrics.f1 * 100).toFixed(1)}%</dd>
            </div>
            <div>
              <dt>Hits</dt>
              <dd>{result.metrics.true_positives}</dd>
            </div>
            <div>
              <dt>False positives</dt>
              <dd>{result.metrics.false_positives}</dd>
            </div>
            <div>
              <dt>Missed</dt>
              <dd>{result.metrics.false_negatives}</dd>
            </div>
          </dl>

          <p className='muted'>
            Matched at IoU ≥ {result.metrics.iou_threshold}. Green boxes matched,
            red are false positives, amber are people the model missed.
          </p>
        </>
      )}
    </section>
  );
}
