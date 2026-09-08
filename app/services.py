from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, List, Optional

from app.schemas import BudgetState, JobResponse, JobStatus, TranscriptResponse, TranscriptSegment


@dataclass
class Job:
    job_id: str
    status: JobStatus
    language_hint: str
    is_medical_context: bool
    expected_speakers: int
    duration_sec: float
    estimated_cost_usd: float
    created_at: datetime
    updated_at: datetime
    language_detected: Optional[str] = None
    model_selected: Optional[str] = None
    actual_cost_usd: Optional[float] = None
    transcript: Optional[TranscriptResponse] = None


@dataclass
class Usage:
    month: str
    cost_usd: float = 0.0
    minutes_processed: float = 0.0


class TranscriptionService:
    """In-memory MVP service layer.

    Replace this with PostgreSQL + object storage in production.
    """

    STANDARD_RATE = 0.016
    MEDICAL_RATE = 0.078
    SOFT_LIMIT_RATIO = 0.9

    def __init__(self, monthly_budget_usd: float = 50.0) -> None:
        self.jobs: Dict[str, Job] = {}
        self.monthly_budget_usd = monthly_budget_usd
        self.usage = Usage(month=self._current_month())
        self._lock = Lock()

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _current_month(self) -> str:
        return self._now().strftime("%Y-%m")

    def _reset_usage_if_new_month(self) -> None:
        current_month = self._current_month()
        if self.usage.month != current_month:
            self.usage = Usage(month=current_month)

    def estimate_cost(self, duration_sec: float, model: str) -> float:
        minutes = duration_sec / 60
        rate = self.MEDICAL_RATE if model == "medical_conversation" else self.STANDARD_RATE
        return round(minutes * rate, 4)

    def can_process(self, estimated_cost: float) -> BudgetState:
        self._reset_usage_if_new_month()
        projected = self.usage.cost_usd + estimated_cost
        if projected > self.monthly_budget_usd:
            return BudgetState.block
        if projected > (self.monthly_budget_usd * self.SOFT_LIMIT_RATIO):
            return BudgetState.warn
        return BudgetState.allow

    def choose_model(self, language: str, is_medical_context: bool) -> str:
        if language == "en-US" and is_medical_context:
            return "medical_conversation"
        return "chirp_3"

    def create_job(
        self,
        language_hint: str,
        is_medical_context: bool,
        expected_speakers: int,
        duration_sec: float,
    ) -> Job:
        with self._lock:
            model = self.choose_model(language_hint, is_medical_context)
            estimated = self.estimate_cost(duration_sec, model)
            budget_state = self.can_process(estimated)

            now = self._now()
            job_id = f"job_{uuid.uuid4().hex[:12]}"
            status = JobStatus.queued if budget_state != BudgetState.block else JobStatus.blocked_budget
            job = Job(
                job_id=job_id,
                status=status,
                language_hint=language_hint,
                is_medical_context=is_medical_context,
                expected_speakers=expected_speakers,
                duration_sec=duration_sec,
                estimated_cost_usd=estimated,
                created_at=now,
                updated_at=now,
                model_selected=model,
            )
            self.jobs[job_id] = job
            return job

    def get_job(self, job_id: str) -> Optional[Job]:
        return self.jobs.get(job_id)

    def process_job(self, job_id: str) -> Optional[Job]:
        with self._lock:
            job = self.get_job(job_id)
            if not job or job.status == JobStatus.blocked_budget:
                return job

            self._reset_usage_if_new_month()
            pending_cost_usd = job.actual_cost_usd if job.actual_cost_usd is not None else job.estimated_cost_usd
            if self.usage.cost_usd + pending_cost_usd > self.monthly_budget_usd:
                job.status = JobStatus.blocked_budget
                job.updated_at = self._now()
                return job

            job.status = JobStatus.processing
            job.updated_at = self._now()

            language_detected = "fr-FR" if job.language_hint == "fr-FR" else "en-US"
            segments: List[TranscriptSegment] = [
                TranscriptSegment(
                    segment_id="s1",
                    speaker="spk_1",
                    start_sec=0.8,
                    end_sec=4.9,
                    text="Bonjour, on commence la consultation.",
                    confidence=0.93,
                ),
                TranscriptSegment(
                    segment_id="s2",
                    speaker="spk_2",
                    start_sec=5.0,
                    end_sec=9.8,
                    text="Merci docteur, j'ai une douleur persistante.",
                    confidence=0.89,
                ),
            ] if language_detected == "fr-FR" else [
                TranscriptSegment(
                    segment_id="s1",
                    speaker="spk_1",
                    start_sec=0.9,
                    end_sec=5.4,
                    text="Hello, let's start the consultation.",
                    confidence=0.92,
                ),
                TranscriptSegment(
                    segment_id="s2",
                    speaker="spk_2",
                    start_sec=5.5,
                    end_sec=10.7,
                    text="Thanks doctor, I have persistent pain.",
                    confidence=0.88,
                ),
            ]

            full_text = " ".join(segment.text for segment in segments)
            avg_conf = round(sum(segment.confidence for segment in segments) / len(segments), 3)

            job.language_detected = language_detected
            job.actual_cost_usd = job.estimated_cost_usd
            job.transcript = TranscriptResponse(
                job_id=job.job_id,
                language_detected=language_detected,
                model_used=job.model_selected or "chirp_3",
                duration_sec=job.duration_sec,
                avg_confidence=avg_conf,
                full_text=full_text,
                segments=segments,
            )
            job.status = JobStatus.completed
            job.updated_at = self._now()

            self.usage.cost_usd = round(self.usage.cost_usd + (job.actual_cost_usd or 0), 4)
            self.usage.minutes_processed = round(self.usage.minutes_processed + (job.duration_sec / 60), 3)
            return job

    def as_job_response(self, job: Job) -> JobResponse:
        return JobResponse(
            job_id=job.job_id,
            status=job.status,
            language_hint=job.language_hint,
            language_detected=job.language_detected,
            model_selected=job.model_selected,
            estimated_cost_usd=job.estimated_cost_usd,
            actual_cost_usd=job.actual_cost_usd,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )


service = TranscriptionService(monthly_budget_usd=50.0)
