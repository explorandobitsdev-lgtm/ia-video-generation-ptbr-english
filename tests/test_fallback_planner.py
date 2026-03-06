from pathlib import Path

from app.config import Settings
from app.job_store import JobStore
from app.narration import NarrationCue
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
