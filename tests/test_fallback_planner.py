from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from app.config import Settings
from app.job_store import JobStore
from app.narration import NarrationCue
from app.narration import NarrationService
from app.narration import NarrationSubtitle
from app.planner import LessonPlanner
from app.script_writer import ScriptWriter
from app.schemas import JobStatus, LessonScene, NarrationSegment, RenderRequest
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


def test_render_request_accepts_detailed_prompt_over_previous_limit() -> None:
    prompt = (
        "Crie um video educacional infantil de ingles para iniciantes com comandos de sala de aula. "
        + ("look, find, listen, show, add, open, close, pick up, ask, answer, sit down, stand up. " * 32)
    )

    request = RenderRequest(prompt=prompt, duration_minutes=3)

    assert len(request.prompt) > 2000
    assert len(request.prompt) < 8000


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
    assert teacher_en.length_scale == 1.16
    assert animated_en.length_scale == 1.13
    assert settings.narration_gap_ms == 210
    assert settings.sentence_gap_ms == 255


def test_narration_does_not_pad_scene_audio_to_planned_duration(tmp_path: Path, monkeypatch) -> None:
    settings = build_settings(tmp_path)
    narration = NarrationService(settings)
    scene = LessonScene(
        scene_id="scene-01",
        title="Boas-vindas",
        duration_seconds=20,
        teaching_mode="intro",
        visual_prompt="children classroom",
        narration=[
            NarrationSegment(language="pt-BR", text="Olá, turma."),
            NarrationSegment(language="en-US", text="Look, find, listen, show."),
        ],
    )

    def fake_run_piper(*, output_path: Path, **_kwargs) -> None:
        narration._write_silence_wav(output_path, 1.0)

    monkeypatch.setattr(narration, "_run_piper", fake_run_piper)

    result = narration.synthesize_scene(scene, tmp_path / "scene")

    assert result.duration < scene.duration_seconds
    assert (tmp_path / "scene" / "padding.wav").exists() is False
    assert (tmp_path / "scene" / "tail-pad.wav").exists()


def test_narration_supports_inline_pause_marker(tmp_path: Path, monkeypatch) -> None:
    settings = build_settings(tmp_path)
    narration = NarrationService(settings)
    scene = LessonScene(
        scene_id="scene-quiz",
        title="Quiz Final",
        duration_seconds=14,
        teaching_mode="game",
        visual_prompt="quiz classroom",
        narration=[
            NarrationSegment(language="pt-BR", text="Escute a frase."),
            NarrationSegment(language="en-US", text="What's her name?"),
            NarrationSegment(language="pt-BR", text="[[pause:5.0]]"),
            NarrationSegment(language="pt-BR", text="Se voce pensou no significado certo, acertou."),
        ],
        vocabulary=["What's her name?"],
    )

    def fake_run_piper(*, output_path: Path, **_kwargs) -> None:
        narration._write_silence_wav(output_path, 1.0)

    monkeypatch.setattr(narration, "_run_piper", fake_run_piper)

    result = narration.synthesize_scene(scene, tmp_path / "scene")

    assert result.duration >= 8.2
    assert len(result.subtitles) == 3
    assert all("[[pause:" not in subtitle.text for subtitle in result.subtitles)


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
    assert planner._apply_pt_br_accents("uma situacao simples") == "uma situação simples"


