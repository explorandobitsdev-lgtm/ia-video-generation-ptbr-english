from __future__ import annotations

import logging
import traceback
from threading import Thread

from app.config import Settings
from app.job_store import JobStore
from app.planner import LessonPlanner
from app.script_writer import ScriptWriter
from app.schemas import JobStatus, RenderJob, RenderRequest
from app.video import VideoComposer

logger = logging.getLogger(__name__)


class RenderOrchestrator:
    def __init__(self, settings: Settings, job_store: JobStore) -> None:
        self.settings = settings
        self.job_store = job_store
        self.planner = LessonPlanner(settings)
        self.script_writer = ScriptWriter()
        self.video_composer = VideoComposer(settings)

    def queue(self, request: RenderRequest) -> RenderJob:
        if request.visual_backend is None:
            request = request.model_copy(update={"visual_backend": self.settings.default_visual_backend})
        job = self.job_store.create(request)
        thread = Thread(target=self._run_job, args=(job.job_id,), daemon=True)
        thread.start()
        return job

    def get(self, job_id: str) -> RenderJob:
        return self.job_store.load(job_id)

    def list_jobs(self, limit: int = 20) -> list[RenderJob]:
        return self.job_store.list_jobs(limit=limit)

    def run_sync(self, request: RenderRequest) -> RenderJob:
        if request.visual_backend is None:
            request = request.model_copy(update={"visual_backend": self.settings.default_visual_backend})
        job = self.job_store.create(request)
        self._run_job(job.job_id)
        return self.job_store.load(job.job_id)

    def _run_job(self, job_id: str) -> None:
        job = self.job_store.load(job_id)
        job.status = JobStatus.running
        self.job_store.save(job)
        workdir = self.settings.outputs_dir / job_id
        workdir.mkdir(parents=True, exist_ok=True)

        try:
            plan = self.planner.generate(job.request)
            plan, _script_blocks = self.script_writer.prepare(plan, job.request)
            artifacts = self.video_composer.render(plan, job.request, workdir)
            (workdir / "lesson-plan.json").write_text(
                plan.model_dump_json(indent=2),
                encoding="utf-8",
            )
            job.plan = plan
            job.output_video_path = str(artifacts.video_path)
            job.preview_image_path = str(artifacts.preview_image_path)
            job.status = JobStatus.completed
            self.job_store.save(job)
        except Exception as exc:
            logger.exception("Render job failed: %s", job_id)
            job.status = JobStatus.failed
            job.error = f"{exc}\n\n{traceback.format_exc(limit=5)}"
            self.job_store.save(job)
