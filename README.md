# Medical Transcription MVP (FR/EN, post-call)

A starter backend for a Plaud-like transcription app focused on **post-call uploads**, **French/English transcription**, **speaker diarization**, and **budget-aware processing**.

## What is implemented

- FastAPI backend with core endpoints:
  - `POST /v1/uploads`
  - `POST /v1/jobs/{job_id}/process`
  - `GET /v1/jobs/{job_id}`
  - `GET /v1/transcripts/{job_id}`
  - `POST /v1/transcripts/{job_id}/export`
  - `GET /v1/usage`
- Model routing logic:
  - `en-US + medical_context=true` -> `medical_conversation`
  - all others -> `chirp_3`
- Monthly budget guard with cap set to `$50`.
- In-memory storage layer (MVP scaffold) to be replaced by PostgreSQL + cloud storage.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open docs at: `http://127.0.0.1:8000/docs`

## Example flow

1. Upload audio (form-data):

```bash
curl -X POST http://127.0.0.1:8000/v1/uploads \
  -F "file=@sample.wav" \
  -F "language_hint=fr-FR" \
  -F "is_medical_context=true" \
  -F "expected_speakers=2" \
  -F "duration_sec=600"
```

2. Process job:

```bash
curl -X POST http://127.0.0.1:8000/v1/jobs/<job_id>/process
```

3. Get transcript:

```bash
curl http://127.0.0.1:8000/v1/transcripts/<job_id>
```

## Production TODOs

- Replace in-memory service with PostgreSQL + background worker + object storage.
- Integrate Google Cloud Speech-to-Text V2.
- Add authenticated users and audit logs.
- Add data retention and hard delete workflows for HIPAA operations.
