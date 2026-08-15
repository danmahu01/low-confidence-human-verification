export interface Health {
  status: string;
  model_path: string;
  model_available: boolean;
  device: string;
  classes: string[];
  threshold: number;
}

export type Priority = 'high' | 'medium' | 'low';

/** Sort key — lower number sorts first. */
export const PRIORITY_ORDER: Record<Priority, number> = {
  high: 0,
  medium: 1,
  low: 2,
};

/** One YOLO detection. */
export interface Person {
  id: string;
  /** Class name from the model, e.g. "person". */
  label: string;
  /** 0–1, straight from the model. */
  confidence: number;
  priority: Priority;
  /** [x1, y1, x2, y2] in pixels. */
  bbox: [number, number, number, number];
  /** Video only — which sampled frame this came from. */
  frame: number | null;
  /** Video only — stable id for one person across frames. */
  track_id: number | null;
}

/** Returned by POST /api/upload. */
export interface StoredUpload {
  id: string;
  filename: string;
  stored_name: string;
  kind: 'video' | 'image';
  content_type: string | null;
  size_bytes: number;
}

export interface UploadResponse {
  upload: StoredUpload;
  people: Person[];
}

export interface PeopleResponse {
  people: Person[];
  upload: StoredUpload | null;
}
