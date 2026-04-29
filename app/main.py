from __future__ import annotations

import json

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse

from app.schemas import ExportRequest, JobStatus, UploadResponse
from app.services import service

app = FastAPI(title="Medical Transcription MVP", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/v1/uploads", response_model=UploadResponse)
async def create_upload(
    file: UploadFile = File(...),
    language_hint: str = Form("auto"),
    is_medical_context: bool = Form(True),
    expected_speakers: int = Form(2),
    duration_sec: float = Form(600.0),
) -> UploadResponse:
    if language_hint not in {"auto", "en-US", "fr-FR"}:
        raise HTTPException(status_code=400, detail="language_hint must be auto, en-US, or fr-FR")
    if expected_speakers < 1 or expected_speakers > 6:
        raise HTTPException(status_code=400, detail="expected_speakers must be between 1 and 6")

    # MVP note: this validates file presence but does not persist bytes yet.
    _ = await file.read(16)

    job = service.create_job(
        language_hint=language_hint,
        is_medical_context=is_medical_context,
        expected_speakers=expected_speakers,
        duration_sec=duration_sec,
    )
    return UploadResponse(job_id=job.job_id, status=job.status, estimated_cost_usd=job.estimated_cost_usd)


@app.post("/v1/jobs/{job_id}/process")
def process_job(job_id: str) -> dict:
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    if job.status == JobStatus.blocked_budget:
        raise HTTPException(status_code=402, detail="job blocked due to monthly budget cap")

    processed = service.process_job(job_id)
    if not processed:
        raise HTTPException(status_code=500, detail="failed to process job")
    return {"job_id": processed.job_id, "status": processed.status}


@app.get("/v1/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return service.as_job_response(job).model_dump()


@app.get("/v1/transcripts/{job_id}")
def get_transcript(job_id: str) -> dict:
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    if job.status != JobStatus.completed or not job.transcript:
        raise HTTPException(status_code=409, detail="transcript not ready")
    return job.transcript.model_dump()


@app.post("/v1/transcripts/{job_id}/export")
def export_transcript(job_id: str, request: ExportRequest):
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    if job.status != JobStatus.completed or not job.transcript:
        raise HTTPException(status_code=409, detail="transcript not ready")

    if request.format == "json":
        return job.transcript.model_dump()

    txt_body = "\n".join(
        f"[{s.start_sec:.2f}-{s.end_sec:.2f}] {s.speaker}: {s.text}"
        for s in job.transcript.segments
    )
    return PlainTextResponse(txt_body, media_type="text/plain")


@app.get("/v1/usage")
def get_usage() -> dict:
    return {
        "month": service.usage.month,
        "minutes_processed": service.usage.minutes_processed,
        "cost_usd": service.usage.cost_usd,
        "budget_cap_usd": service.monthly_budget_usd,
        "budget_remaining_usd": round(service.monthly_budget_usd - service.usage.cost_usd, 4),
    }
