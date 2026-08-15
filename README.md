# VITA

Detecting a person in thermal imagery is a solved research problem — VITA's novelty is turning that detection into an operational triage signal, with confidence-based guidance and persistent tracking across video, rather than stopping at a bounding box. It's not a new detection method; it's the decision-support layer the underlying research (POP, published Feb 2025) never built.

## Problem

## Approach

```
input ──▶ detector ──▶ confidence gate ──┬── ≥ threshold ──▶ auto-resolved
          (YOLO)                         │
                                         └── < threshold ──▶ re-evaluate crop
                                                                   │
                                              ┌────────────────────┴──────────────┐
                                              │                                   │
                                       jump > 20% ──▶ flagged            no jump ──▶ not confirmed
                                              │
                                              └──▶ review queue ──▶ human ──▶ resolved
```

## Demo

| | |
| --- | --- |
| 🎥 **[Demo video](VITAdemo_vid.mp4)** | VITA running end to end — upload, detection, review queue (18 MB) |
| 📊 **[Slide deck](vita_slide.pptx)** | Project overview and approach (62 KB) |

> GitHub will not play an `.mp4` inline from a repo file link — the link
> downloads it. To get an embedded player, drag the file into a GitHub issue
> or release and use the `user-images.githubusercontent.com` URL it returns.

## Setup

Two things the repo does **not** contain, because both are gitignored — set
them up after cloning or the backend will not start:

| What                     | Why it's missing | What to do                                                       |
| ------------------------ | ---------------- | ---------------------------------------------------------------- |
| `backend/.env`           | may hold secrets | `cp backend/.env.example backend/.env`                           |
| `backend/models/best.pt` | 6 MB binary      | drop your trained weights in, or point `YOLO_MODEL_PATH` at them |

### Prerequisites

- Python 3.11+
- Node 20+
- A trained YOLO `.pt` model

> A `.pt` file is a zip archive internally. If your file manager helpfully
> "extracts" it, you get a **directory** named `best.pt` and the backend will
> report it as unusable. Keep the original file.

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then set YOLO_MODEL_PATH if needed
python run.py                 # http://127.0.0.1:5000
```

Torch installs the CUDA build by default (~3 GB). On a CPU-only machine:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

The dev server proxies `/api` to the backend, so run both and use the Vite
URL only.

### Check it works

```bash
curl localhost:5000/api/health
```

`model_available: true` means the weights were found and loaded.

## Configuration

All backend settings live in `backend/.env` (see `.env.example`).

| Variable                | Default                     | What it does                                          |
| ----------------------- | --------------------------- | ----------------------------------------------------- |
| `YOLO_MODEL_PATH`       | `models/best.pt`            | Path to your weights                                  |
| `YOLO_DEVICE`           | `cpu`                       | `cpu`, `0` for CUDA, `mps` on Apple silicon           |
| `YOLO_CLASSES`          | `person`                    | Class names to keep; blank keeps all                  |
| `YOLO_MIN_CONFIDENCE`   | `0.25`                      | Detections below this are discarded outright          |
| `CONFIDENCE_THRESHOLD`  | `0.85`                      | At or above, trusted; below, a human reviews          |
| `REEVAL_CONF_THRESHOLD` | `0.5`                       | Above this, flagged without re-evaluation             |
| `REEVAL_DELTA_PCT`      | `20`                        | Confidence jump needed to rescue a detection          |
| `REEVAL_DELTA_MODE`     | `relative`                  | `relative` (% change) or `points` (percentage points) |
| `VIDEO_FRAME_STRIDE`    | `15`                        | Analyse every Nth video frame                         |
| `TRACKER_CONFIG`        | `app/trackers/lowconf.yaml` | Tracker tuned to keep low-confidence people           |
| `MAX_UPLOAD_MB`         | `200`                       | Upload size cap                                       |

Two thresholds do different jobs and are deliberately separate:
`CONFIDENCE_THRESHOLD` sets review **priority**, `REEVAL_CONF_THRESHOLD` decides
whether a detection is **re-evaluated** at all.

## API

| Method | Path                            | Purpose                                                              |
| ------ | ------------------------------- | -------------------------------------------------------------------- |
| `POST` | `/api/upload`                   | Upload an image or video; runs detection and returns people          |
| `GET`  | `/api/people`                   | Detections from the latest upload (`?upload_id=` for a specific one) |
| `GET`  | `/api/upload/<id>/file`         | The uploaded media (range requests supported)                        |
| `GET`  | `/api/upload/<id>/crops/<file>` | One detection thumbnail                                              |
| `GET`  | `/api/upload/limits`            | Accepted file types and size cap                                     |
| `GET`  | `/api/health`                   | Model path, device, and whether the weights loaded                   |
