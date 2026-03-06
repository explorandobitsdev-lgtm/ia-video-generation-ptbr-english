import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from app.config import Settings
from app.schemas import JobStatus, RenderJob, RenderRequest


class JobStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = Lock()
        self.settings.ensure_directories()

    def create(self, request: RenderRequest) -> RenderJob:
        job_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "-" + secrets.token_hex(4)
        job = RenderJob(job_id=job_id, status=JobStatus.queued, request=request)
        self.save(job)
        return job

    def save(self, job: RenderJob) -> RenderJob:
        job.updated_at = datetime.now(timezone.utc)
        payload = job.model_dump(mode="json")
        with self._lock:
            self._job_path(job.job_id).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return job

    def load(self, job_id: str) -> RenderJob:
        path = self._job_path(job_id)
        if not path.exists():
            raise KeyError(f"Job {job_id} not found")
        return RenderJob.model_validate_json(path.read_text(encoding="utf-8"))

    def list_jobs(self, limit: int = 20) -> list[RenderJob]:
        jobs: list[RenderJob] = []
        for path in sorted(self.settings.jobs_dir.glob("*.json"), reverse=True):
            jobs.append(RenderJob.model_validate_json(path.read_text(encoding="utf-8")))
            if len(jobs) >= limit:
                break
        return jobs

    def _job_path(self, job_id: str) -> Path:
        return self.settings.jobs_dir / f"{job_id}.json"
