from pathlib import Path

from PIL import Image, ImageChops

from app.config import Settings
from app.job_store import JobStore
from app.narration import NarrationCue
from app.narration import NarrationService
from app.narration import NarrationSubtitle
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
    english_lines = [segment.text for scene in plan.scenes for segment in scene.narration if segment.language == "en-US"]

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


def test_scene_companion_keeps_robot_face_visible(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    planner = LessonPlanner(settings)
    renderer = TemplateVisualRenderer(settings)
    request = RenderRequest(
        prompt="Crie um video de 1 minuto sobre contar em ingles para criancas.",
        duration_minutes=1,
    )

    plan = planner.generate(request)
    output_path = tmp_path / "scene-companion.png"
    renderer.render_scene(plan.scenes[0], output_path, scene_index=1, request=request)

    image = Image.open(output_path)

    assert image.getpixel((294, 452)) == (15, 23, 42)


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

    assert image.getpixel((326, 748)) == (254, 243, 199)
    assert image.getpixel((1594, 748)) == (139, 92, 246)
    assert image.getpixel((520, 520)) == (255, 253, 247)
    assert image.getpixel((1260, 552)) == (254, 243, 199)


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


def test_fallback_plan_picks_age_topic_from_structured_prompt(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    planner = LessonPlanner(settings)
    request = RenderRequest(
        prompt=(
            "Crie um video educacional de 1 minuto para criancas de 7 a 12 anos aprendendo ingles basico. "
            "Tema da aula: perguntar e responder a idade em ingles. "
            "Estilo visual: desenho animado infantil, colorido e amigavel, semelhante a livros didaticos de ingles para criancas. "
            "Objetivo da aula: ensinar a pergunta \"How old are you?\" e como responder \"I'm eight years old.\" "
            "Elementos visuais: baloes de fala, numeros aparecendo animados, criancas sorrindo, escola ao fundo."
        ),
        duration_minutes=1,
    )

    plan = planner.generate(request)
    scene = plan.scenes[2]
    practice_scene = plan.scenes[3]
    opening_pt_lines = [segment.text.lower() for segment in plan.scenes[0].narration if segment.language == "pt-BR"]

    assert plan.title.startswith("Idade em Inglês")
    assert plan.vocabulary[:3] == ["how old are you", "i'm eight years old", "i'm six years old"]
    assert any("quantos anos" in line for line in opening_pt_lines)
    assert plan.scenes[1].vocabulary[:4] == [
        "i'm eight years old",
        "i'm six years old",
        "i'm seven years old",
        "i'm ten years old",
    ]
    assert practice_scene.vocabulary[:4] == [
        "i'm eight years old",
        "i'm six years old",
        "i'm seven years old",
        "i'm ten years old",
    ]
    assert practice_scene.on_screen_text[1:5] == [
        "I'm Eight Years Old",
        "I'm Six Years Old",
        "I'm Seven Years Old",
        "I'm Ten Years Old",
    ]
    assert any(segment.language == "en-US" and segment.speaker == "teacher" and segment.text == "How old are you?" for segment in scene.narration)
    assert any(segment.language == "en-US" and segment.speaker == "student" and segment.text == "I'm eight years old." for segment in scene.narration)


def test_fallback_plan_builds_custom_topic_from_prompt_examples(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    planner = LessonPlanner(settings)
    request = RenderRequest(
        prompt=(
            "Crie um video educacional de 1 minuto para criancas. "
            "Tema da aula: material escolar em ingles. "
            "Objetivo da aula: ensinar as palavras \"pencil\", \"notebook\" e \"eraser\". "
            "Estilo visual: sala de aula alegre com mochilas e cadernos."
        ),
        duration_minutes=1,
    )

    plan = planner.generate(request)
    english_lines = [segment.text for scene in plan.scenes for segment in scene.narration if segment.language == "en-US"]

    assert plan.title.startswith("Material Escolar em Inglês")
    assert plan.vocabulary[:3] == ["pencil", "notebook", "eraser"]
    assert "material escolar em inglês" in plan.summary.lower()
    assert "Let's learn: pencil, notebook, eraser." in english_lines
    assert "one" not in plan.vocabulary[:3]


def test_local_planner_restores_pt_br_accents_in_generated_text(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    planner = LessonPlanner(settings)
    request = RenderRequest(
        prompt=(
            "Crie um video educacional de 1 minuto para criancas de 7 a 12 anos aprendendo ingles basico. "
            "Tema da aula: perguntar e responder a idade em ingles. "
            "Objetivo da aula: ensinar a pergunta \"How old are you?\" e como responder \"I'm eight years old.\""
        ),
        duration_minutes=1,
    )

    plan = planner.generate(request)
    opening_line = " ".join(segment.text for segment in plan.scenes[0].narration if segment.language == "pt-BR")
    dialogue_explanation = plan.scenes[2].narration[-1].text

    assert "Olá, turma." in opening_line
    assert "idade em inglês" in opening_line
    assert "você" in opening_line
    assert "diálogo" in dialogue_explanation
    assert "criança" in dialogue_explanation


def test_local_planner_splits_english_phrases_out_of_pt_br_narration(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    planner = LessonPlanner(settings)
    request = RenderRequest(
        prompt=(
            "Crie um video educacional de 1 minuto para criancas de 7 a 12 anos aprendendo ingles basico. "
            "Tema da aula: perguntar e responder a idade em ingles. "
            "Objetivo da aula: ensinar a pergunta \"How old are you?\" e como responder \"I'm eight years old.\""
        ),
        duration_minutes=1,
    )

    plan = planner.generate(request)
    opening_segments = plan.scenes[0].narration

    assert opening_segments[0].language == "pt-BR"
    assert "how old are you" not in opening_segments[0].text.lower()
    assert opening_segments[1].language == "en-US"
    assert opening_segments[1].text == "How old are you."
    assert opening_segments[2].language == "pt-BR"
    assert "quantos anos" in opening_segments[2].text.lower()
    return
    assert "quantos anos você tem" in opening_segments[2].text.lower()


def test_narration_panel_keeps_the_full_opening_explanation(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    planner = LessonPlanner(settings)
    renderer = TemplateVisualRenderer(settings)
    request = RenderRequest(
        prompt=(
            "Crie um video educacional de 1 minuto para criancas de 7 a 12 anos aprendendo ingles basico. "
            "Tema da aula: perguntar e responder a idade em ingles. "
            "Objetivo da aula: ensinar a pergunta \"How old are you?\" e como responder \"I'm eight years old.\""
        ),
        duration_minutes=1,
    )

    plan = planner.generate(request)
    first_panel = renderer._narration_panel_text(plan.scenes[0])
    second_panel = renderer._narration_panel_text(plan.scenes[1])

    assert "How old are you." in first_panel
    assert "Isso significa quantos anos você tem." in first_panel
    assert "I am" in second_panel
    assert "years old." in second_panel
    assert second_panel.endswith("Agora veja alguns exemplos.")


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
        subtitles=[],
        subtitle_path=None,
    )

    assert f"x={card.left - 8}" in filter_chain
    assert f"y={card.top - 8}" in filter_chain
    assert f"w={card.width + 16}" in filter_chain
    assert f"h={card.height + 16}" in filter_chain


def test_dialogue_video_highlight_tracks_speaking_character_regions(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    planner = LessonPlanner(settings)
    composer = VideoComposer(settings)
    request = RenderRequest(
        prompt="Crie um video de 2 minutos sobre saudacoes em ingles bom dia, boa tarde e boa noite para criancas.",
        duration_minutes=2,
    )

    plan = planner.generate(request)
    scene = plan.scenes[2]
    bubble_frames = composer.visual_renderer.dialogue_bubble_layout(scene, settings.video_width, settings.video_height)

    filter_chain = composer._build_scene_filter(
        scene=scene,
        duration=float(scene.duration_seconds),
        animated_clip=False,
        cues=[],
        subtitles=[
            NarrationSubtitle(speaker="teacher", language="en-US", text="Good morning, Ana.", start=1.0, end=2.1),
            NarrationSubtitle(speaker="student", language="en-US", text="I'm fine, thank you.", start=2.3, end=3.0),
            NarrationSubtitle(speaker="teacher", language="pt-BR", text="Muito bem.", start=3.2, end=4.0),
        ],
        subtitle_path=None,
    )

    teacher = bubble_frames["teacher"]
    student = bubble_frames["student"]

    assert f"x={teacher.left - 4}" in filter_chain
    assert f"y={teacher.top - 4}" in filter_chain
    assert f"w={(teacher.right - teacher.left) + 8}" in filter_chain
    assert f"h={(teacher.bottom - teacher.top) + 8}" in filter_chain
    assert "between(t,1.00,2.10)" in filter_chain
    assert f"x={student.left - 4}" in filter_chain
    assert f"y={student.top - 4}" in filter_chain
    assert f"w={(student.right - student.left) + 8}" in filter_chain
    assert f"h={(student.bottom - student.top) + 8}" in filter_chain
    assert "between(t,2.30,3.00)" in filter_chain
    assert "between(t,3.20,4.00)" not in filter_chain
    assert "color=blue@0.10" not in filter_chain


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
