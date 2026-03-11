from pathlib import Path

from PIL import Image, ImageChops

from app.config import Settings
from app.job_store import JobStore
from app.narration import NarrationCue
from app.narration import NarrationService
from app.planner import LessonPlanner
from app.script_writer import ScriptWriter
from app.schemas import JobStatus, RenderRequest
from app.video import VideoComposer
from app.visuals import TemplateVisualRenderer


def build_settings(tmp_path: Path) -> Settings:
    return Settings(
        use_ollama=False,
        data_dir=tmp_path / "data",
        jobs_dir=tmp_path / "data" / "jobs",
        outputs_dir=tmp_path / "data" / "outputs",
        tmp_dir=tmp_path / "data" / "tmp",
        piper_download_dir=tmp_path / "data" / "piper",
    )


def test_fallback_plan_hits_requested_duration(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    planner = LessonPlanner(settings)
    request = RenderRequest(
        prompt="Crie um video de 5 minutos sobre cores em ingles para criancas.",
        duration_minutes=5,
    )

    plan = planner.generate(request)

    assert len(plan.scenes) == 12
    assert sum(scene.duration_seconds for scene in plan.scenes) == 300
    languages = {segment.language for scene in plan.scenes for segment in scene.narration}
    assert {"pt-BR", "en-US"}.issubset(languages)


def test_fallback_plan_supports_short_video(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    planner = LessonPlanner(settings)
    request = RenderRequest(
        prompt="Crie um video de 1 minuto sobre cumprimentos em ingles para criancas.",
        duration_minutes=1,
    )

    plan = planner.generate(request)

    assert len(plan.scenes) == 4
    assert sum(scene.duration_seconds for scene in plan.scenes) == 60


def test_render_request_normalizes_lesson_name() -> None:
    request = RenderRequest(
        prompt="Crie um video de 1 minuto sobre cores em ingles para criancas.",
        lesson_name="  Aula   de cores  ",
    )

    assert request.lesson_name == "Aula de cores"


def test_fallback_plan_covers_numbers_one_to_ten_in_short_video(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    planner = LessonPlanner(settings)
    request = RenderRequest(
        prompt=(
            "Crie um video de 1 minuto sobre contar, ensine os numeros de 1 a 10 em ingles "
            "para criancas de 5 a 8 anos, com narracao em pt-BR mesclando palavras e frases curtas em ingles."
        ),
        duration_minutes=1,
    )

    plan = planner.generate(request)
    taught_words = [word for scene in plan.scenes for word in scene.vocabulary]

    assert plan.vocabulary[:10] == ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
    assert set(plan.vocabulary[:10]).issubset(set(taught_words))
    assert max(len(scene.vocabulary) for scene in plan.scenes) <= 3


def test_number_cards_show_numeric_badges(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    planner = LessonPlanner(settings)
    renderer = TemplateVisualRenderer(settings)
    request = RenderRequest(
        prompt="Crie um video de 1 minuto sobre contar, ensine os numeros de 1 a 10 em ingles para criancas.",
        duration_minutes=1,
    )

    plan = planner.generate(request)
    cards = renderer.card_layout(plan.scenes[0], settings.video_width, settings.video_height)

    assert [card.badge_text for card in cards] == ["1", "2", "3"]


def test_render_scene_shows_lesson_theme_and_removes_footer_bar(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    planner = LessonPlanner(settings)
    renderer = TemplateVisualRenderer(settings)
    request = RenderRequest(
        prompt="Crie um video de 1 minuto sobre contar em ingles para criancas.",
        duration_minutes=1,
        lesson_name="  Numbers  ",
    )

    plan = planner.generate(request)
    output_path = tmp_path / "scene.png"
    renderer.render_scene(plan.scenes[0], output_path, scene_index=1, request=request)

    image = Image.open(output_path)
    top_right_pixel = image.getpixel((settings.video_width - 90, 82))
    bottom_pixel = image.getpixel((80, settings.video_height - 30))

    assert top_right_pixel == (251, 146, 60)
    assert bottom_pixel != (15, 23, 42)


def test_dialogue_scene_renders_two_characters_with_exchange_bubbles(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    planner = LessonPlanner(settings)
    renderer = TemplateVisualRenderer(settings)
    request = RenderRequest(
        prompt="Crie um video de 2 minutos sobre saudacoes em ingles bom dia, boa tarde e boa noite para criancas.",
        duration_minutes=2,
    )

    plan = planner.generate(request)
    output_path = tmp_path / "dialogue-scene.png"
    renderer.render_scene(plan.scenes[2], output_path, scene_index=3, request=request)

    image = Image.open(output_path)

    assert image.getpixel((372, 770)) == (29, 78, 216)
    assert image.getpixel((1496, 760)) == (249, 115, 22)
    assert image.getpixel((520, 520)) == (255, 253, 247)
    assert image.getpixel((1180, 570)) == (254, 243, 199)


def test_scene_companion_frames_are_static(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    planner = LessonPlanner(settings)
    renderer = TemplateVisualRenderer(settings)
    request = RenderRequest(
        prompt="Crie um video de 1 minuto sobre contar em ingles para criancas.",
        duration_minutes=1,
        lesson_name="Numbers",
    )

    plan = planner.generate(request)
    frame_paths = renderer.render_scene_animation(
        plan.scenes[0],
        tmp_path / "teacher-motion",
        scene_index=1,
        request=request,
        frame_count=6,
    )

    first_frame = Image.open(frame_paths[0])
    fourth_frame = Image.open(frame_paths[3])
    diff = ImageChops.difference(first_frame, fourth_frame)

    assert len(frame_paths) == 6
    assert diff.getbbox() is None


def test_narration_defaults_are_slightly_slower(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    narration = NarrationService(settings)

    teacher_pt = narration._build_synthesis_config("pt-BR", request=None, speaker="teacher")
    teacher_en = narration._build_synthesis_config("en-US", request=None, speaker="teacher")
    animated_en = narration._build_synthesis_config(
        "en-US",
        request=RenderRequest(
            prompt="Crie um video de 1 minuto sobre contar em ingles para criancas.",
            duration_minutes=1,
            narration_style="animated",
        ),
        speaker="teacher",
    )

    assert teacher_pt.length_scale == 1.10
    assert teacher_en.length_scale == 1.08
    assert animated_en.length_scale == 1.05
    assert settings.narration_gap_ms == 210
    assert settings.sentence_gap_ms == 255


def test_vocabulary_and_echo_scenes_repeat_words_after_prompt(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    planner = LessonPlanner(settings)
    request = RenderRequest(
        prompt="Crie um video de 1 minuto sobre contar, ensine os numeros de 1 a 10 em ingles para criancas.",
        duration_minutes=1,
    )

    plan = planner.generate(request)

    assert plan.scenes[1].narration[-1].language == "en-US"
    assert "four. five. six." in plan.scenes[1].narration[-1].text.lower()
    assert plan.scenes[2].narration[-1].language == "en-US"
    assert "seven. eight." in plan.scenes[2].narration[-1].text.lower()


def test_fallback_plan_uses_requested_greetings_from_prompt(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    planner = LessonPlanner(settings)
    request = RenderRequest(
        prompt=(
            "Crie um video de 2 minutos sobre saudações em ingles bom dia, "
            "boa tarde e boa noite para criancas de 5 a 8 anos."
        ),
        duration_minutes=2,
    )

    plan = planner.generate(request)

    assert plan.vocabulary[:3] == ["good morning", "good afternoon", "good night"]
    assert "bom dia" in plan.scenes[0].narration[0].text.lower()
    assert "good morning" in plan.scenes[0].narration[1].text.lower()
    assert any(segment.speaker == "student" for segment in plan.scenes[2].narration)


def test_fallback_plan_picks_pronouns_topic_from_prompt(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    planner = LessonPlanner(settings)
    request = RenderRequest(
        prompt=(
            "Crie um video de 1 minutos sobre pronomes em ingles para criancas de 5 a 8 anos, "
            "com narracao em pt-BR mesclando palavras e frases curtas em ingles."
        ),
        duration_minutes=1,
    )

    plan = planner.generate(request)

    assert plan.title.startswith("Pronomes em Ingl")
    assert plan.vocabulary[:6] == ["i", "you", "he", "she", "we", "they"]
    assert "pronomes pessoais simples" in plan.summary.lower()


def test_auto_mode_uses_local_fast_path_for_supported_topics(tmp_path: Path, monkeypatch) -> None:
    settings = Settings(
        use_ollama=True,
        ollama_base_url="http://invalid-host-for-test:11434",
        data_dir=tmp_path / "data",
        jobs_dir=tmp_path / "data" / "jobs",
        outputs_dir=tmp_path / "data" / "outputs",
        tmp_dir=tmp_path / "data" / "tmp",
        piper_download_dir=tmp_path / "data" / "piper",
    )
    planner = LessonPlanner(settings)
    request = RenderRequest(
        prompt="Crie um video de 1 minutos sobre pronomes em ingles para criancas de 5 a 8 anos.",
        duration_minutes=1,
        planner_mode="auto",
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Ollama nao deveria ser chamado para tema local suportado")

    monkeypatch.setattr("app.planner.httpx.post", fail_if_called)

    plan = planner.generate(request)

    assert plan.title.startswith("Pronomes em Ingl")


def test_fallback_plan_picks_presentations_topic_from_prompt(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    planner = LessonPlanner(settings)
    request = RenderRequest(
        prompt=(
            "Crie um video de 1 minuto sobre aprensetações meu nome é, como você chama, "
            "eeu sou bruno muito prazer em ingles para criancas de 5 a 8 anos."
        ),
        duration_minutes=1,
    )

    plan = planner.generate(request)

    assert plan.title == "Apresentações em Inglês para Crianças"
    assert plan.vocabulary[:4] == ["my name is", "what is your name", "i am bruno", "nice to meet you"]
    assert "apresentações" in plan.scenes[0].narration[0].text.lower()
    assert "my name is bruno" in plan.scenes[1].narration[1].text.lower()
    assert "what is your name" in plan.scenes[2].narration[1].text.lower()


def test_greetings_dialogue_scene_explains_the_exchange_in_portuguese(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    planner = LessonPlanner(settings)
    request = RenderRequest(
        prompt="Crie um video de 2 minutos sobre saudacoes em ingles bom dia, boa tarde e boa noite para criancas.",
        duration_minutes=2,
    )

    plan = planner.generate(request)
    scene = plan.scenes[2]
    teacher_pt_lines = [
        segment.text.lower()
        for segment in scene.narration
        if segment.language == "pt-BR" and segment.speaker == "teacher"
    ]

    assert any("como você está" in line for line in teacher_pt_lines)
    assert any("estou bem, obrigado" in line for line in teacher_pt_lines)


def test_video_highlight_uses_rendered_card_geometry(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    planner = LessonPlanner(settings)
    composer = VideoComposer(settings)
    request = RenderRequest(
        prompt="Crie um video de 2 minutos sobre saudacoes em ingles bom dia, boa tarde e boa noite para criancas.",
        duration_minutes=2,
    )

    plan = planner.generate(request)
    scene = plan.scenes[1]
    card = composer.visual_renderer.card_layout(scene, settings.video_width, settings.video_height)[0]

    filter_chain = composer._build_scene_filter(
        scene=scene,
        duration=float(scene.duration_seconds),
        animated_clip=False,
        cues=[NarrationCue(label=scene.vocabulary[0], start=1.0, end=2.0)],
        subtitle_path=None,
    )

    assert f"x={card.left - 8}" in filter_chain
    assert f"y={card.top - 8}" in filter_chain
    assert f"w={card.width + 16}" in filter_chain
    assert f"h={card.height + 16}" in filter_chain


def test_job_store_round_trip(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    store = JobStore(settings)
    job = store.create(
        RenderRequest(
            prompt="Crie um video de 5 minutos sobre animais em ingles para criancas.",
            duration_minutes=5,
        )
    )

    loaded = store.load(job.job_id)

    assert loaded.job_id == job.job_id
    assert loaded.status == JobStatus.queued


def test_script_writer_blocks_and_sync(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    planner = LessonPlanner(settings)
    writer = ScriptWriter()
    request = RenderRequest(
        prompt="Crie um video de 5 minutos sobre cores em ingles para criancas.",
        duration_minutes=5,
        narration_style="natural",
    )

    plan = planner.generate(request)
    synced_plan, blocks = writer.prepare(plan, request)

    assert len(blocks) == len(synced_plan.scenes)
    assert all(len(block.text) <= 500 for block in blocks)
    assert sum(scene.duration_seconds for scene in synced_plan.scenes) == 300
    assert "\n\n" in writer.build_script_text(blocks)
