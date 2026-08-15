import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { api } from '../api/client';
import { PRIORITY_ORDER, type PeopleResponse, type Person } from '../types';

export default function Results() {
  const [data, setData] = useState<PeopleResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<PeopleResponse>('/people')
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, []);

  const sorted: Person[] | null = data
    ? [...data.people].sort(
        (a, b) =>
          PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority] ||
          a.confidence - b.confidence,
      )
    : null;

  return (
    <section>
      <h2>Detected people</h2>

      {data?.upload && (
        <p className='muted'>
          From {data.upload.filename} ({data.upload.kind})
        </p>
      )}

      {error && <p className='error'>Could not load results: {error}</p>}

      {!sorted && !error && <p>Loading…</p>}

      {sorted && sorted.length === 0 && (
        <p className='muted'>
          Nothing here yet. <Link to='/capture'>Upload an image or video</Link> to
          get started.
        </p>
      )}

      {sorted && sorted.length > 0 && (
        <table className='results'>
          <thead>
            <tr>
              <th>Person</th>
              <th>Priority</th>
              <th>Confidence</th>
              <th>Frame</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((person) => (
              <tr key={person.id}>
                <td>
                  {person.label}
                  {person.track_id !== null && (
                    <span className='muted'> #{person.track_id}</span>
                  )}
                </td>
                <td>
                  <span className={`badge badge-${person.priority}`}>
                    {person.priority}
                  </span>
                </td>
                <td>{Math.round(person.confidence * 100)}%</td>
                <td className='muted'>{person.frame ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
