import { useEffect, useRef, useState, type RefObject } from 'react';
import { Link } from 'react-router-dom';

import { api } from '../api/client';
import BoundingBox, { useMediaMetrics } from '../components/BoundingBox';
import { PRIORITY_ORDER, type PeopleResponse, type Person } from '../types';

export default function Results() {
  const [data, setData] = useState<PeopleResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const mediaRef = useRef<HTMLImageElement | HTMLVideoElement | null>(null);
  const { metrics, measure } = useMediaMetrics(mediaRef);

  useEffect(() => {
    api
      .get<PeopleResponse>('/people')
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, []);

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

  function select(person: Person) {
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
    <section>
      <h2>Detected people</h2>

      {error && <p className='error'>Could not load results: {error}</p>}
      {!data && !error && <p>Loading…</p>}

      {data && !upload && (
        <p className='muted'>
          Nothing analysed yet.{' '}
          <Link to='/capture'>Upload an image or video</Link> to get started.
        </p>
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
              {selected && ' · click the card again to clear the box'}
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
                  onClick={() => select(person)}
                >
                  {person.crop_url ? (
                    <img
                      src={person.crop_url}
                      alt={`${person.label} at ${Math.round(person.confidence * 100)}% confidence`}
                      className='card-thumb'
                    />
                  ) : (
                    <div className='card-thumb card-thumb-empty'>no crop</div>
                  )}

                  <div className='card-body'>
                    <strong>{Math.round(person.confidence * 100)}%</strong>
                    <span className={`badge badge-${person.priority}`}>
                      {person.priority}
                    </span>
                  </div>

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
    </section>
  );
}
