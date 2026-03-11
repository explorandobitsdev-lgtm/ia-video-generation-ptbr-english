from __future__ import annotations

import shutil
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path
import re

from piper import PiperVoice, SynthesisConfig
import piper.download_voices as piper_download_voices

from app.config import Settings
from app.schemas import LessonScene, NarrationSegment, RenderRequest
from app.utils import slugify


@dataclass(frozen=True)
class NarrationCue:
    label: str
    start: float
    end: float


@dataclass(frozen=True)
class NarrationSubtitle:
    speaker: str
    language: str
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class NarrationResult:
    audio_path: Path
    duration: float
    cues: list[NarrationCue]
    subtitles: list[NarrationSubtitle]


class NarrationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._voice_cache: dict[str, PiperVoice] = {}

    def synthesize_scene(
        self,
        scene: LessonScene,
        scene_dir: Path,
        request: RenderRequest | None = None,
    ) -> NarrationResult:
        scene_dir.mkdir(parents=True, exist_ok=True)
        segment_paths: list[Path] = []
        cues: list[NarrationCue] = []
        subtitles: list[NarrationSubtitle] = []
        current_offset = 0.0
        clip_index = 1
        focus_words = [word.strip() for word in (scene.vocabulary or scene.on_screen_text[:4]) if word.strip()]

        for index, segment in enumerate(scene.narration, start=1):
            pause_duration = self._pause_marker_seconds(segment.text)
            if pause_duration is not None:
                output_path = scene_dir / f"segment-{clip_index:02d}-pause.wav"
                self._write_silence_wav(
                    output_path,
                    pause_duration,
                    reference_audio=segment_paths[-1] if segment_paths else None,
                )
                segment_paths.append(output_path)
                current_offset += pause_duration
                clip_index += 1
                continue

            voice = self._voice_for_segment(segment)
            chunks = self._chunk_text(segment.text)
            for chunk_position, chunk in enumerate(chunks, start=1):
                output_path = scene_dir / f"segment-{clip_index:02d}.wav"
                self._run_piper(
                    text=chunk,
                    language=segment.language,
                    speaker=segment.speaker,
                    voice=voice,
                    output_path=output_path,
                    request=request,
                )
                segment_paths.append(output_path)
                chunk_duration = self.wav_duration(output_path)
                cues.extend(
                    self._extract_cues(
                        text=chunk,
                        focus_words=focus_words,
                        chunk_start=current_offset,
                        chunk_duration=chunk_duration,
                    )
                )
                subtitles.append(
                    NarrationSubtitle(
                        speaker=segment.speaker,
                        language=segment.language,
                        text=chunk,
                        start=current_offset,
                        end=current_offset + chunk_duration,
                    )
                )
                current_offset += chunk_duration
                clip_index += 1

                if chunk_position < len(chunks):
                    gap_duration = self._pause_for_chunk(chunk)
                    silence_path = scene_dir / f"segment-{clip_index:02d}-gap.wav"
                    self._write_silence_wav(
                        silence_path,
                        gap_duration,
                        reference_audio=output_path,
                    )
                    segment_paths.append(silence_path)
                    current_offset += gap_duration
                    clip_index += 1

            if index < len(scene.narration):
                gap_duration = self._segment_gap_seconds(segment, scene.narration[index])
                silence_path = scene_dir / f"segment-{clip_index:02d}-gap.wav"
                self._write_silence_wav(
                    silence_path,
                    gap_duration,
                    reference_audio=segment_paths[-1],
                )
                segment_paths.append(silence_path)
                current_offset += gap_duration
                clip_index += 1

        final_audio = scene_dir / f"{slugify(scene.title)}-narration.wav"
        duration = self._concatenate_wavs(segment_paths, final_audio)
        tail_padding = self._scene_end_padding_seconds(scene)
        if tail_padding > 0:
            pad_path = scene_dir / "tail-pad.wav"
            self._write_silence_wav(
                pad_path,
                tail_padding,
                reference_audio=final_audio,
            )
            padded_audio = scene_dir / f"{slugify(scene.title)}-narration-final.wav"
            duration = self._concatenate_wavs([final_audio, pad_path], padded_audio)
            final_audio = padded_audio
        return NarrationResult(
            audio_path=final_audio,
            duration=duration,
            cues=self._deduplicate_cues(cues),
            subtitles=self._merge_subtitles(subtitles),
        )

    def _voice_for_segment(self, segment: NarrationSegment) -> str:
        if segment.language == "pt-BR":
            return (
                self.settings.piper_pt_teacher_voice
                if segment.speaker == "teacher"
                else self.settings.piper_pt_student_voice
            )
        return (
            self.settings.piper_en_teacher_voice
            if segment.speaker == "teacher"
            else self.settings.piper_en_student_voice
        )

    def _segment_gap_seconds(self, current: NarrationSegment, next_segment: NarrationSegment) -> float:
        if self._pause_marker_seconds(current.text) is not None or self._pause_marker_seconds(next_segment.text) is not None:
            return 0.0
        if current.speaker != next_segment.speaker:
            return self.settings.dialogue_gap_ms / 1000
        return self.settings.narration_gap_ms / 1000

    def _pause_marker_seconds(self, text: str) -> float | None:
        normalized = " ".join(text.strip().split())
        match = re.fullmatch(r"\[\[pause:(\d+(?:\.\d+)?)\]\]", normalized, flags=re.IGNORECASE)
        if match is None:
            return None
        return float(match.group(1))

    def _scene_end_padding_seconds(self, scene: LessonScene) -> float:
        if scene.teaching_mode == "movement":
            return 0.25
        if scene.teaching_mode == "dialogue":
            return 0.22
        return 0.32

    def _run_piper(
        self,
        text: str,
        language: str,
        speaker: str,
        voice: str,
        output_path: Path,
        request: RenderRequest | None = None,
    ) -> None:
        piper_voice = self._load_voice(voice)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        synthesis_config = self._build_synthesis_config(language, request, speaker)
        with wave.open(str(output_path), "wb") as wav_file:
            piper_voice.synthesize_wav(
                self._normalize_text(text),
                wav_file,
                syn_config=synthesis_config,
            )

    def _load_voice(self, voice_name: str) -> PiperVoice:
        cached_voice = self._voice_cache.get(voice_name)
        if cached_voice is not None:
            return cached_voice

        download_dir = self.settings.piper_download_dir
        download_dir.mkdir(parents=True, exist_ok=True)
        model_path = download_dir / f"{voice_name}.onnx"
        config_path = download_dir / f"{voice_name}.onnx.json"
        if not model_path.exists() or not config_path.exists():
            piper_download_voices.download_voice(voice_name, download_dir)

        loaded_voice = PiperVoice.load(
            model_path=model_path,
            config_path=config_path,
            download_dir=download_dir,
        )
        self._voice_cache[voice_name] = loaded_voice
        return loaded_voice

    def _build_synthesis_config(
        self,
        language: str,
        request: RenderRequest | None,
        speaker: str,
    ) -> SynthesisConfig:
        animated = request is not None and request.narration_style == "animated"
        student_length_bonus = 0.01 if speaker == "student" else 0.0
        student_noise_bonus = 0.02 if speaker == "student" else 0.0
        if language == "pt-BR":
            return SynthesisConfig(
                length_scale=self.settings.tts_pt_length_scale - (0.03 if animated else 0.0) + student_length_bonus,
                noise_scale=self.settings.tts_pt_noise_scale + (0.04 if animated else 0.0) + student_noise_bonus,
                noise_w_scale=self.settings.tts_noise_w_scale,
                volume=1.06 if speaker == "teacher" else 1.0,
            )
        return SynthesisConfig(
            length_scale=self.settings.tts_en_length_scale - (0.03 if animated else 0.0) + student_length_bonus,
            noise_scale=self.settings.tts_en_noise_scale + (0.04 if animated else 0.0) + student_noise_bonus,
            noise_w_scale=self.settings.tts_noise_w_scale,
            volume=1.0 if speaker == "teacher" else 0.96,
        )

    def _chunk_text(self, text: str) -> list[str]:
        normalized = " ".join(text.split())
        chunks = [part.strip() for part in re.split(r"(?<=[\.\!\?])\s+", normalized) if part.strip()]
        return chunks or [normalized]

    def _pause_for_chunk(self, chunk: str) -> float:
        if chunk.endswith(("?", "!")):
            return self.settings.sentence_gap_ms / 1000
        if chunk.endswith((".", ";", ":")):
            return (self.settings.sentence_gap_ms - 40) / 1000
        return self.settings.intra_sentence_gap_ms / 1000

    def _normalize_text(self, text: str) -> str:
        normalized = " ".join(text.strip().split())
        normalized = normalized.replace(":", ".")
        if normalized and normalized[-1] not in ".!?":
            normalized += "."
        return normalized

    def _concatenate_wavs(self, inputs: list[Path], output_path: Path) -> float:
        if len(inputs) == 1:
            shutil.copyfile(inputs[0], output_path)
            return self.wav_duration(output_path)

        ffmpeg_command = self.settings.resolve_ffmpeg_command()
        command = [ffmpeg_command, "-y"]
        for audio_file in inputs:
            command.extend(["-i", str(audio_file)])

        filter_inputs = "".join(f"[{index}:a]" for index in range(len(inputs)))
        filter_complex = f"{filter_inputs}concat=n={len(inputs)}:v=0:a=1[a]"
        command.extend(
            [
                "-filter_complex",
                filter_complex,
                "-map",
                "[a]",
                "-ar",
                "22050",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(output_path),
            ]
        )
        subprocess.run(command, check=True, capture_output=True)
        return self.wav_duration(output_path)

    def _extract_cues(
        self,
        text: str,
        focus_words: list[str],
        chunk_start: float,
        chunk_duration: float,
    ) -> list[NarrationCue]:
        normalized_chunk = self._normalize_for_match(text)
        if not normalized_chunk or chunk_duration <= 0:
            return []

        cues: list[NarrationCue] = []
        for focus_word in focus_words:
            normalized_focus = self._normalize_for_match(focus_word)
            if not normalized_focus:
                continue

            match = re.search(rf"\b{re.escape(normalized_focus)}\b", normalized_chunk)
            if match is None:
                continue

            start_ratio = match.start() / max(len(normalized_chunk), 1)
            end_ratio = match.end() / max(len(normalized_chunk), 1)
            start = chunk_start + (chunk_duration * start_ratio)
            end = chunk_start + (chunk_duration * end_ratio)
            emphasis_padding = min(0.24, chunk_duration * 0.08)
            cues.append(
                NarrationCue(
                    label=focus_word,
                    start=max(0.0, start - emphasis_padding),
                    end=max(start + 0.45, end + emphasis_padding),
                )
            )

        return cues

    def _deduplicate_cues(self, cues: list[NarrationCue]) -> list[NarrationCue]:
        deduped: list[NarrationCue] = []
        seen: set[tuple[str, int]] = set()
        for cue in sorted(cues, key=lambda item: (item.start, item.end, item.label.lower())):
            key = (cue.label.lower(), int(round(cue.start * 10)))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(cue)
        return deduped

    def _merge_subtitles(self, subtitles: list[NarrationSubtitle]) -> list[NarrationSubtitle]:
        merged: list[NarrationSubtitle] = []
        for subtitle in subtitles:
            cleaned = " ".join(subtitle.text.split())
            if not cleaned:
                continue
            if (
                merged
                and merged[-1].speaker == subtitle.speaker
                and merged[-1].language == subtitle.language
                and len(merged[-1].text) + len(cleaned) <= 72
                and subtitle.start - merged[-1].end <= 0.2
            ):
                previous = merged.pop()
                merged.append(
                    NarrationSubtitle(
                        speaker=previous.speaker,
                        language=previous.language,
                        text=f"{previous.text} {cleaned}",
                        start=previous.start,
                        end=subtitle.end,
                    )
                )
                continue
            merged.append(
                NarrationSubtitle(
                    speaker=subtitle.speaker,
                    language=subtitle.language,
                    text=cleaned,
                    start=subtitle.start,
                    end=subtitle.end,
                )
            )
        return merged

    def _normalize_for_match(self, text: str) -> str:
        lowered = text.lower()
        lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
        return " ".join(lowered.split())

    def _write_silence_wav(
        self,
        output_path: Path,
        duration_seconds: float,
        reference_audio: Path | None = None,
    ) -> None:
        channels = 1
        sample_width = 2
        frame_rate = 22050
        if reference_audio is not None:
            with wave.open(str(reference_audio), "rb") as wav_file:
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                frame_rate = wav_file.getframerate()
        total_frames = int(frame_rate * max(duration_seconds, 0))
        silence_frame = (0).to_bytes(sample_width, byteorder="little", signed=True)
        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(frame_rate)
            wav_file.writeframes(silence_frame * total_frames)

    def wav_duration(self, path: Path) -> float:
        with wave.open(str(path), "rb") as wav_file:
            return wav_file.getnframes() / float(wav_file.getframerate())
