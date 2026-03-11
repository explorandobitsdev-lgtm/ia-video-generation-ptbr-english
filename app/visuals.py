from __future__ import annotations

from dataclasses import dataclass
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.config import Settings
from app.schemas import LessonScene, NarrationSegment, RenderRequest


@dataclass(frozen=True)
class CardFrame:
    text: str
    left: int
    top: int
    width: int
    height: int
    fill: str
    detail_text: str | None = None
    badge_text: str | None = None


NUMBER_BADGES = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}


class TemplateVisualRenderer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def render_scene(
        self,
        scene: LessonScene,
        output_path: Path,
        scene_index: int,
        request: RenderRequest | None = None,
        *,
        animation_frame: int = 0,
        animation_cycle: int = 1,
        include_companion: bool = True,
    ) -> Path:
        image = self._build_scene_image(
            scene=scene,
            scene_index=scene_index,
            request=request,
            animation_frame=animation_frame,
            animation_cycle=animation_cycle,
            include_companion=include_companion,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path)
        return output_path

    def render_scene_animation(
        self,
        scene: LessonScene,
        output_dir: Path,
        scene_index: int,
        request: RenderRequest | None = None,
        *,
        frame_count: int = 12,
    ) -> list[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        frame_paths: list[Path] = []
        for frame_index in range(frame_count):
            frame_path = output_dir / f"frame-{frame_index:03d}.png"
            self.render_scene(
                scene=scene,
                output_path=frame_path,
                scene_index=scene_index,
                request=request,
                animation_frame=frame_index,
                animation_cycle=frame_count,
                include_companion=True,
            )
            frame_paths.append(frame_path)
        return frame_paths

    def _build_scene_image(
        self,
        scene: LessonScene,
        scene_index: int,
        request: RenderRequest | None,
        *,
        animation_frame: int,
        animation_cycle: int,
        include_companion: bool,
    ) -> Image.Image:
        width = self.settings.video_width
        height = self.settings.video_height
        base_color = self._hex_to_rgb(scene.background_palette[0]) + (255,)
        image = Image.new("RGBA", (width, height), color=base_color)
        draw = ImageDraw.Draw(image)

        self._draw_gradient(draw, width, height, scene.background_palette)
        self._draw_confetti(draw, width, height, scene_index)
        self._draw_hills(draw, width, height, scene.background_palette)
        if include_companion and scene.teaching_mode != "dialogue":
            self._draw_scene_companion(
                image,
                width,
                height,
                animation_frame=animation_frame,
                animation_cycle=animation_cycle,
            )
        self._draw_title(draw, scene, width, request)
        self._draw_cards(draw, scene, width, height)
        self._draw_narration_panel(draw, scene, width, height)
        return image.convert("RGB")

    def _draw_gradient(self, draw: ImageDraw.ImageDraw, width: int, height: int, colors: list[str]) -> None:
        top = self._hex_to_rgb(colors[0])
        mid = self._hex_to_rgb(colors[min(1, len(colors) - 1)])
        bottom = self._hex_to_rgb(colors[-1])
        for y in range(height):
            ratio = y / max(height - 1, 1)
            if ratio < 0.56:
                local_ratio = ratio / 0.56
                current = tuple(
                    int(top[channel] * (1 - local_ratio) + mid[channel] * local_ratio)
                    for channel in range(3)
                )
            else:
                local_ratio = (ratio - 0.56) / 0.44
                current = tuple(
                    int(mid[channel] * (1 - local_ratio) + bottom[channel] * local_ratio)
                    for channel in range(3)
                )
            draw.line([(0, y), (width, y)], fill=current)

    def _draw_confetti(self, draw: ImageDraw.ImageDraw, width: int, height: int, seed: int) -> None:
        rng = random.Random(seed)
        colors = ["#FFFFFF", "#F97316", "#2563EB", "#10B981", "#EC4899", "#FACC15"]
        for _ in range(18):
            x = rng.randint(-30, width + 30)
            y = rng.randint(26, int(height * 0.66))
            radius = rng.randint(14, 34)
            outline = colors[rng.randint(0, len(colors) - 1)]
            draw.ellipse((x, y, x + radius, y + radius), outline=outline, width=4)
            core_radius = max(5, radius // 4)
            core_x = x + rng.randint(4, max(4, radius - core_radius))
            core_y = y + rng.randint(4, max(4, radius - core_radius))
            draw.ellipse((core_x, core_y, core_x + core_radius, core_y + core_radius), fill=outline)
        for _ in range(12):
            x = rng.randint(24, width - 24)
            y = rng.randint(24, int(height * 0.7))
            radius = rng.randint(4, 10)
            fill = colors[rng.randint(0, len(colors) - 1)]
            draw.ellipse((x, y, x + radius, y + radius), fill=fill)

    def _draw_hills(self, draw: ImageDraw.ImageDraw, width: int, height: int, colors: list[str]) -> None:
        draw.ellipse(
            (-180, int(height * 0.72), int(width * 0.46), int(height * 1.08)),
            fill=self._hex_to_rgba(colors[1], 170),
        )
        draw.ellipse(
            (int(width * 0.64), int(height * 0.7), int(width * 1.12), int(height * 1.08)),
            fill=self._hex_to_rgba(colors[2], 150),
        )
        draw.ellipse(
            (int(width * 0.24), int(height * 0.18), int(width * 0.8), int(height * 0.82)),
            fill=(255, 255, 255, 28),
        )
        draw.rounded_rectangle(
            (0, int(height * 0.78), width, height),
            radius=0,
            fill=self._hex_to_rgba(colors[1], 150),
        )

    def _draw_scene_companion(
        self,
        image: Image.Image,
        width: int,
        height: int,
        *,
        animation_frame: int,
        animation_cycle: int,
    ) -> None:
        notebook_shift = 0
        sparkle_shift = 0
        pencil_angle = 0
        sticker_scale = 1.0

        companion = Image.new("RGBA", (360, 360), (0, 0, 0, 0))
        draw = ImageDraw.Draw(companion)

        draw.ellipse((40, 306, 248, 334), fill=(100, 116, 139, 92))
        draw.rounded_rectangle((52, 122, 220, 312), radius=48, fill="#FFF7ED", outline="#FB923C", width=6)
        draw.rounded_rectangle((40, 154, 72, 286), radius=18, fill="#DBEAFE", outline="#60A5FA", width=4)
        draw.rounded_rectangle((200, 154, 232, 286), radius=18, fill="#DBEAFE", outline="#60A5FA", width=4)
        draw.rounded_rectangle((74, 114, 198, 186), radius=28, fill="#FED7AA", outline="#FDBA74", width=4)
        draw.rectangle((88, 174, 184, 182), fill="#F59E0B")
        draw.ellipse((126, 168, 148, 190), fill="#FFF7ED", outline="#F59E0B", width=3)
        draw.rounded_rectangle((92, 208, 180, 284), radius=28, fill="#FEF3C7", outline="#F59E0B", width=4)
        draw.line((136, 208, 136, 284), fill="#FCD34D", width=4)
        draw.line((92, 246, 180, 246), fill="#FCD34D", width=4)

        notebook_top = 54 + notebook_shift
        draw.rounded_rectangle((112, notebook_top, 198, 152 + notebook_shift), radius=16, fill="#DBEAFE", outline="#60A5FA", width=4)
        draw.rectangle((122, notebook_top + 12, 134, notebook_top + 86), fill="#93C5FD")
        for line_y in (notebook_top + 28, notebook_top + 46, notebook_top + 64):
            draw.line((142, line_y, 184, line_y), fill="#60A5FA", width=3)

        sticker_center_x = 136
        sticker_center_y = 246
        sticker_radius = int(round(24 * sticker_scale))
        draw.ellipse(
            (
                sticker_center_x - sticker_radius,
                sticker_center_y - sticker_radius,
                sticker_center_x + sticker_radius,
                sticker_center_y + sticker_radius,
            ),
            fill="#60A5FA",
            outline="#2563EB",
            width=4,
        )
        label_font = self._load_font(18, bold=True)
        draw.text((117, 234), "ABC", font=label_font, fill="#FFFFFF")

        pencil_layer = self._build_companion_pencil_layer(pencil_angle)
        companion.alpha_composite(pencil_layer, (188, 116))

        for center_x, center_y, size, fill in (
            (246, 88 + sparkle_shift, 14, "#FDE68A"),
            (272, 128 - sparkle_shift, 12, "#93C5FD"),
            (54, 108 + sparkle_shift, 10, "#F9A8D4"),
        ):
            draw.polygon(
                [
                    (center_x, center_y - size),
                    (center_x + size // 2, center_y),
                    (center_x, center_y + size),
                    (center_x - size // 2, center_y),
                ],
                fill=fill,
            )

        companion_x = int(width * 0.075)
        companion_y = int(height * 0.46)
        image.alpha_composite(companion, (companion_x, companion_y))

    def _build_companion_pencil_layer(self, angle_degrees: float) -> Image.Image:
        pencil = Image.new("RGBA", (180, 180), (0, 0, 0, 0))
        draw = ImageDraw.Draw(pencil)
        draw.rounded_rectangle((22, 72, 124, 98), radius=12, fill="#FCD34D", outline="#F59E0B", width=3)
        draw.polygon([(124, 72), (154, 85), (124, 98)], fill="#FDE68A", outline="#D97706")
        draw.polygon([(148, 82), (162, 85), (148, 88)], fill="#111827")
        draw.rounded_rectangle((10, 72, 28, 98), radius=8, fill="#F9A8D4", outline="#EC4899", width=3)
        draw.rectangle((28, 72, 36, 98), fill="#E5E7EB")
        return pencil.rotate(angle_degrees, resample=Image.BICUBIC, center=(24, 86), expand=True)

    def _draw_title(
        self,
        draw: ImageDraw.ImageDraw,
        scene: LessonScene,
        width: int,
        request: RenderRequest | None,
    ) -> None:
        badge_font = self._load_font(28, bold=True)
        body_font = self._load_font(28, bold=False)

        panel_left = 36
        panel_top = 42
        panel_right = width - 52
        panel_bottom = 176
        badge_left = panel_left + 22
        badge_top = panel_top + 10
        badge_right = badge_left + 178
        badge_bottom = badge_top + 54
        title_x = badge_right + 34
        lesson_theme = self._lesson_theme_text(request)
        theme_left = panel_right - 24
        title_right = panel_right - 28

        self._draw_elevated_panel(
            draw,
            (panel_left, panel_top, panel_right, panel_bottom),
            radius=40,
            fill=(255, 253, 247, 230),
        )
        draw.rounded_rectangle((panel_left + 24, panel_bottom - 18, panel_right - 24, panel_bottom - 10), radius=8, fill="#E2E8F0")
        draw.rounded_rectangle((panel_left + 24, panel_bottom - 18, panel_left + 280, panel_bottom - 10), radius=8, fill="#2563EB")
        draw.rounded_rectangle((badge_left, badge_top, badge_right, badge_bottom), radius=24, fill="#1D4ED8")
        draw.text((badge_left + 22, badge_top + 10), "Kid Class", font=badge_font, fill="#FFFFFF")
        if lesson_theme:
            theme_font = self._fit_font_to_width(draw, lesson_theme, bold=True, sizes=[26, 24, 22, 20], max_width=280)
            theme_text = self._truncate_text_to_width(draw, lesson_theme, theme_font, 280)
            theme_width = self._text_width(draw, theme_text, theme_font) + 44
            theme_left = panel_right - theme_width - 24
            title_right = theme_left - 28
            draw.rounded_rectangle(
                (theme_left, panel_top + 22, theme_left + theme_width, panel_top + 74),
                radius=24,
                fill="#FB923C",
            )
            draw.text((theme_left + 22, panel_top + 34), theme_text, font=theme_font, fill="#FFFFFF")

        title_max_width = max(320, title_right - title_x)
        title_font = self._fit_font_to_width(draw, scene.title, bold=True, sizes=[58, 54, 50, 46, 42], max_width=title_max_width)
        title_text = self._truncate_text_to_width(draw, scene.title, title_font, title_max_width)
        draw.text((title_x, 60), title_text, font=title_font, fill="#0F172A")

        preview_words = "  |  ".join(scene.on_screen_text[:4]) if scene.on_screen_text else "English time"
        preview_max_width = title_right - title_x
        preview_lines = self._wrap_text_to_width(draw, preview_words, body_font, preview_max_width)
        preview_y = 128
        for line_index, line in enumerate(preview_lines[:2]):
            draw.text((title_x + 2, preview_y + (line_index * 32)), line, font=body_font, fill="#475569")

    def _draw_cards(self, draw: ImageDraw.ImageDraw, scene: LessonScene, width: int, height: int) -> None:
        detail_font = self._load_font(20, bold=False)
        for card in self.card_layout(scene, width, height):
            self._draw_elevated_panel(
                draw,
                (card.left, card.top, card.left + card.width, card.top + card.height),
                radius=30,
                fill=card.fill,
            )
            draw.rounded_rectangle(
                (card.left + 18, card.top + 18, card.left + card.width - 18, card.top + 32),
                radius=7,
                fill="#FFFFFF",
            )
            title_top_padding = 34 if card.badge_text else 0
            if card.badge_text:
                self._draw_card_badge(draw, card)
            title_bottom = self._draw_card_title(
                draw,
                card.text.title(),
                x=card.left,
                y=card.top,
                card_width=card.width,
                top_padding=title_top_padding,
            )
            if card.detail_text:
                detail_y = max(card.top + (110 if card.badge_text else 100), title_bottom + 8)
                draw.text((card.left + 24, detail_y), card.detail_text, font=detail_font, fill="#64748B")

        if scene.teaching_mode == "dialogue":
            self._draw_dialogue_scene(draw, scene, width, height)

    def card_layout(self, scene: LessonScene, width: int, height: int) -> list[CardFrame]:
        cards = scene.vocabulary or scene.on_screen_text[:4]
        if not cards:
            return []

        if scene.teaching_mode == "dialogue":
            visible_cards = cards[:3]
            card_width = 260
            card_height = 150
            gap = 24
            top = 236
            colors = ["#FFFDF7", "#FEF3C7", "#DBEAFE"]
            detail_text = None
        else:
            visible_cards = cards[:4]
            card_width = 250
            card_height = 150
            gap = 20
            top = 244
            colors = ["#FFFFFF", "#FEF3C7", "#DBEAFE", "#FCE7F3"]
            detail_text = "Listen • Repeat"

        total_width = (len(visible_cards) * card_width) + (max(len(visible_cards) - 1, 0) * gap)
        base_x = int((width - total_width) / 2)
        return [
            CardFrame(
                text=word,
                left=base_x + index * (card_width + gap),
                top=top,
                width=card_width,
                height=card_height,
                fill=colors[index % len(colors)],
                detail_text=detail_text,
                badge_text=self._number_badge_for_word(word),
            )
            for index, word in enumerate(visible_cards)
        ]

    def _draw_card_badge(self, draw: ImageDraw.ImageDraw, card: CardFrame) -> None:
        if not card.badge_text:
            return

        badge_font = self._load_font(24 if len(card.badge_text) == 1 else 22, bold=True)
        badge_width = 56 if len(card.badge_text) == 1 else 72
        badge_left = card.left + int((card.width - badge_width) / 2)
        badge_top = card.top + 14
        badge_right = badge_left + badge_width
        badge_bottom = badge_top + 36
        draw.rounded_rectangle(
            (badge_left, badge_top, badge_right, badge_bottom),
            radius=20,
            fill="#1D4ED8",
            outline="#FFFFFF",
            width=3,
        )
        text_width = self._text_width(draw, card.badge_text, badge_font)
        text_x = badge_left + int((badge_width - text_width) / 2)
        draw.text((text_x, badge_top + 4), card.badge_text, font=badge_font, fill="#FFFFFF")

    def _draw_dialogue_scene(self, draw: ImageDraw.ImageDraw, scene: LessonScene, width: int, height: int) -> None:
        label_font = self._load_font(24, bold=True)
        text_font = self._load_font(28, bold=False)
        teacher_segment, student_segment = self._dialogue_segments(scene)

        if teacher_segment is not None and student_segment is not None:
            self._draw_dialogue_stage(draw, width, height)
            teacher_tip = self._draw_dialogue_character(
                draw,
                center_x=372,
                base_y=800,
                role="teacher",
                accent="#1D4ED8",
                shirt_fill="#1D4ED8",
                shirt_outline="#1E40AF",
                label="Professor",
            )
            student_tip = self._draw_dialogue_character(
                draw,
                center_x=1548,
                base_y=800,
                role="student",
                accent="#F97316",
                shirt_fill="#F97316",
                shirt_outline="#EA580C",
                label="Aluno",
            )
            draw.line((612, 684, 1298, 684), fill="#FFFFFF", width=6)
            draw.ellipse((936, 658, 974, 696), fill="#FFFFFF")

            self._draw_dialogue_exchange_bubble(
                draw=draw,
                text=teacher_segment.text,
                speaker_label="Professor",
                bubble_label="Pergunta",
                left=216,
                top=426,
                right=884,
                fill_color="#FFFDF7",
                accent="#1D4ED8",
                label_font=label_font,
                text_font=text_font,
                tail_tip=teacher_tip,
                tail_side="right",
            )
            self._draw_dialogue_exchange_bubble(
                draw=draw,
                text=student_segment.text,
                speaker_label="Aluno",
                bubble_label="Resposta",
                left=1040,
                top=470,
                right=1710,
                fill_color="#FEF3C7",
                accent="#EA580C",
                label_font=label_font,
                text_font=text_font,
                tail_tip=student_tip,
                tail_side="left",
            )
            return

        english_lines = [segment for segment in scene.narration if segment.language == "en-US"][:2]
        if len(english_lines) < 2:
            english_lines = [segment for segment in scene.narration[:2]]

        top = 430
        previous_bottom = top
        for index, segment in enumerate(english_lines[:2]):
            is_teacher = segment.speaker == "teacher"
            bubble_left = 420 if is_teacher else 520
            bubble_right = width - (116 if is_teacher else 136)
            fill_color = "#FFFDF7" if is_teacher else "#FEF3C7"
            accent = "#1D4ED8" if is_teacher else "#EA580C"
            previous_bottom = self._draw_dialogue_bubble(
                draw=draw,
                text=segment.text,
                speaker_label="Professor" if is_teacher else "Aluno",
                left=bubble_left,
                top=top if index == 0 else previous_bottom + 28,
                right=bubble_right,
                fill_color=fill_color,
                accent=accent,
                label_font=label_font,
                text_font=text_font,
            )

    def _dialogue_segments(self, scene: LessonScene) -> tuple[NarrationSegment | None, NarrationSegment | None]:
        english_lines = [segment for segment in scene.narration if segment.language == "en-US"]
        teacher_segment = next((segment for segment in english_lines if segment.speaker == "teacher"), None)
        student_segment = next((segment for segment in english_lines if segment.speaker == "student"), None)
        return teacher_segment, student_segment

    def _draw_dialogue_stage(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        stage_top = 352
        stage_bottom = 812
        self._draw_elevated_panel(
            draw,
            (160, stage_top, width - 160, stage_bottom),
            radius=58,
            fill=(255, 249, 241, 224),
        )
        draw.rounded_rectangle(
            (220, stage_top + 28, 676, stage_top + 96),
            radius=34,
            fill=(219, 234, 254, 220),
            outline="#FFFFFF",
            width=3,
        )
        draw.rounded_rectangle(
            (width - 612, stage_top + 28, width - 220, stage_top + 96),
            radius=34,
            fill=(255, 237, 213, 220),
            outline="#FFFFFF",
            width=3,
        )
        banner_font = self._load_font(28, bold=True)
        draw.text((260, stage_top + 46), "Role Play", font=banner_font, fill="#1E3A8A")
        draw.text((width - 548, stage_top + 46), "Question + Answer", font=banner_font, fill="#C2410C")
        draw.rounded_rectangle(
            (248, stage_top + 126, width - 248, stage_top + 132),
            radius=3,
            fill=(255, 255, 255, 145),
        )
        draw.ellipse((292, stage_bottom - 126, 652, stage_bottom + 18), fill=(147, 197, 253, 118))
        draw.ellipse((1270, stage_bottom - 126, 1630, stage_bottom + 18), fill=(244, 114, 182, 92))

    def _draw_dialogue_character(
        self,
        draw: ImageDraw.ImageDraw,
        center_x: int,
        base_y: int,
        *,
        role: str,
        accent: str,
        shirt_fill: str,
        shirt_outline: str,
        label: str,
    ) -> tuple[int, int]:
        skin_fill = "#F8C9A0" if role == "teacher" else "#F7C59F"
        hair_fill = "#334155" if role == "teacher" else "#7C3AED"
        glow_fill = self._hex_to_rgba(accent, 28)
        card_left = center_x - 98
        card_top = base_y - 196
        card_right = center_x + 98
        card_bottom = base_y
        head_radius = 50
        head_top = card_top + 26
        head_bottom = head_top + (head_radius * 2)

        draw.ellipse((center_x - 136, card_top + 84, center_x + 136, card_bottom + 20), fill=glow_fill)
        self._draw_elevated_panel(
            draw,
            (card_left, card_top, card_right, card_bottom),
            radius=52,
            fill=(255, 253, 247, 222),
        )
        draw.rounded_rectangle(
            (card_left + 18, card_top + 18, card_right - 18, card_top + 36),
            radius=9,
            fill=accent,
        )
        draw.ellipse((center_x - 74, card_top + 92, center_x + 74, card_bottom - 18), fill=self._hex_to_rgba(shirt_fill, 34))
        draw.ellipse(
            (center_x - head_radius, head_top, center_x + head_radius, head_bottom),
            fill=skin_fill,
            outline="#FFFFFF",
            width=4,
        )
        if role == "teacher":
            draw.pieslice(
                (center_x - 60, head_top - 10, center_x + 60, head_bottom - 18),
                start=180,
                end=360,
                fill=hair_fill,
            )
            draw.rectangle((center_x - 58, head_top + 30, center_x - 40, head_bottom - 24), fill=hair_fill)
            draw.rectangle((center_x + 40, head_top + 30, center_x + 58, head_bottom - 24), fill=hair_fill)
        else:
            draw.ellipse((center_x - 68, head_top - 12, center_x + 68, head_top + 78), fill=hair_fill)
            draw.polygon(
                [
                    (center_x - 66, head_top + 48),
                    (center_x - 24, head_top + 10),
                    (center_x + 16, head_top + 48),
                    (center_x + 64, head_top + 18),
                    (center_x + 66, head_top + 86),
                    (center_x - 66, head_top + 86),
                ],
                fill=hair_fill,
            )

        eye_y = head_top + 54
        draw.ellipse((center_x - 28, eye_y, center_x - 10, eye_y + 16), fill="#0F172A")
        draw.ellipse((center_x + 10, eye_y, center_x + 28, eye_y + 16), fill="#0F172A")
        draw.arc(
            (center_x - 28, head_top + 76, center_x + 28, head_top + 114),
            start=20,
            end=160,
            fill="#B45309",
            width=4,
        )
        draw.ellipse((center_x - 54, head_top + 68, center_x - 40, head_top + 84), fill="#FCA5A5")
        draw.ellipse((center_x + 40, head_top + 68, center_x + 54, head_top + 84), fill="#FCA5A5")
        draw.rounded_rectangle(
            (center_x - 64, card_top + 118, center_x + 64, card_bottom - 36),
            radius=34,
            fill=shirt_fill,
            outline=shirt_outline,
            width=4,
        )
        draw.arc(
            (center_x - 54, card_top + 124, center_x + 54, card_top + 196),
            start=180,
            end=360,
            fill="#FFFFFF",
            width=4,
        )

        label_font = self._load_font(22, bold=True)
        label_width = self._text_width(draw, label, label_font) + 44
        label_left = center_x - int(label_width / 2)
        label_top = card_bottom - 66
        self._draw_elevated_panel(
            draw,
            (label_left, label_top, label_left + label_width, label_top + 48),
            radius=20,
            fill=accent,
        )
        draw.text((label_left + 22, label_top + 10), label, font=label_font, fill="#FFFFFF")
        return center_x + (74 if role == "teacher" else -74), card_top + 70

    def _draw_dialogue_exchange_bubble(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        speaker_label: str,
        bubble_label: str,
        left: int,
        top: int,
        right: int,
        fill_color: str,
        accent: str,
        label_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        text_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        tail_tip: tuple[int, int],
        tail_side: str,
    ) -> int:
        wrapped = self._wrap_text_to_width(draw, text, text_font, (right - left) - 60)[:3]
        line_height = self._line_height(draw, text_font) + 4
        bubble_height = max(154, 102 + (len(wrapped) * line_height))
        bottom = top + bubble_height

        if tail_side == "right":
            tail = [(right - 88, bottom - 18), (right - 14, bottom - 46), tail_tip]
        else:
            tail = [(left + 88, bottom - 18), (left + 14, bottom - 46), tail_tip]
        draw.polygon(tail, fill=fill_color)
        self._draw_elevated_panel(
            draw,
            (left, top, right, bottom),
            radius=34,
            fill=fill_color,
        )
        draw.rounded_rectangle((left + 24, top + 18, right - 24, top + 26), radius=4, fill="#FFFFFF")

        bubble_label_width = self._text_width(draw, bubble_label, label_font) + 44
        draw.rounded_rectangle((left + 24, top + 18, left + 24 + bubble_label_width, top + 58), radius=18, fill=accent)
        draw.text((left + 44, top + 26), bubble_label, font=label_font, fill="#FFFFFF")

        speaker_font = self._load_font(22, bold=True)
        draw.text((left + 30, top + 74), speaker_label, font=speaker_font, fill=accent)

        text_y = top + 108
        for line_index, line in enumerate(wrapped):
            draw.text((left + 28, text_y + (line_index * line_height)), line, font=text_font, fill="#0F172A")
        return bottom

    def _draw_dialogue_bubble(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        speaker_label: str,
        left: int,
        top: int,
        right: int,
        fill_color: str,
        accent: str,
        label_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        text_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    ) -> int:
        label_width = self._text_width(draw, speaker_label, label_font) + 44
        wrapped = self._wrap_text_to_width(draw, text, text_font, (right - left) - 56)[:3]
        line_height = self._line_height(draw, text_font) + 4
        bubble_height = max(132, 86 + (len(wrapped) * line_height))
        bottom = top + bubble_height

        draw.rounded_rectangle((left, top, right, bottom), radius=34, fill=fill_color, outline="#FFFFFF", width=4)
        draw.rounded_rectangle((left + 24, top + 18, left + 24 + label_width, top + 58), radius=18, fill=accent)
        draw.text((left + 42, top + 26), speaker_label, font=label_font, fill="#FFFFFF")

        text_y = top + 76
        for line_index, line in enumerate(wrapped):
            draw.text((left + 28, text_y + (line_index * line_height)), line, font=text_font, fill="#0F172A")
        return bottom

    def _draw_narration_panel(self, draw: ImageDraw.ImageDraw, scene: LessonScene, width: int, height: int) -> None:
        panel_left = 68
        panel_top = 846 if scene.teaching_mode == "dialogue" else 838
        panel_right = width - 68
        panel_bottom = 1022 if scene.teaching_mode == "dialogue" else 1004
        self._draw_elevated_panel(
            draw,
            (panel_left, panel_top, panel_right, panel_bottom),
            radius=36,
            fill=(255, 253, 247, 232),
        )

        panel_font = self._load_font(22 if scene.teaching_mode == "dialogue" else 24, bold=False)
        text = self._narration_panel_text(scene)
        wrapped = self._wrap_text_to_width(draw, text, panel_font, panel_right - panel_left - 56)
        line_height = self._line_height(draw, panel_font) + 4
        start_y = panel_top + 22
        if scene.teaching_mode == "dialogue":
            badge_font = self._load_font(22, bold=True)
            draw.rounded_rectangle((panel_left + 24, panel_top + 18, panel_left + 270, panel_top + 58), radius=18, fill="#1D4ED8")
            draw.text((panel_left + 42, panel_top + 26), "Professor explica", font=badge_font, fill="#FFFFFF")
            start_y = panel_top + 70
        visible_lines = wrapped[:2] if scene.teaching_mode == "dialogue" else wrapped[:3]
        for line_index, line in enumerate(visible_lines):
            draw.text((panel_left + 28, start_y + (line_index * line_height)), line, font=panel_font, fill="#0F172A")

    def _draw_elevated_panel(
        self,
        draw: ImageDraw.ImageDraw,
        box: tuple[int, int, int, int],
        *,
        radius: int,
        fill: str | tuple[int, int, int] | tuple[int, int, int, int],
        outline: str = "#FFFFFF",
        outline_width: int = 3,
        shadow_offset: tuple[int, int] = (0, 12),
        shadow_fill: tuple[int, int, int, int] = (15, 23, 42, 34),
    ) -> None:
        left, top, right, bottom = box
        shadow_left = left + shadow_offset[0]
        shadow_top = top + shadow_offset[1]
        shadow_right = right + shadow_offset[0]
        shadow_bottom = bottom + shadow_offset[1]
        draw.rounded_rectangle(
            (shadow_left, shadow_top, shadow_right, shadow_bottom),
            radius=radius,
            fill=shadow_fill,
        )
        draw.rounded_rectangle(
            (left, top, right, bottom),
            radius=radius,
            fill=fill,
            outline=outline,
            width=outline_width,
        )

    def _load_font(self, size: int, bold: bool) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "C:/Windows/Fonts/verdanab.ttf" if bold else "C:/Windows/Fonts/verdana.ttf",
            "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        ]
        for candidate in candidates:
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                continue
        return ImageFont.load_default()

    def _draw_card_title(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        x: int,
        y: int,
        card_width: int,
        top_padding: int = 0,
    ) -> int:
        max_width = card_width - 44
        for font_size in (34, 32, 30, 28, 26, 24, 22):
            font = self._load_font(font_size, bold=True)
            lines = self._wrap_text_to_width(draw, text, font, max_width)
            if len(lines) <= 2:
                line_height = self._line_height(draw, font)
                total_height = len(lines) * line_height
                start_y = y + 26 + top_padding + max(0, (44 - total_height) // 2)
                for line_index, line in enumerate(lines):
                    draw.text((x + 22, start_y + (line_index * line_height)), line, font=font, fill="#0F172A")
                return start_y + (len(lines) * line_height)

        fallback_font = self._load_font(20, bold=True)
        fallback_lines = self._wrap_text_to_width(draw, text, fallback_font, max_width)[:2]
        line_height = self._line_height(draw, fallback_font)
        for line_index, line in enumerate(fallback_lines):
            draw.text((x + 22, y + 26 + top_padding + (line_index * line_height)), line, font=fallback_font, fill="#0F172A")
        return y + 26 + top_padding + (len(fallback_lines) * line_height)

    def _number_badge_for_word(self, word: str) -> str | None:
        return NUMBER_BADGES.get(word.strip().lower())

    def _lesson_theme_text(self, request: RenderRequest | None) -> str | None:
        if request is None or not request.lesson_name:
            return None
        return " ".join(request.lesson_name.split())

    def _narration_panel_text(self, scene: LessonScene) -> str:
        teacher_segments = [
            " ".join(segment.text.split())
            for segment in scene.narration
            if segment.language == "pt-BR" and segment.speaker == "teacher"
        ]
        if teacher_segments:
            if scene.teaching_mode == "dialogue":
                return teacher_segments[-1]
            return teacher_segments[0]
        if scene.narration:
            return " ".join(scene.narration[0].text.split())
        return ""

    def _wrap_text_to_width(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        max_width: int,
    ) -> list[str]:
        words = text.split()
        if not words:
            return [text]

        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if self._text_width(draw, candidate, font) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def _text_width(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    ) -> int:
        left, _top, right, _bottom = draw.textbbox((0, 0), text, font=font)
        return right - left

    def _line_height(
        self,
        draw: ImageDraw.ImageDraw,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    ) -> int:
        _left, top, _right, bottom = draw.textbbox((0, 0), "Ag", font=font)
        return (bottom - top) + 2

    def _fit_font_to_width(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        *,
        bold: bool,
        sizes: list[int],
        max_width: int,
    ) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        for size in sizes:
            font = self._load_font(size, bold=bold)
            if self._text_width(draw, text, font) <= max_width:
                return font
        return self._load_font(sizes[-1], bold=bold)

    def _truncate_text_to_width(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        max_width: int,
    ) -> str:
        if self._text_width(draw, text, font) <= max_width:
            return text

        words = text.split()
        if not words:
            return text

        truncated = words[0]
        for word in words[1:]:
            candidate = f"{truncated} {word}"
            if self._text_width(draw, f"{candidate}...", font) <= max_width:
                truncated = candidate
            else:
                break
        if truncated == words[0] and self._text_width(draw, f"{truncated}...", font) > max_width:
            while truncated and self._text_width(draw, f"{truncated}...", font) > max_width:
                truncated = truncated[:-1]
        return f"{truncated}..." if truncated != text else text

    def _hex_to_rgb(self, color: str) -> tuple[int, int, int]:
        color = color.lstrip("#")
        return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))

    def _hex_to_rgba(self, color: str, alpha: int) -> tuple[int, int, int, int]:
        return self._hex_to_rgb(color) + (alpha,)
