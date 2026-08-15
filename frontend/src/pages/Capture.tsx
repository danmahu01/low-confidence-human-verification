import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { api } from '../api/client';
import type { UploadResponse } from '../types';

type Kind = 'image' | 'video';

function kindOf(file: File): Kind | null {
  if (file.type.startsWith('video/')) return 'video';
  if (file.type.startsWith('image/')) return 'image';
  return null;
}

export default function Capture() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [kind, setKind] = useState<Kind | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Object URLs leak if we don't revoke them when the file changes.
  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  function selectFile(next: File | null) {
    setError(null);
    if (!next) {
      setFile(null);
      setKind(null);
      return;
    }
    const detected = kindOf(next);
    if (!detected) {
      setError('That file is not an image or a video.');
      return;
    }
    setFile(next);
    setKind(detected);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;

    setUploading(true);
    setError(null);
    try {
      const body = new FormData();
      body.append('file', file);
      await api.upload<UploadResponse>('/upload', body);
      navigate('/result');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed.');
    } finally {
      setUploading(false);
    }
  }

  return (
    <section>
      <h2>Upload footage</h2>
      <p className='muted'>
        Upload an image or a video. People detected in it are scored, and
        anything the model is unsure about goes to the review queue.
      </p>

      <form onSubmit={handleSubmit}>
        <div
          className={`dropzone${dragging ? ' is-dragging' : ''}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            selectFile(e.dataTransfer.files[0] ?? null);
          }}
        >
          {previewUrl && kind === 'video' && (
            <video src={previewUrl} className='preview' controls />
          )}
          {previewUrl && kind === 'image' && (
            <img src={previewUrl} alt='Selected upload' className='preview' />
          )}
          {!previewUrl && <p>Drop an image or video here, or click to choose one</p>}
        </div>

        <input
          ref={inputRef}
          type='file'
          accept='image/*,video/*'
          hidden
          onChange={(e) => selectFile(e.target.files?.[0] ?? null)}
        />

        {file && (
          <p className='muted'>
            {file.name} — {(file.size / 1024 / 1024).toFixed(1)} MB{' '}
            <button type='button' className='link' onClick={() => selectFile(null)}>
              remove
            </button>
          </p>
        )}

        {error && <p className='error'>{error}</p>}

        <button type='submit' disabled={!file || uploading}>
          {uploading ? 'Uploading…' : 'Upload'}
        </button>
      </form>
    </section>
  );
}
