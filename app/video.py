from __future__ import annotations

import logging
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.narration import NarrationCue, NarrationService, NarrationSubtitle
from app.schemas import LessonPlan, LessonScene, RenderRequest
from app.utils import slugify
from app.video_ai import CogVideoXAnimator
from app.visuals import TemplateVisualRenderer

logger = logging.getLogger(__name__)


@dataclass
class RenderArtifacts:
    video_path: Path
    preview_image_path: Path


class VideoComposer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.visual_renderer = TemplateVisualRenderer(settings)
        self.video_animator = CogVideoXAnimator(settings)
        self.narration = NarrationService(settings)

    def render(self, plan: LessonPlan, request: RenderRequest, workdir: Path) -> RenderArtifacts:
        ffmpeg_command = self.settings.resolve_ffmpeg_command()
        requested_backend = request.visual_backend or self.settings.default_visual_backend
        visual_backend = requested_backend
        if requested_backend == "cogvideox" and not self.settings.video_ai_enabled:
            logger.info("CogVideoX solicitado, mas video_ai_enabled=False. Usando template local.")
            visual_backend = "template"

        scene_clips: list[Path] = []
        preview_image: Path | None = None

        for index, scene in enumerate(plan.scenes, start=1):
            scene_dir = workdir / f"{index:02d}-{slugify(scene.title)}"
            scene_dir.mkdir(parents=True, exist_ok=True)
            image_path = self.visual_renderer.render_scene(
                scene,
                scene_dir / "frame.png",
                index,
                request=request,
            )
            if preview_image is None:
                preview_image = image_path

            animation_path = None
            if visual_backend == "cogvideox":
                try:
                    animation_path = self.video_animator.animate_scene(
                        scene=scene,
                        image_path=image_path,
                        output_path=scene_dir / "motion.mp4",
                    )
                except Exception as exc:
                    logger.warning("CogVideoX falhou para %s. Usando frame estatico. Motivo: %s", scene.title, exc)
                    animation_path = None

            if animation_path is None:
                animation_path = self._render_local_scene_motion(
                    scene=scene,
                    scene_dir=scene_dir,
                    scene_index=index,
                    request=request,
                    ffmpeg_command=ffmpeg_command,
                )

            narration_result = self.narration.synthesize_scene(scene, scene_dir, request=request)
            duration = narration_result.duration
            plan.scenes[index - 1] = scene.model_copy(update={"duration_seconds": max(1, int(round(duration)))})
            scene_clip = scene_dir / "scene.mp4"
            self._create_scene_clip(
                scene=scene,
                image_path=image_path,
                animation_path=animation_path,
                audio_path=narration_result.audio_path,
                output_path=scene_clip,
                duration=duration,
                cues=narration_result.cues,
                subtitles=narration_result.subtitles,
                ffmpeg_command=ffmpeg_command,
            )
            scene_clips.append(scene_clip)

        final_video = workdir / "lesson.mp4"
        self._concat_clips(scene_clips, final_video, ffmpeg_command=ffmpeg_command)
        if preview_image is None:
            raise RuntimeError("No preview image generated")
        return RenderArtifacts(video_path=final_video, preview_image_path=preview_image)

    def _render_local_scene_motion(
        self,
        scene: LessonScene,
        scene_dir: Path,
        scene_index: int,
        request: RenderRequest,
        ffmpeg_command: str,
    ) -> Path:
        frames_dir = scene_dir / "template-motion"
        frame_count = 12
        self.visual_renderer.render_scene_animation(
            scene=scene,
            output_dir=frames_dir,
            scene_index=scene_index,
            request=request,
            frame_count=frame_count,
        )
        motion_path = scene_dir / "template-motion.mp4"
        command = [
            ffmpeg_command,
            "-y",
            "-framerate",
            "10",
            "-i",
            str(frames_dir / "frame-%03d.png"),
            "-vf",
            f"fps={self.settings.video_fps},format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "16",
            "-tune",
            "animation",
            "-movflags",
            "+faststart",
            str(motion_path),
        ]
        subprocess.run(command, check=True, capture_output=True)
        return motion_path

    def _create_scene_clip(
        self,
        scene: LessonScene,
        image_path: Path,
        animation_path: Path | None,
        audio_path: Path,
        output_path: Path,
        duration: float,
        cues: list[NarrationCue],
        subtitles: list[NarrationSubtitle],
        ffmpeg_command: str,
    ) -> None:
        filter_chain = self._build_scene_filter(
            scene=scene,
            duration=duration,
            animated_clip=animation_path is not None,
            cues=cues,
            subtitles=subtitles,
            subtitle_path=None,
        )
        audio_filter_chain = self._build_audio_filter()
        base_command = [ffmpeg_command, "-y"]
        if animation_path:
            command = base_command + [
                "-stream_loop",
                "-1",
                "-i",
                str(animation_path),
                "-i",
                str(audio_path),
                "-t",
                f"{duration:.2f}",
                "-vf",
                filter_chain,
                "-af",
                audio_filter_chain,
                "-c:v",
                "libx264",
                "-preset",
                "slow",
                "-crf",
                "16",
                "-tune",
                "animation",
                "-pix_fmt",
                "yuv420p",
                "-profile:v",
                "high",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        else:
            command = base_command + [
                "-loop",
                "1",
                "-framerate",
                str(self.settings.video_fps),
                "-i",
                str(image_path),
                "-i",
                str(audio_path),
                "-t",
                f"{duration:.2f}",
                "-vf",
                filter_chain,
                "-af",
                audio_filter_chain,
                "-c:v",
                "libx264",
                "-preset",
                "slow",
                "-crf",
                "16",
                "-tune",
                "animation",
                "-pix_fmt",
                "yuv420p",
                "-profile:v",
                "high",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        subprocess.run(command, check=True, capture_output=True)

    def _build_scene_filter(
        self,
        scene: LessonScene,
        duration: float,
        animated_clip: bool,
        cues: list[NarrationCue],
        subtitles: list[NarrationSubtitle],
        subtitle_path: Path | None,
    ) -> str:
        if animated_clip:
            filters = [
                f"scale={self.settings.video_width}:{self.settings.video_height}:flags=lanczos",
                "eq=saturation=1.06:brightness=0.02",
                "setsar=1",
            ]
        else:
            filters = [
                f"scale={self.settings.video_width}:{self.settings.video_height}:flags=lanczos",
                "eq=saturation=1.08:brightness=0.03",
                "setsar=1",
            ]

        if scene.teaching_mode == "dialogue":
            bubble_frames = self.visual_renderer.dialogue_bubble_layout(
                scene,
                self.settings.video_width,
                self.settings.video_height,
            )
            for start, end, speaker in self._dialogue_highlight_schedule(duration, subtitles):
                bubble_frame = bubble_frames.get(speaker)
                if bubble_frame is None:
                    continue
                x = bubble_frame.left - 4
                y = bubble_frame.top - 4
                width = (bubble_frame.right - bubble_frame.left) + 8
                height = (bubble_frame.bottom - bubble_frame.top) + 8
                stroke_color = "blue@0.95" if speaker == "teacher" else "orange@0.95"
                filters.append(
                    "drawbox="
                    f"x={x}:y={y}:w={width}:h={height}:"
                    f"color={stroke_color}:t=3:"
                    f"enable='between(t,{start:.2f},{end:.2f})'"
                )
        else:
            card_frames = self.visual_renderer.card_layout(scene, self.settings.video_width, self.settings.video_height)
            for start, end, card_index in self._card_highlight_schedule(scene, duration, cues):
                if card_index >= len(card_frames):
                    continue
                card = card_frames[card_index]
                x = card.left - 8
                y = card.top - 8
                width = card.width + 16
                height = card.height + 16
                filters.append(
                    "drawbox="
                    f"x={x}:y={y}:w={width}:h={height}:"
                    "color=yellow@0.12:t=fill:"
                    f"enable='between(t,{start:.2f},{end:.2f})'"
                )
                filters.append(
                    "drawbox="
                    f"x={x}:y={y}:w={width}:h={height}:"
                    "color=orange@0.95:t=5:"
                    f"enable='between(t,{start:.2f},{end:.2f})'"
                )

        return ",".join(filters)

    def _build_audio_filter(self) -> str:
        return ",".join(
            [
                "highpass=f=80",
                "lowpass=f=8500",
                "acompressor=threshold=-18dB:ratio=2.5:attack=20:release=180:makeup=2.5",
                "volume=1.08",
            ]
        )

    def _card_highlight_schedule(
        self,
        scene: LessonScene,
        duration: float,
        cues: list[NarrationCue],
    ) -> list[tuple[float, float, int]]:
        cards = (scene.vocabulary or scene.on_screen_text[:4])[:4]
        if not cards:
            return []

        cue_map = {cue.label.lower(): cue for cue in cues}
        schedule: list[tuple[float, float, int]] = []

        for index, card in enumerate(cards):
            cue = cue_map.get(card.lower())
            if cue is not None:
                start = min(duration - 0.15, max(0.0, cue.start))
                end = min(duration, max(start + 0.55, cue.end))
                schedule.append((start, end, index))

        if schedule:
            return schedule

        usable_duration = max(duration - 0.8, 1.6)
        slot = usable_duration / len(cards)
        highlight_length = min(1.9, max(1.0, slot * 0.72))
        for index, _card in enumerate(cards):
            start = min(duration - 0.25, 0.45 + (index * slot))
            end = min(duration, start + highlight_length)
            schedule.append((start, end, index))

        return schedule

    def _dialogue_highlight_schedule(
        self,
        duration: float,
        subtitles: list[NarrationSubtitle],
    ) -> list[tuple[float, float, str]]:
        schedule: list[tuple[float, float, str]] = []
        for subtitle in subtitles:
            if subtitle.speaker not in {"teacher", "student"}:
                continue
            if subtitle.language != "en-US":
                continue
            start = min(duration - 0.15, max(0.0, subtitle.start))
            end = min(duration, max(start + 0.55, subtitle.end))
            schedule.append((start, end, subtitle.speaker))

        return schedule

    def _concat_clips(self, scene_clips: list[Path], output_path: Path, ffmpeg_command: str) -> None:
        concat_file = output_path.parent / "scenes.txt"
        concat_file.write_text(
            "\n".join(f"file '{clip.resolve().as_posix()}'" for clip in scene_clips),
            encoding="utf-8",
        )
        command = [
            ffmpeg_command,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "16",
            "-tune",
            "animation",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        subprocess.run(command, check=True, capture_output=True)

    def _write_ass_subtitles(self, output_path: Path, subtitles: list[NarrationSubtitle]) -> None:
        has_dialogue = len({subtitle.speaker for subtitle in subtitles}) > 1
        header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,24,&H00FFFFFF,&H000000FF,&H00131A24,&H8C000000,-1,0,0,0,100,100,0,0,3,1,0,2,130,130,92,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        lines = [header]
        for subtitle in subtitles:
            start = self._ass_time(subtitle.start)
            end = self._ass_time(subtitle.end)
            text = self._ass_escape(self._subtitle_text(subtitle, has_dialogue))
            lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n")
        output_path.write_text("".join(lines), encoding="utf-8")

    def _subtitle_filter_path(self, path: Path) -> str:
        try:
            relative_path = path.resolve().relative_to(Path.cwd().resolve())
            subtitle_path = relative_path.as_posix()
        except ValueError:
            subtitle_path = path.resolve().as_posix()
        subtitle_path = subtitle_path.replace(":", "\\:")
        return subtitle_path.replace("'", "\\'")

    def _ass_time(self, value: float) -> str:
        total_centiseconds = int(round(max(value, 0.0) * 100))
        hours, remainder = divmod(total_centiseconds, 360000)
        minutes, remainder = divmod(remainder, 6000)
        seconds, centiseconds = divmod(remainder, 100)
        return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"

    def _ass_escape(self, text: str) -> str:
        escaped = text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")
        return escaped.replace("\n", r"\N")

    def _subtitle_text(self, subtitle: NarrationSubtitle, has_dialogue: bool) -> str:
        speaker_label = ""
        if has_dialogue:
            speaker_label = "Professor: " if subtitle.speaker == "teacher" else "Aluno: "
        wrapped = textwrap.wrap(f"{speaker_label}{subtitle.text}", width=52)
        return "\n".join(wrapped[:3])
