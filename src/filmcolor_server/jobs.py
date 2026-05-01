from __future__ import annotations

from itertools import count

from filmcolor_core.models import JobRecord, JobStatus


class JobRegistry:
    def __init__(self) -> None:
        self._counter = count(1)
        self._jobs: dict[str, JobRecord] = {}

    def create(self, kind: str, message: str = "") -> JobRecord:
        job_id = f"job-{next(self._counter):06d}"
        job = JobRecord(id=job_id, kind=kind, status=JobStatus.QUEUED, message=message)
        self._jobs[job_id] = job
        return job

    def set_running(self, job_id: str, message: str = "") -> JobRecord:
        job = self._jobs[job_id]
        job.status = JobStatus.RUNNING
        job.message = message
        return job

    def set_succeeded(self, job_id: str, message: str = "", progress: float = 1.0) -> JobRecord:
        job = self._jobs[job_id]
        job.status = JobStatus.SUCCEEDED
        job.message = message
        job.progress = progress
        return job

    def set_failed(self, job_id: str, message: str) -> JobRecord:
        job = self._jobs[job_id]
        job.status = JobStatus.FAILED
        job.message = message
        return job

    def get(self, job_id: str) -> JobRecord:
        return self._jobs[job_id]
