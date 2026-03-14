from functools import lru_cache
from pathlib import Path
import shutil
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Kids Bilingual Video Studio"
    api_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = 8000

    data_dir: Path = Path("data")
    jobs_dir: Path = Path("data/jobs")
    outputs_dir: Path = Path("data/outputs")
    tmp_dir: Path = Path("data/tmp")
    piper_download_dir: Path = Path("data/piper")
    web_dir: Path = Path("app/web")

    use_ollama: bool = True
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2"
    ollama_timeout_seconds: int = 240

    piper_command: str = "piper"
    piper_pt_teacher_voice: str = "pt_BR-faber-medium"
    piper_pt_student_voice: str = "pt_BR-cadu-medium"
    piper_en_teacher_voice: str = "en_US-lessac-high"
    piper_en_student_voice: str = "en_US-lessac-medium"
    narration_gap_ms: int = 210
    dialogue_gap_ms: int = 150
    intra_sentence_gap_ms: int = 110
    sentence_gap_ms: int = 255
    tts_pt_length_scale: float = 1.10
    tts_en_length_scale: float = 1.16
    tts_pt_noise_scale: float = 0.82
    tts_en_noise_scale: float = 0.74
    tts_noise_w_scale: float = 0.92

    ffmpeg_command: str = "ffmpeg"
    ffprobe_command: str = "ffprobe"
    video_width: int = 1920
    video_height: int = 1080
    video_fps: int = 30

    default_visual_backend: Literal["template", "cogvideox"] = "template"
    video_ai_enabled: bool = False
    cogvideox_model_id: str = "THUDM/CogVideoX-2b"
    cogvideox_num_inference_steps: int = 35

    def ensure_directories(self) -> None:
        for path in (
            self.data_dir,
            self.jobs_dir,
            self.outputs_dir,
            self.tmp_dir,
            self.piper_download_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def resolve_ffmpeg_command(self) -> str:
        local_ffmpeg = shutil.which(self.ffmpeg_command)
        if local_ffmpeg:
            return local_ffmpeg

        try:
            import imageio_ffmpeg

            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                f"'{self.ffmpeg_command}' nao foi encontrado e o fallback imageio-ffmpeg falhou."
            ) from exc


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
