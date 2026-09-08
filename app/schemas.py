from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    blocked_budget = "blocked_budget"


class UploadResponse(BaseModel):
    job_id: str
    status: JobStatus
    estimated_cost_usd: float


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    language_hint: str
    language_detected: Optional[str] = None
    model_selected: Optional[str] = None
    estimated_cost_usd: float
    actual_cost_usd: Optional[float] = None
    created_at: datetime
    updated_at: datetime


class TranscriptSegment(BaseModel):
    segment_id: str
    speaker: str
    start_sec: float
    end_sec: float
    text: str
    confidence: float = Field(ge=0, le=1)


class TranscriptResponse(BaseModel):
    job_id: str
    language_detected: str
    model_used: str
    duration_sec: float
    avg_confidence: float
    full_text: str
    segments: List[TranscriptSegment]


class ExportRequest(BaseModel):
    format: str = Field(pattern="^(txt|json)$")


class BudgetState(str, Enum):
    allow = "allow"
    warn = "warn"
    block = "block"
