from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse

from app.schemas import RenderJobView, RenderRequest

router = APIRouter()


@router.get("/health")
def healthcheck(request: Request) -> dict[str, str | bool]:
    settings = request.app.state.settings
    return {
        "status": "ok",
        "use_ollama": settings.use_ollama,
        "default_visual_backend": settings.default_visual_backend,
    }


@router.get("/renders", response_model=list[RenderJobView])
def list_renders(request: Request, limit: int = 20) -> list[RenderJobView]:
    orchestrator = request.app.state.orchestrator
    settings = request.app.state.settings
    return [
        RenderJobView.from_job(job, settings.api_prefix)
        for job in orchestrator.list_jobs(limit=limit)
    ]


@router.post(
    "/renders",
    response_model=RenderJobView,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_render(render_request: RenderRequest, request: Request) -> RenderJobView:
    orchestrator = request.app.state.orchestrator
    settings = request.app.state.settings
    job = orchestrator.queue(render_request)
    return RenderJobView.from_job(job, settings.api_prefix)


@router.get("/renders/{job_id}", response_model=RenderJobView)
def get_render(job_id: str, request: Request) -> RenderJobView:
    orchestrator = request.app.state.orchestrator
    settings = request.app.state.settings
    try:
        job = orchestrator.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RenderJobView.from_job(job, settings.api_prefix)


@router.get("/renders/{job_id}/download")
def download_render(job_id: str, request: Request) -> FileResponse:
    orchestrator = request.app.state.orchestrator
    try:
        job = orchestrator.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not job.output_video_path:
        raise HTTPException(status_code=409, detail="Video ainda nao foi gerado")
    return FileResponse(
        path=job.output_video_path,
        media_type="video/mp4",
        filename=f"{job.job_id}.mp4",
    )
