from __future__ import annotations

from dataclasses import dataclass
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.config import Settings
from app.schemas import LessonScene, RenderRequest


@dataclass(frozen=True)
class CardFrame:
    text: str
    left: int
    top: int
    width: int
    height: int
    fill: str
    detail_text: str | None = None


class TemplateVisualRenderer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def render_scene(
        self,
        scene: LessonScene,
        output_path: Path,
        scene_index: int,
        request: RenderRequest | None = None,
    ) -> Path:
        width = self.settings.video_width
        height = self.settings.video_height
        image = Image.new("RGB", (width, height), color=scene.background_palette[0])
        draw = ImageDraw.Draw(image)

        self._draw_gradient(draw, width, height, scene.background_palette)
        self._draw_confetti(draw, width, height, scene_index)
        self._draw_hills(draw, width, height, scene.background_palette)
        self._draw_mascot(draw, width, height)
        self._draw_title(draw, scene, width, request)
        self._draw_cards(draw, scene, width, height)
        self._draw_narration_panel(draw, scene, width, height)
        self._draw_footer(draw, width, height, scene_index, request)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path)
        return output_path

    def _draw_gradient(self, draw: ImageDraw.ImageDraw, width: int, height: int, colors: list[str]) -> None:
        for y in range(height):
            ratio = y / max(height - 1, 1)
            top = self._hex_to_rgb(colors[0])
            bottom = self._hex_to_rgb(colors[-1])
            current = tuple(
                int(top[channel] * (1 - ratio) + bottom[channel] * ratio)
                for channel in range(3)
            )
            draw.line([(0, y), (width, y)], fill=current)

    def _draw_confetti(self, draw: ImageDraw.ImageDraw, width: int, height: int, seed: int) -> None:
        rng = random.Random(seed)
        colors = ["#FFFFFF", "#F97316", "#2563EB", "#10B981", "#EC4899"]
        for _ in range(42):
            x = rng.randint(0, width)
            y = rng.randint(0, int(height * 0.68))
            radius = rng.randint(5, 16)
            fill = colors[rng.randint(0, len(colors) - 1)]
            draw.ellipse((x, y, x + radius, y + radius), fill=fill)

    def _draw_hills(self, draw: ImageDraw.ImageDraw, width: int, height: int, colors: list[str]) -> None:
        draw.ellipse(
            (-140, int(height * 0.72), int(width * 0.55), int(height * 1.25)),
            fill=colors[1],
        )
        draw.ellipse(
            (int(width * 0.35), int(height * 0.65), int(width * 1.12), int(height * 1.22)),
            fill=colors[2],
        )
        draw.rectangle((0, int(height * 0.74), width, height), fill=colors[1])

    def _draw_mascot(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        mascot_x = int(width * 0.12)
        mascot_y = int(height * 0.46)
        draw.rounded_rectangle(
            (mascot_x, mascot_y, mascot_x + 160, mascot_y + 190),
            radius=32,
            fill="#FFF7ED",
            outline="#FB923C",
            width=5,
        )
        draw.ellipse((mascot_x + 35, mascot_y + 24, mascot_x + 125, mascot_y + 114), fill="#FDE68A")
        draw.ellipse((mascot_x + 56, mascot_y + 55, mascot_x + 66, mascot_y + 65), fill="#111827")
        draw.ellipse((mascot_x + 94, mascot_y + 55, mascot_x + 104, mascot_y + 65), fill="#111827")
        draw.arc(
            (mascot_x + 55, mascot_y + 64, mascot_x + 105, mascot_y + 94),
            start=0,
            end=180,
            fill="#111827",
            width=4,
        )
        draw.polygon(
            [
                (mascot_x + 24, mascot_y + 45),
                (mascot_x + 5, mascot_y + 15),
                (mascot_x + 48, mascot_y + 28),
            ],
            fill="#FCA5A5",
        )
        draw.polygon(
            [
                (mascot_x + 136, mascot_y + 45),
                (mascot_x + 155, mascot_y + 15),
                (mascot_x + 112, mascot_y + 28),
            ],
            fill="#93C5FD",
        )

    def _draw_title(
        self,
        draw: ImageDraw.ImageDraw,
        scene: LessonScene,
        width: int,
        request: RenderRequest | None,
    ) -> None:
        title_font = self._load_font(58, bold=True)
        badge_font = self._load_font(30, bold=True)
        body_font = self._load_font(28, bold=False)
        meta_font = self._load_font(24, bold=True)

        draw.rounded_rectangle((215, 42, width - 52, 176), radius=36, fill="#FFFDF7", outline="#FFFFFF", width=3)
        draw.text((250, 62), scene.title, font=title_font, fill="#111827")

        preview_words = "  |  ".join(scene.on_screen_text[:4]) if scene.on_screen_text else "English time"
        preview_lines = self._wrap_text_to_width(draw, preview_words, body_font, width - 390)
        preview_y = 128
        for line_index, line in enumerate(preview_lines[:2]):
            draw.text((252, preview_y + (line_index * 34)), line, font=body_font, fill="#334155")

        draw.rounded_rectangle((56, 46, 190, 100), radius=24, fill="#1D4ED8")
        draw.text((70, 58), "Kid Class", font=badge_font, fill="#FFFFFF")
        if request is not None:
            draw.rounded_rectangle((width - 332, 52, width - 54, 102), radius=24, fill="#EA580C")
            draw.text(
                (width - 308, 64),
                f"Aula {request.lesson_number}  |  Passo {request.step_number}",
                font=meta_font,
                fill="#FFFFFF",
            )

    def _draw_cards(self, draw: ImageDraw.ImageDraw, scene: LessonScene, width: int, height: int) -> None:
        detail_font = self._load_font(24, bold=False)
        for card in self.card_layout(scene, width, height):
            draw.rounded_rectangle(
                (card.left, card.top, card.left + card.width, card.top + card.height),
                radius=28,
                fill=card.fill,
                outline="#FFFFFF",
                width=4,
            )
            self._draw_card_title(draw, card.text.title(), x=card.left, y=card.top, card_width=card.width)
            if card.detail_text:
                draw.text((card.left + 24, card.top + 100), card.detail_text, font=detail_font, fill="#475569")

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
            detail_text = "Speak with me"

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
            )
            for index, word in enumerate(visible_cards)
        ]

    def _draw_dialogue_scene(self, draw: ImageDraw.ImageDraw, scene: LessonScene, width: int, height: int) -> None:
        label_font = self._load_font(24, bold=True)
        text_font = self._load_font(28, bold=False)
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
        panel_top = height - (206 if scene.teaching_mode == "dialogue" else 166)
        panel_right = width - 68
        panel_bottom = height - (62 if scene.teaching_mode == "dialogue" else 52)
        draw.rounded_rectangle(
            (panel_left, panel_top, panel_right, panel_bottom),
            radius=34,
            fill="#FFFDF7",
            outline="#FFFFFF",
            width=4,
        )

        panel_font = self._load_font(24, bold=False)
        text = self._narration_panel_text(scene)
        wrapped = self._wrap_text_to_width(draw, text, panel_font, panel_right - panel_left - 56)
        line_height = self._line_height(draw, panel_font) + 4
        start_y = panel_top + 20
        if scene.teaching_mode == "dialogue":
            badge_font = self._load_font(22, bold=True)
            draw.rounded_rectangle((panel_left + 24, panel_top + 18, panel_left + 270, panel_top + 58), radius=18, fill="#1D4ED8")
            draw.text((panel_left + 42, panel_top + 26), "Professor explica", font=badge_font, fill="#FFFFFF")
            start_y = panel_top + 72
        for line_index, line in enumerate(wrapped[:3]):
            draw.text((panel_left + 28, start_y + (line_index * line_height)), line, font=panel_font, fill="#0F172A")

    def _draw_footer(
        self,
        draw: ImageDraw.ImageDraw,
        width: int,
        height: int,
        scene_index: int,
        request: RenderRequest | None,
    ) -> None:
        footer_font = self._load_font(22, bold=False)
        draw.rounded_rectangle((36, height - 54, width - 36, height - 20), radius=16, fill="#0F172A")
        footer_text = f"Cena {scene_index:02d}  |  narracao automatica"
        if request is not None:
            footer_text = f"Aula {request.lesson_number}  |  Passo {request.step_number}  |  Cena {scene_index:02d}"
        draw.text(
            (56, height - 48),
            footer_text,
            font=footer_font,
            fill="#FFFFFF",
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
    ) -> None:
        max_width = card_width - 44
        for font_size in (34, 32, 30, 28, 26, 24, 22):
            font = self._load_font(font_size, bold=True)
            lines = self._wrap_text_to_width(draw, text, font, max_width)
            if len(lines) <= 2:
                line_height = self._line_height(draw, font)
                total_height = len(lines) * line_height
                start_y = y + 26 + max(0, (44 - total_height) // 2)
                for line_index, line in enumerate(lines):
                    draw.text((x + 22, start_y + (line_index * line_height)), line, font=font, fill="#0F172A")
                return

        fallback_font = self._load_font(20, bold=True)
        fallback_lines = self._wrap_text_to_width(draw, text, fallback_font, max_width)[:2]
        line_height = self._line_height(draw, fallback_font)
        for line_index, line in enumerate(fallback_lines):
            draw.text((x + 22, y + 26 + (line_index * line_height)), line, font=fallback_font, fill="#0F172A")

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

    def _hex_to_rgb(self, color: str) -> tuple[int, int, int]:
        color = color.lstrip("#")
        return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))
