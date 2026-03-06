from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.config import Settings
from app.schemas import LessonScene


class CogVideoXAnimator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._pipe = None

    def animate_scene(self, scene: LessonScene, image_path: Path, output_path: Path) -> Path:
        try:
            import torch
            from diffusers import CogVideoXImageToVideoPipeline
            from diffusers.utils import export_to_video
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Backend CogVideoX requer a extra [video-ai].") from exc

        if self._pipe is None:
            self._pipe = CogVideoXImageToVideoPipeline.from_pretrained(
                self.settings.cogvideox_model_id,
                torch_dtype=torch.float16,
            )
            self._pipe.enable_model_cpu_offload()

        source_image = Image.open(image_path).convert("RGB")
        frame_count = max(16, min(49, int(scene.duration_seconds * 8)))
        result = self._pipe(
            prompt=scene.visual_prompt,
            image=source_image,
            num_frames=frame_count,
            num_inference_steps=self.settings.cogvideox_num_inference_steps,
        )
        export_to_video(result.frames[0], output_path, fps=8)
        return output_path
