from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class RenderRequest(BaseModel):
    prompt: str = Field(min_length=12, max_length=8000)
    duration_minutes: int = Field(default=5, ge=1, le=15)
    target_age: str = Field(default="5-8")
    lesson_name: str | None = Field(default=None, max_length=120)
    lesson_number: int = Field(default=1, ge=1, le=999)
    step_number: int = Field(default=1, ge=1, le=999)
    planner_mode: Literal["auto", "local"] = "auto"
    visual_backend: Literal["template", "cogvideox"] | None = None
    narration_style: Literal["natural", "animated"] = "natural"
    include_subtitles: bool = True

    @field_validator("prompt")
    @classmethod
    def normalize_prompt(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("lesson_name")
    @classmethod
    def normalize_lesson_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None


class NarrationSegment(BaseModel):
    language: Literal["pt-BR", "en-US"]
    speaker: Literal["teacher", "student"] = "teacher"
    text: str = Field(min_length=1, max_length=500)


class LessonScene(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scene_id: str
    title: str
    duration_seconds: int = Field(ge=10, le=120)
    teaching_mode: Literal["intro", "vocabulary", "dialogue", "game", "review", "story", "movement"] = "vocabulary"
    visual_prompt: str
    narration: list[NarrationSegment]
    on_screen_text: list[str] = Field(default_factory=list)
    vocabulary: list[str] = Field(default_factory=list)
    card_details: list[str] = Field(default_factory=list)
    background_palette: list[str] = Field(default_factory=list)


class LessonPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    summary: str
    audience: str = "children"
    target_age: str = "5-8"
    duration_minutes: int = Field(ge=1, le=15)
    style: str
    learning_objectives: list[str] = Field(default_factory=list)
    vocabulary: list[str] = Field(default_factory=list)
    scenes: list[LessonScene] = Field(min_length=1)


class RenderJob(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    job_id: str
    status: JobStatus
    request: RenderRequest
    plan: LessonPlan | None = None
    output_video_path: str | None = None
    preview_image_path: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RenderJobView(BaseModel):
    job_id: str
    status: JobStatus
    request: RenderRequest
    plan: LessonPlan | None = None
    output_video_path: str | None = None
    preview_image_path: str | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    download_url: str | None = None

    @classmethod
    def from_job(cls, job: RenderJob, api_prefix: str) -> "RenderJobView":
        download_url = None
        if job.output_video_path:
            download_url = f"{api_prefix}/renders/{job.job_id}/download"
        return cls(
            **job.model_dump(),
            download_url=download_url,
        )
