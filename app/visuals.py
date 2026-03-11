from __future__ import annotations

from dataclasses import dataclass
import math
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
        if include_companion:
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

        draw.rounded_rectangle((panel_left, panel_top, panel_right, panel_bottom), radius=36, fill="#FFFDF7", outline="#FFFFFF", width=3)
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
        draw.text((title_x, 62), title_text, font=title_font, fill="#111827")

        preview_words = "  |  ".join(scene.on_screen_text[:4]) if scene.on_screen_text else "English time"
        preview_max_width = title_right - title_x
        preview_lines = self._wrap_text_to_width(draw, preview_words, body_font, preview_max_width)
        preview_y = 128
        for line_index, line in enumerate(preview_lines[:2]):
            draw.text((title_x + 2, preview_y + (line_index * 34)), line, font=body_font, fill="#334155")

    def _draw_cards(self, draw: ImageDraw.ImageDraw, scene: LessonScene, width: int, height: int) -> None:
        detail_font = self._load_font(22, bold=False)
        for card in self.card_layout(scene, width, height):
            draw.rounded_rectangle(
                (card.left, card.top, card.left + card.width, card.top + card.height),
                radius=28,
                fill=card.fill,
                outline="#FFFFFF",
                width=4,
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
                draw.text((card.left + 24, detail_y), card.detail_text, font=detail_font, fill="#475569")

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
        panel_top = height - (258 if scene.teaching_mode == "dialogue" else 214)
        panel_right = width - 68
        panel_bottom = height - 88
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
