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

/** Verdicts from confidence_loop.tag_detections. */
export type TagStatus =
  | 'flagged_high_confidence'
  | 'flagged_reeval_jump'
  | 'not_confirmed';

export const STATUS_LABEL: Record<TagStatus, string> = {
  flagged_high_confidence: 'confident',
  flagged_reeval_jump: 'confirmed on zoom',
  not_confirmed: 'unconfirmed',
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
  /** Thumbnail cropped from the frame this detection came from. */
  crop_url: string | null;
  /** Video only — position in the clip, for seeking to this detection. */
  time_seconds: number | null;
  /** Verdict from the confidence re-evaluation loop. */
  status: TagStatus | null;
  /** Confidence after re-scoring the crop; null if it was never re-evaluated. */
  reeval_confidence: number | null;
  /** Percent change from original to re-evaluated confidence. */
  delta_pct: number | null;
  /** Validation only — whether this prediction matched a ground-truth box. */
  matched?: boolean | null;
  /** Validation only — IoU with the box it matched. */
  iou?: number | null;
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
  verdict: Verdict;
}

/** Overall answer for one upload. */
export type VerdictLevel = 'high' | 'possible' | 'unlikely' | 'none';

export interface Verdict {
  level: VerdictLevel;
  /** e.g. "High probability of human presence" */
  label: string;
  detail: string;
  total: number;
  confident: number;
  rescued: number;
  unconfirmed: number;
  max_confidence: number | null;
}

export interface PeopleResponse {
  people: Person[];
  upload: StoredUpload | null;
  verdict: Verdict | null;
}

/** One box from the ground-truth label file. */
export interface GroundTruthBox {
  id: string;
  class_id: number;
  label: string;
  bbox: [number, number, number, number];
  /** True if some prediction matched it; false means the model missed it. */
  matched: boolean;
}

export interface ValidationMetrics {
  true_positives: number;
  false_positives: number;
  false_negatives: number;
  precision: number;
  recall: number;
  f1: number;
  iou_threshold: number;
}

export interface ValidationResponse {
  upload: StoredUpload;
  metrics: ValidationMetrics;
  predictions: Person[];
  ground_truth: GroundTruthBox[];
}