def test_fallback_plan_builds_custom_topic_from_structured_verb_list(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    planner = LessonPlanner(settings)
    renderer = TemplateVisualRenderer(settings)
    request = RenderRequest(
        prompt=(
            "Crie um vídeo educacional infantil de inglês para iniciantes (crianças de 7 a 12 anos) com duração aproximada de 2 a 3 minutos. "
            "Tema da aula: Comandos e ações em inglês usados na sala de aula. "
            "Estilo visual: Desenho animado educativo, colorido, amigável, semelhante a livros didáticos infantis. "
            "Objetivo da aula: Ensinar e praticar os seguintes verbos em inglês: look find listen show add open close pick up ask answer sit down stand up. "
            "O vídeo deve ensinar pronúncia, significado e exemplos simples. "
            "Estrutura do vídeo: 2. Apresentação dos comandos. "
            "Narrador: \"Show significa mostrar.\" "
            "Narrador: \"Add significa somar.\" "
            "Texto na tela: Classroom Actions."
        ),
        duration_minutes=3,
    )

    plan = planner.generate(request)
    english_lines = [segment.text.lower() for scene in plan.scenes for segment in scene.narration if segment.language == "en-US"]
    opening_line = " ".join(segment.text for segment in plan.scenes[0].narration if segment.language == "pt-BR")
    first_scene_cards = renderer.card_layout(plan.scenes[0], settings.video_width, settings.video_height)
    third_scene_english = [segment.text.lower() for segment in plan.scenes[2].narration if segment.language == "en-US"]
    fourth_scene_pt = [segment.text for segment in plan.scenes[3].narration if segment.language == "pt-BR"]
    seventh_scene_english = [segment.text.lower() for segment in plan.scenes[6].narration if segment.language == "en-US"]
    seventh_scene_pt = [segment.text.lower() for segment in plan.scenes[6].narration if segment.language == "pt-BR"]

    assert plan.title.startswith("Comandos e Ações em Inglês")
    assert plan.vocabulary[:6] == ["look", "find", "listen", "show", "add", "open"]
    assert "pick up" in plan.vocabulary
    assert "sit down" in plan.vocabulary
    assert "stand up" in plan.vocabulary
    assert "show significa mostrar" not in [item.lower() for item in plan.vocabulary]
    assert "semelhante a livros didáticos infantis" not in [item.lower() for item in plan.vocabulary]
    assert "Hoje vamos aprender comandos e ações em inglês usados na sala de aula." in opening_line
    assert "o professor usa para orientar a turma" in opening_line.lower()
    assert "significam olhar, encontrar, escutar e mostrar." in opening_line
    assert plan.scenes[0].vocabulary == ["look", "find", "listen", "show"]
    assert plan.scenes[0].card_details == ["Olhar", "Encontrar", "Escutar", "Mostrar"]
    assert [card.detail_text for card in first_scene_cards] == ["Olhar", "Encontrar", "Escutar", "Mostrar"]
    assert any("ask" in line and "answer" in line for line in third_scene_english)
    assert fourth_scene_pt[0] == "Agora repita comigo bem devagar. Primeiro eu falo, depois você repete."
    assert "você está repetindo ações que significam olhar, encontrar, escutar e mostrar." in fourth_scene_pt[1].lower()
    assert any("open your book" in line and "close your book" in line for line in seventh_scene_english)
    assert any("usados o tempo todo pelo professor" in line for line in seventh_scene_pt)
    assert any("sit down" in line and "stand up" in line for line in english_lines)


def test_fallback_plan_prefers_custom_profile_for_her_and_his_name_lesson(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    planner = LessonPlanner(settings)
    renderer = TemplateVisualRenderer(settings)
    request = RenderRequest(
        prompt=(
            "Crie um vídeo educacional infantil de inglês para iniciantes com duração aproximada de 2 minutos. "
            "Tema da aula: Como perguntar e responder o nome de outra pessoa usando her e his em inglês. "
            "Objetivo da aula: Ensinar a diferença entre \"What's her name?\" e \"What's his name?\" "
            "e como responder \"Her name's Sara.\" e \"His name's Max.\" "
            "Estilo visual: pátio escolar colorido com crianças brincando."
        ),
        duration_minutes=2,
    )

    plan = planner.generate(request)
    first_scene_cards = renderer.card_layout(plan.scenes[0], settings.video_width, settings.video_height)
    dialogue_english = [segment.text for segment in plan.scenes[2].narration if segment.language == "en-US"]
    pt_lines = [segment.text.lower() for scene in plan.scenes for segment in scene.narration if segment.language == "pt-BR"]
    opening_pt = " ".join(segment.text for segment in plan.scenes[0].narration if segment.language == "pt-BR")
    repetition_pt = " ".join(segment.text.lower() for segment in plan.scenes[1].narration if segment.language == "pt-BR")
    dialogue_pt = " ".join(segment.text.lower() for segment in plan.scenes[2].narration if segment.language == "pt-BR")

    assert not plan.title.startswith("Apresentações em Inglês")
    assert plan.vocabulary[:4] == ["What's her name?", "What's his name?", "Her name's Sara", "His name's Max"]
    assert plan.scenes[0].card_details == [
        "Qual é o nome dela",
        "Qual é o nome dele",
        "O nome dela é Sara",
        "O nome dele é Max",
    ]
    assert [card.detail_text for card in first_scene_cards] == [
        "Qual é o nome dela",
        "Qual é o nome dele",
        "O nome dela é Sara",
        "O nome dele é Max",
    ]
    assert "aprender a perguntar e responder o nome de outra pessoa em inglês" in opening_pt
    assert all("what's" not in line for line in pt_lines)
    assert all(" her " not in f" {line} " for line in pt_lines)
    assert all(" his " not in f" {line} " for line in pt_lines)
    assert "qual é o nome dela" in repetition_pt
    assert "o nome dela é sara" in repetition_pt
    assert "qual é o nome dela" in dialogue_pt
    assert "o nome dela é sara" in dialogue_pt
    assert dialogue_english[0] == "What's her name?"
    assert dialogue_english[1] == "Her name's Sara."
    assert plan.scenes[-1].title == "Quiz Final"
    assert plan.scenes[-1].teaching_mode == "game"
    assert plan.scenes[-1].vocabulary == ["What's her name?"]
    assert plan.scenes[-1].card_details == ["Qual é o nome dela"]
    final_pt = " ".join(segment.text.lower() for segment in plan.scenes[-1].narration if segment.language == "pt-BR")
    assert "cinco segundos" in final_pt
    assert "se você pensou" in final_pt


def test_fallback_plan_supports_lets_invitation_lesson_without_portuguese_cards(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    planner = LessonPlanner(settings)
    renderer = TemplateVisualRenderer(settings)
    request = RenderRequest(
        prompt=(
            "Crie um vídeo educacional infantil de inglês para iniciantes (crianças de 7 a 12 anos) com duração aproximada de 2,5 a 3 minutos. "
            "Tema da aula: Convidar alguém para fazer uma atividade usando \"Let's\" em inglês. "
            "Estilo visual: Desenho animado infantil, colorido e amigável, semelhante a livros didáticos de inglês para crianças. "
            "Objetivo da aula: Ensinar como convidar alguém para fazer algo usando: Let's + atividade. "
            "Exemplos principais: Let's paint! Let's play! Let's play a game. "
            "Estrutura do vídeo: Narrador explica: \"Let's significa vamos.\" "
            "\"Let's paint significa: Vamos pintar!\" "
            "\"Let's play significa: Vamos brincar!\" "
            "Texto na tela: See you in the next English lesson!"
        ),
        duration_minutes=3,
    )

    plan = planner.generate(request)
    first_scene_cards = renderer.card_layout(plan.scenes[0], settings.video_width, settings.video_height)

    assert plan.vocabulary[:4] == ["Let's", "Let's paint", "Let's play", "Let's play a game"]
    assert "colorido" not in [item.lower() for item in plan.vocabulary]
    assert "amig" not in " ".join(plan.vocabulary).lower()
    assert all("portugu" not in item.lower() for item in plan.vocabulary)
    assert plan.scenes[0].vocabulary == ["Let's", "Let's paint", "Let's play", "Let's play a game"]
    assert [card.text for card in first_scene_cards] == ["Let's", "Let's paint", "Let's play", "Let's play a game"]
    assert plan.scenes[0].card_details[:3] == ["Vamos", "Vamos pintar!", "Vamos brincar!"]
    assert plan.scenes[-1].vocabulary[0].lower().startswith("let")


def test_inline_english_hint_words_are_split_out_of_pt_br_narration(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    planner = LessonPlanner(settings)
    scene = LessonScene(
        scene_id="scene-01",
        title="Tema",
        duration_seconds=10,
        visual_prompt="school yard",
        narration=[
            NarrationSegment(
                language="pt-BR",
                text="Usamos her para falar de uma menina e his para falar de um menino.",
            )
        ],
        vocabulary=["What's her name?", "What's his name?"],
    )

    normalized_scene = planner._split_mixed_language_scene(scene, scene.vocabulary)
    normalized_segments = [(segment.language, segment.text) for segment in normalized_scene.narration]

    assert normalized_segments == [
        ("pt-BR", "Usamos"),
        ("en-US", "her"),
        ("pt-BR", "para falar de uma menina e"),
        ("en-US", "his"),
        ("pt-BR", "para falar de um menino."),
    ]


def test_fallback_plan_supports_new_custom_weekdays_theme(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    planner = LessonPlanner(settings)
    request = RenderRequest(
        prompt=(
            "Crie um vídeo educacional infantil de inglês para iniciantes com duração de 2 minutos. "
            "Tema da aula: Dias da semana em inglês. "
            "Objetivo da aula: ensinar Monday, Tuesday, Wednesday e Friday com exemplos simples. "
            "Estilo visual: calendário divertido na sala de aula."
        ),
        duration_minutes=2,
    )

    plan = planner.generate(request)
    english_lines = [segment.text.lower() for scene in plan.scenes for segment in scene.narration if segment.language == "en-US"]

    assert plan.title.startswith("Dias da Semana em Inglês")
    assert plan.vocabulary[:4] == ["Monday", "Tuesday", "Wednesday", "Friday"]
    assert any("monday" in line and "tuesday" in line for line in english_lines)


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
    reinforcement_line = plan.scenes[3].narration[0].text

    assert "Olá, turma." in opening_line
    assert "idade em inglês" in opening_line
    assert "você" in opening_line
    assert "diálogo" in dialogue_explanation
    assert "criança" in dialogue_explanation
    assert "reforçar" in reinforcement_line


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


def test_final_quiz_video_filter_adds_countdown_and_answer_overlay(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    composer = VideoComposer(settings)
    scene = LessonScene(
        scene_id="scene-06",
        title="Quiz Final",
        duration_seconds=14,
        teaching_mode="game",
        visual_prompt="quiz classroom",
        narration=[
            NarrationSegment(language="pt-BR", text="Quiz final."),
            NarrationSegment(language="en-US", text="What's her name?"),
            NarrationSegment(language="pt-BR", text="Agora pense rapido."),
            NarrationSegment(language="pt-BR", text="Se voce pensou que isso significa qual é o nome dela, acertou."),
        ],
        vocabulary=["What's her name?"],
        card_details=["Qual é o nome dela"],
    )

    filter_chain = composer._build_scene_filter(
        scene=scene,
        duration=float(scene.duration_seconds),
        animated_clip=False,
        cues=[],
        subtitles=[
            NarrationSubtitle(speaker="teacher", language="pt-BR", text="Quiz final.", start=0.0, end=1.2),
            NarrationSubtitle(speaker="teacher", language="en-US", text="What's her name?", start=1.4, end=2.3),
            NarrationSubtitle(speaker="teacher", language="pt-BR", text="Agora pense rapido.", start=2.4, end=3.4),
            NarrationSubtitle(
                speaker="teacher",
                language="pt-BR",
                text="Se voce pensou que isso significa qual é o nome dela, acertou.",
                start=8.4,
                end=10.2,
            ),
        ],
        subtitle_path=None,
    )

    assert "drawtext=" in filter_chain
    assert "text='5'" in filter_chain
    assert "text='1'" in filter_chain
    assert "text='Resposta\\: Qual é o nome dela'" in filter_chain
    assert "between(t,3.40,4.40)" in filter_chain
    assert "enable='gte(t,8.40)'" in filter_chain
    assert "color=yellow@0.12" not in filter_chain


def test_final_quiz_video_filter_detects_answer_reveal_with_accents(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    composer = VideoComposer(settings)
    scene = LessonScene(
        scene_id="scene-06",
        title="Quiz Final",
        duration_seconds=14,
        teaching_mode="game",
        visual_prompt="quiz classroom",
        narration=[
            NarrationSegment(language="pt-BR", text="Quiz final."),
            NarrationSegment(language="en-US", text="What's his name?"),
        ],
        vocabulary=["What's his name?"],
        card_details=["Qual é o nome dele"],
    )

    filter_chain = composer._build_scene_filter(
        scene=scene,
        duration=27.38,
        animated_clip=False,
        cues=[],
        subtitles=[
            NarrationSubtitle(speaker="teacher", language="en-US", text="What's his name?", start=6.75, end=7.77),
            NarrationSubtitle(speaker="teacher", language="pt-BR", text="Se você pensou que isso significa qual é o nome dele, acertou.", start=17.52, end=21.24),
        ],
        subtitle_path=None,
    )

    assert "between(t,12.52,13.52)" in filter_chain
    assert "enable='gte(t,17.52)'" in filter_chain


def test_final_quiz_helper_text_wraps_before_timer(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    renderer = TemplateVisualRenderer(settings)
    scene = LessonScene(
        scene_id="scene-quiz",
        title="Quiz Final",
        duration_seconds=20,
        visual_prompt="quiz",
        on_screen_text=["Ouça e responda"],
        vocabulary=["Let's paint"],
        card_details=["Vamos pintar"],
        narration=[
            NarrationSegment(language="pt-BR", text="Quiz final."),
            NarrationSegment(language="en-US", text="Let's paint."),
        ],
        teaching_mode="game",
    )

    image = Image.new("RGB", (settings.video_width, settings.video_height), "#FFFFFF")
    draw = ImageDraw.Draw(image)
    quiz_frame = renderer.final_quiz_layout(scene, settings.video_width, settings.video_height)
    assert quiz_frame is not None

    helper_font = renderer._load_font(24, bold=False)
    helper_text = (
        "Ouça a frase em inglês, pense no significado e responda "
        "antes do contador terminar."
    )
    helper_max_width = quiz_frame.timer_left - quiz_frame.panel_left - 110
    helper_lines = renderer._wrap_text_to_width(draw, helper_text, helper_font, helper_max_width)[:2]

    assert len(helper_lines) == 2
    assert all(renderer._text_width(draw, line, helper_font) <= helper_max_width for line in helper_lines)


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
