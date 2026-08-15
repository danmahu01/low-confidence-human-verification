import { useEffect, useRef, useState, type RefObject } from 'react';
import { Link } from 'react-router-dom';

import { api } from '../api/client';
import BoundingBox, { useMediaMetrics } from '../components/BoundingBox';
import {
  PRIORITY_ORDER,
  STATUS_LABEL,
  type PeopleResponse,
  type Person,
} from '../types';

export default function Results() {
  const [data, setData] = useState<PeopleResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [zoomed, setZoomed] = useState<Person | null>(null);

  const mediaRef = useRef<HTMLImageElement | HTMLVideoElement | null>(null);
  const { metrics, measure } = useMediaMetrics(mediaRef);

  useEffect(() => {
    api
      .get<PeopleResponse>('/people')
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, []);

  // Escape closes the zoom first, then clears the selection.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key !== 'Escape') return;
      if (zoomed) setZoomed(null);
      else setSelectedId(null);
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [zoomed]);

  const upload = data?.upload ?? null;
  const people: Person[] = data
    ? [...data.people].sort(
        (a, b) =>
          PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority] ||
          a.confidence - b.confidence,
      )
    : [];

  const selected = people.find((p) => p.id === selectedId) ?? null;
  const mediaUrl = upload ? `/api/upload/${upload.id}/file` : null;

  function select(person: Person, event: React.MouseEvent) {
    // Without this the click bubbles to the page handler that clears selection.
    event.stopPropagation();

    const next = person.id === selectedId ? null : person;
    setSelectedId(next?.id ?? null);
    if (!next) return;

    // A box only matches one frame, so jump the video there before drawing it.
    const el = mediaRef.current;
    if (el instanceof HTMLVideoElement && next.time_seconds !== null) {
      el.pause();
      el.currentTime = next.time_seconds;
    }
  }

  return (
    // Clicking anywhere that isn't a card clears the selection.
    <section onClick={() => setSelectedId(null)}>
      <h2>Detected people</h2>

      {error && <p className='error'>Could not load results: {error}</p>}
      {!data && !error && <p>Loading…</p>}

      {data && !upload && (
        <p className='muted'>
          Nothing analysed yet.{' '}
          <Link to='/capture'>Upload an image or video</Link> to get started.
        </p>
      )}

      {data?.verdict && upload && (
        <div className={`verdict verdict-${data.verdict.level}`}>
          <strong className='verdict-label'>{data.verdict.label}</strong>
          <span className='verdict-detail'>{data.verdict.detail}</span>
          <span className='verdict-counts muted'>
            {data.verdict.confident} confident · {data.verdict.rescued} confirmed
            on zoom · {data.verdict.unconfirmed} unconfirmed
            {data.verdict.max_confidence !== null &&
              ` · peak ${Math.round(data.verdict.max_confidence * 100)}%`}
          </span>
        </div>
      )}

      {upload && mediaUrl && (
        <>
          <figure className='stage'>
            <div className='stage-frame'>
              {upload.kind === 'video' ? (
                <video
                  ref={mediaRef as RefObject<HTMLVideoElement>}
                  src={mediaUrl}
                  controls
                  className='stage-media'
                  onLoadedMetadata={measure}
                />
              ) : (
                <img
                  ref={mediaRef as RefObject<HTMLImageElement>}
                  src={mediaUrl}
                  alt={upload.filename}
                  className='stage-media'
                  onLoad={measure}
                />
              )}

              {selected && metrics && (
                <BoundingBox person={selected} metrics={metrics} />
              )}
            </div>

            <figcaption className='muted'>
              {upload.filename} — {people.length}{' '}
              {people.length === 1 ? 'person' : 'people'} detected
              {selected && ' · click anywhere or press Esc to clear'}
            </figcaption>
          </figure>

          {people.length === 0 ? (
            <p className='muted'>No people found in this upload.</p>
          ) : (
            <div className='carousel' role='list'>
              {people.map((person) => (
                <button
                  type='button'
                  role='listitem'
                  key={person.id}
                  className={`card${selectedId === person.id ? ' is-selected' : ''}`}
                  onClick={(e) => select(person, e)}
                >
                  {person.crop_url ? (
                    <div className='card-thumb-wrap'>
                      <img
                        src={person.crop_url}
                        alt={`${person.label} at ${Math.round(person.confidence * 100)}% confidence`}
                        className='card-thumb'
                      />
                      <span
                        role='button'
                        tabIndex={0}
                        className='zoom-btn'
                        title='Zoom in'
                        onClick={(e) => {
                          e.stopPropagation();
                          setZoomed(person);
                        }}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.stopPropagation();
                            setZoomed(person);
                          }
                        }}
                      >
                        ⛶
                      </span>
                    </div>
                  ) : (
                    <div className='card-thumb card-thumb-empty'>no crop</div>
                  )}

                  <div className='card-body'>
                    <strong>{Math.round(person.confidence * 100)}%</strong>
                    <span className={`badge badge-${person.priority}`}>
                      {person.priority}
                    </span>
                  </div>

                  {person.status && (
                    <div className={`status status-${person.status}`}>
                      {STATUS_LABEL[person.status]}
                      {person.delta_pct !== null && (
                        <span className='status-delta'>
                          {person.delta_pct > 0 ? '+' : ''}
                          {person.delta_pct.toFixed(0)}%
                        </span>
                      )}
                    </div>
                  )}

                  <div className='card-meta muted'>
                    {person.label}
                    {person.track_id !== null && ` #${person.track_id}`}
                    {person.time_seconds !== null &&
                      ` · ${person.time_seconds.toFixed(1)}s`}
                  </div>
                </button>
              ))}
            </div>
          )}
        </>
      )}

      {zoomed && zoomed.crop_url && (
        <div
          className='lightbox'
          role='dialog'
          aria-modal='true'
          aria-label='Zoomed detection'
          onClick={() => setZoomed(null)}
        >
          <figure className='lightbox-inner' onClick={(e) => e.stopPropagation()}>
            <img
              src={zoomed.crop_url}
              alt={`${zoomed.label} enlarged`}
              className='lightbox-img'
            />
            <figcaption className='lightbox-meta'>
              <span>
                <strong>{Math.round(zoomed.confidence * 100)}%</strong> confidence
              </span>
              <span className={`badge badge-${zoomed.priority}`}>
                {zoomed.priority}
              </span>
              {zoomed.status && <span>{STATUS_LABEL[zoomed.status]}</span>}
              {zoomed.reeval_confidence !== null && (
                <span className='muted'>
                  re-scored {Math.round(zoomed.reeval_confidence * 100)}%
                  {zoomed.delta_pct !== null &&
                    ` (${zoomed.delta_pct > 0 ? '+' : ''}${zoomed.delta_pct.toFixed(0)}%)`}
                </span>
              )}
              {zoomed.time_seconds !== null && (
                <span className='muted'>at {zoomed.time_seconds.toFixed(1)}s</span>
              )}
            </figcaption>
            <button
              type='button'
              className='lightbox-close'
              onClick={() => setZoomed(null)}
            >
              Close
            </button>
          </figure>
        </div>
      )}
    </section>
  );
}
