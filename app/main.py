from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.api import router
from app.config import get_settings
from app.job_store import JobStore
from app.orchestrator import RenderOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

settings = get_settings()
job_store = JobStore(settings)
orchestrator = RenderOrchestrator(settings, job_store)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="API para criar videos infantis bilingues com prompt, narracao e render local.",
)
app.state.settings = settings
app.state.orchestrator = orchestrator
app.include_router(router, prefix=settings.api_prefix)


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(settings.web_dir / "index.html")
