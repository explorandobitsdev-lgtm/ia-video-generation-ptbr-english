from __future__ import annotations

import random
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.config import Settings
from app.schemas import LessonScene, RenderRequest


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
        wrapped = textwrap.fill(preview_words, width=42)
        draw.text((252, 128), wrapped, font=body_font, fill="#334155")

        draw.rounded_rectangle((56, 46, 190, 100), radius=24, fill="#1D4ED8")
        draw.text((78, 58), "Kid Class", font=badge_font, fill="#FFFFFF")
        if request is not None:
            draw.rounded_rectangle((width - 312, 52, width - 74, 102), radius=24, fill="#EA580C")
            draw.text(
                (width - 292, 64),
                f"Aula {request.lesson_number}  |  Passo {request.step_number}",
                font=meta_font,
                fill="#FFFFFF",
            )

    def _draw_cards(self, draw: ImageDraw.ImageDraw, scene: LessonScene, width: int, height: int) -> None:
        if scene.teaching_mode == "dialogue":
            self._draw_dialogue_scene(draw, scene, width, height)
            return

        detail_font = self._load_font(24, bold=False)
        cards = scene.vocabulary or scene.on_screen_text[:3]
        card_width = 244
        base_x = 220
        y = 250

        for index, word in enumerate(cards[:4]):
            x = base_x + index * 250
            card_color = ["#FFFFFF", "#FEF3C7", "#DBEAFE", "#FCE7F3"][index % 4]
            draw.rounded_rectangle((x, y, x + card_width, y + 150), radius=28, fill=card_color, outline="#FFFFFF", width=4)
            self._draw_card_title(draw, word.title(), x=x, y=y, card_width=card_width)
            draw.text((x + 24, y + 100), "Speak with me", font=detail_font, fill="#475569")

    def _draw_dialogue_scene(self, draw: ImageDraw.ImageDraw, scene: LessonScene, width: int, height: int) -> None:
        label_font = self._load_font(24, bold=True)
        text_font = self._load_font(28, bold=False)
        english_lines = [segment for segment in scene.narration if segment.language == "en-US"][:2]
        if len(english_lines) < 2:
            english_lines = [segment for segment in scene.narration[:2]]

        bubble_specs = [
            (230, 246, width - 220, 356, "#FFFDF7", "#1D4ED8"),
            (290, 388, width - 150, 516, "#FEF3C7", "#EA580C"),
        ]

        for index, segment in enumerate(english_lines[:2]):
            left, top, right, bottom, fill_color, accent = bubble_specs[index]
            draw.rounded_rectangle((left, top, right, bottom), radius=28, fill=fill_color, outline="#FFFFFF", width=4)
            speaker_label = "Professor" if segment.speaker == "teacher" else "Aluno"
            draw.rounded_rectangle((left + 20, top + 16, left + 160, top + 56), radius=18, fill=accent)
            draw.text((left + 38, top + 24), speaker_label, font=label_font, fill="#FFFFFF")
            wrapped = self._wrap_text_to_width(draw, segment.text, text_font, (right - left) - 48)
            line_height = self._line_height(draw, text_font) + 4
            start_y = top + 72
            for line_index, line in enumerate(wrapped[:3]):
                draw.text((left + 24, start_y + (line_index * line_height)), line, font=text_font, fill="#0F172A")

        cards = scene.vocabulary[:3]
        card_width = 228
        gap = 18
        total_width = (len(cards) * card_width) + (max(len(cards) - 1, 0) * gap)
        start_x = int((width - total_width) / 2)
        for index, word in enumerate(cards):
            card_left = start_x + (index * (card_width + gap))
            card_top = 548
            card_bottom = 646
            draw.rounded_rectangle(
                (card_left, card_top, card_left + card_width, card_bottom),
                radius=22,
                fill="#FFFFFF",
                outline="#FFFFFF",
                width=3,
            )
            self._draw_card_title(draw, word.title(), x=card_left, y=card_top + 2, card_width=card_width)

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
