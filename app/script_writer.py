from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas import LessonPlan, LessonScene, RenderRequest


@dataclass(frozen=True)
class ScriptBlock:
    scene_index: int
    text: str
    duration_seconds: int


class ScriptWriter:
    max_block_chars = 500

    def prepare(self, plan: LessonPlan, request: RenderRequest) -> tuple[LessonPlan, list[ScriptBlock]]:
        raw_blocks = [self._scene_to_block(scene) for scene in plan.scenes]
        durations = self._sync_durations(raw_blocks, request)
        synced_scenes: list[LessonScene] = []
        blocks: list[ScriptBlock] = []

        for index, scene in enumerate(plan.scenes, start=1):
            synced_scene = scene.model_copy(
                update={"duration_seconds": durations[index - 1]}
            )
            synced_scenes.append(synced_scene)
            blocks.append(
                ScriptBlock(
                    scene_index=index,
                    text=raw_blocks[index - 1],
                    duration_seconds=durations[index - 1],
                )
            )

        synced_plan = plan.model_copy(update={"scenes": synced_scenes})
        return synced_plan, blocks

    def build_script_text(self, blocks: list[ScriptBlock]) -> str:
        return "\n\n".join(block.text for block in blocks).strip() + "\n"

    def _scene_to_block(self, scene: LessonScene) -> str:
        text = " ".join(segment.text.strip() for segment in scene.narration if segment.text.strip())
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) <= self.max_block_chars:
            return text

        clipped = text[: self.max_block_chars]
        last_stop = max(clipped.rfind("."), clipped.rfind("!"), clipped.rfind("?"))
        if last_stop >= 260:
            return clipped[: last_stop + 1].strip()
        last_space = clipped.rfind(" ")
        if last_space >= 260:
            return clipped[:last_space].strip()
        return clipped.strip()

    def _sync_durations(self, blocks: list[str], request: RenderRequest) -> list[int]:
        target_seconds = request.duration_minutes * 60
        scene_count = len(blocks)
        if scene_count == 0:
            return []

        estimated = [self._estimate_seconds(block, request) for block in blocks]
        total_estimated = sum(estimated) or scene_count
        min_duration = max(4, min(10, target_seconds // scene_count))
        durations = [
            max(min_duration, int(round(value * target_seconds / total_estimated)))
            for value in estimated
        ]
        current_total = sum(durations)

        while current_total < target_seconds:
            for index in range(scene_count):
                if current_total >= target_seconds:
                    break
                durations[index] += 1
                current_total += 1

        while current_total > target_seconds:
            for index in range(scene_count - 1, -1, -1):
                if current_total <= target_seconds:
                    break
                if durations[index] > min_duration:
                    durations[index] -= 1
                    current_total -= 1

        return durations

    def _estimate_seconds(self, text: str, request: RenderRequest) -> float:
        chars_per_second = 14.0 if request.narration_style == "natural" else 15.5
        punctuation_pause = (
            text.count(".") * 0.55
            + text.count("!") * 0.65
            + text.count("?") * 0.65
            + text.count(":") * 0.35
            + text.count(",") * 0.18
        )
        return max(4.0, (len(text) / chars_per_second) + punctuation_pause)
