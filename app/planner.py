from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import httpx

from app.config import Settings
from app.schemas import LessonPlan, LessonScene, NarrationSegment, RenderRequest

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TopicProfile:
    key: str
    title_pt: str
    focus: str
    vocabulary: list[str]
    translations: dict[str, str]
    visual_theme: str
    matches: tuple[str, ...]


TOPIC_PROFILES = (
    TopicProfile(
        key="colors",
        title_pt="Cores em Inglês",
        focus="cores do dia a dia",
        vocabulary=["red", "blue", "yellow", "green", "orange", "purple"],
        translations={
            "red": "vermelho",
            "blue": "azul",
            "yellow": "amarelo",
            "green": "verde",
            "orange": "laranja",
            "purple": "roxo",
        },
        visual_theme="happy classroom with crayons, rainbow, smiling paint drops",
        matches=("cor", "cores", "color", "colors"),
    ),
    TopicProfile(
        key="animals",
        title_pt="Animais em Inglês",
        focus="animais favoritos das crianças",
        vocabulary=["cat", "dog", "bird", "fish", "lion", "tiger"],
        translations={
            "cat": "gato",
            "dog": "cachorro",
            "bird": "pássaro",
            "fish": "peixe",
            "lion": "leão",
            "tiger": "tigre",
        },
        visual_theme="storybook jungle with friendly animals and balloons",
        matches=("animal", "animals", "bicho", "zoo"),
    ),
    TopicProfile(
        key="numbers",
        title_pt="Números em Inglês",
        focus="números de um a dez",
        vocabulary=["one", "two", "three", "four", "five", "six"],
        translations={
            "one": "um",
            "two": "dois",
            "three": "três",
            "four": "quatro",
            "five": "cinco",
            "six": "seis",
        },
        visual_theme="playful counting blocks, stars and balloons",
        matches=("numero", "número", "numeros", "números", "number", "numbers", "contar"),
    ),
    TopicProfile(
        key="greetings",
        title_pt="Cumprimentos em Inglês",
        focus="saudações básicas",
        vocabulary=["hello", "goodbye", "please", "thank you", "friend", "teacher"],
        translations={
            "good morning": "bom dia",
            "good afternoon": "boa tarde",
            "good night": "boa noite",
            "hello": "olá",
            "goodbye": "tchau",
            "please": "por favor",
            "thank you": "obrigado",
            "friend": "amigo",
            "teacher": "professor",
        },
        visual_theme="bright school doorway with waving children and confetti",
        matches=("saud", "greeting", "hello", "cumprimento", "introducao", "introdução", "ingles", "inglês"),
    ),
    TopicProfile(
        key="body",
        title_pt="Corpo em Inglês",
        focus="partes do corpo",
        vocabulary=["head", "eyes", "ears", "hands", "knees", "toes"],
        translations={
            "head": "cabeça",
            "eyes": "olhos",
            "ears": "orelhas",
            "hands": "mãos",
            "knees": "joelhos",
            "toes": "dedos dos pés",
        },
        visual_theme="dance classroom with playful body-part stickers",
        matches=("body", "corpo", "partes do corpo"),
    ),
)


SCENE_BLUEPRINTS = (
    ("Boas-vindas", "Vamos descobrir", "smiling teacher, stars and speech bubbles"),
    ("Primeiras palavras", "Olha e repete", "flashcards floating over a bright board"),
    ("Eco do professor", "Professor fala, turma repete", "playful sound waves and word cards"),
    ("Mais vocabulário", "Novas palavras", "storybook characters holding labels"),
    ("Jogo da resposta", "Qual é a certa?", "two big answer buttons and cheerful mascots"),
    ("Frase curtinha", "Agora em frase", "word blocks forming a simple sentence"),
    ("Mini-história", "Inglês na historinha", "storybook scene with friendly characters"),
    ("Mover e falar", "Mexa o corpo e fale", "children dancing and pointing"),
    ("Quiz 1", "Responda comigo", "quiz board with bright stars"),
    ("Quiz 2", "Hora da resposta", "treasure map with answer bubbles"),
    ("Revisão guiada", "Cantando as palavras", "musical notes, rainbow and applause"),
    ("Tchau, turma", "Até a próxima", "sunset classroom with waving characters"),
)


class LessonPlanner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(self, request: RenderRequest) -> LessonPlan:
        if self.settings.use_ollama and request.planner_mode != "local":
            try:
                plan = self._generate_with_ollama(request)
                return self._normalize_plan(plan, request)
            except Exception as exc:  # pragma: no cover
                logger.warning("Falling back to local planner: %s", exc)

        return self._normalize_plan(self._generate_fallback(request), request)

    def _generate_with_ollama(self, request: RenderRequest) -> LessonPlan:
        schema = LessonPlan.model_json_schema()
        system_prompt = (
            "You are an expert male English teacher for Brazilian children aged 5 to 8. "
            "You create animated lesson plans, not generic entertainment. "
            "Return valid JSON only, no markdown. "
            "Every narration segment must use either pt-BR or en-US. "
            "pt-BR segments must explain the meaning or activity in Brazilian Portuguese first. "
            "en-US segments must contain the English words and short phrases that an American voice will read. "
            "Do not mix both languages inside the same narration segment. "
            "Each scene must contain a visual_prompt, on_screen_text, vocabulary and narration segments. "
            "Teach like a real male teacher: explain the meaning in Portuguese, then model the English pronunciation, "
            "ask the child to repeat, check understanding, and review what was learned. "
            "For greetings, use beginner patterns similar to children's materials: hello is a greeting, good morning class, "
            "how are you, I'm fine, thank you, and classroom call-and-response."
        )
        user_prompt = (
            f"Prompt do usuário: {request.prompt}\n"
            f"Duração total em minutos: {request.duration_minutes}\n"
            f"Faixa etária: {request.target_age}\n"
            "Crie entre 8 e 12 cenas. Distribua duração suficiente para fechar a duração total. "
            "Nos trechos em português brasileiro, apresente antes o significado do que será ensinado. "
            "Depois use segmentos en-US com as palavras e frases em inglês para leitura por voz americana. "
            "Use vocabulário simples, repetição, mini-jogos, checagem de entendimento e uma recapitulação final."
        )
        response = httpx.post(
            f"{self.settings.ollama_base_url}/api/chat",
            timeout=self.settings.ollama_timeout_seconds,
            json={
                "model": self.settings.ollama_model,
                "stream": False,
                "format": schema,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["message"]["content"]
        plan_json = self._extract_json(content)
        return LessonPlan.model_validate_json(plan_json)

    def _generate_fallback(self, request: RenderRequest) -> LessonPlan:
        profile = self._pick_topic(request.prompt)
        vocabulary = self._select_vocabulary(profile, request.prompt)
        primary_vocabulary = self._primary_vocabulary(profile, request.prompt, vocabulary)
        groups = self._build_vocabulary_groups(vocabulary, primary_vocabulary)
        scenes: list[LessonScene] = []
        scene_count = max(4, min(len(SCENE_BLUEPRINTS), request.duration_minutes * 3))

        for index, (scene_title, badge, decor) in enumerate(SCENE_BLUEPRINTS[:scene_count], start=1):
            current_words = groups[(index - 1) % len(groups)]
            scenes.append(
                LessonScene(
                    scene_id=f"scene-{index:02d}",
                    title=scene_title,
                    duration_seconds=20,
                    teaching_mode=self._scene_teaching_mode(index),
                    visual_prompt=(
                        f"{profile.visual_theme}, {decor}, children's 2D illustration, soft shadows, "
                        f"big shapes, educational video frame about {profile.focus}, male english teacher guiding students"
                    ),
                    narration=self._build_scene_narration(index, profile, current_words),
                    on_screen_text=[badge, *[word.title() for word in current_words]],
                    vocabulary=current_words,
                    background_palette=self._palette_for_scene(index),
                )
            )

        return LessonPlan(
            title=f"{profile.title_pt} para Crianças",
            summary=(
                f"Aula guiada por um professor de inglês infantil com {request.duration_minutes} minutos "
                f"para ensinar {profile.focus} em inglês com apoio em português brasileiro."
            ),
            audience="children",
            target_age=request.target_age,
            duration_minutes=request.duration_minutes,
            style="professor de inglês infantil, alegre, didático, acolhedor, com repetição guiada",
            learning_objectives=[
                f"Reconhecer palavras sobre {profile.focus}",
                "Ouvir o professor, entender o significado em português e repetir em inglês",
                "Repetir palavras em inglês com confiança",
                "Usar frases curtinhas em contexto infantil",
            ],
            vocabulary=vocabulary,
            scenes=scenes,
        )

    def _scene_teaching_mode(self, scene_index: int) -> str:
        scene_modes = {
            1: "intro",
            2: "vocabulary",
            3: "dialogue",
            4: "vocabulary",
            5: "game",
            6: "dialogue",
            7: "story",
            8: "movement",
            9: "game",
            10: "game",
            11: "review",
            12: "review",
        }
        return scene_modes.get(scene_index, "vocabulary")

    def _build_scene_narration(
        self,
        scene_index: int,
        profile: TopicProfile,
        words: list[str],
    ) -> list[NarrationSegment]:
        if profile.key == "greetings":
            return self._build_greetings_scene_narration(scene_index, profile, words)

        joined_words = ", ".join(words)
        lead_word = words[0]
        meanings = self._meaning_list(profile, words)
        meaning_intro = self._meaning_intro(meanings)
        chunks = {
            1: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        f"Olá, turma. Eu sou o seu professor de inglês e hoje vou ensinar {profile.focus} com calma. "
                        f"Primeiro vamos entender o significado: {meaning_intro}"
                    ),
                ),
                NarrationSegment(language="en-US", text=f"Let's learn: {joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Agora escute em inglês, olhe para os cartões e repita com voz clara.",
                ),
            ],
            2: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        f"Olhe para a tela. Vou explicar primeiro em português: {meaning_intro} "
                        "Agora eu vou modelar a pronúncia em inglês e você repete."
                    ),
                ),
                NarrationSegment(language="en-US", text=f"Repeat after me: {joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Muito bem. Agora aponte para cada cartão e fale junto comigo, uma palavra de cada vez.",
                ),
            ],
            3: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        f"Vamos fazer o eco do professor. Lembre do significado em português: {meaning_intro} "
                        "Quando eu falar em inglês, você repete do mesmo jeito."
                    ),
                ),
                NarrationSegment(language="en-US", text=joined_words),
                NarrationSegment(
                    language="pt-BR",
                    text="Excelente. Mais uma vez, com capricho na pronúncia e ouvindo cada pedacinho da palavra.",
                ),
            ],
            4: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        f"Agora chegaram novas palavras para a nossa lição. Em português, elas significam: {meaning_intro}"
                    ),
                ),
                NarrationSegment(language="en-US", text=f"New words: {joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Cada palavra tem um som especial. O professor fala em inglês, você escuta e depois repete com calma.",
                ),
            ],
            5: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        f"Hora do jogo do professor. Pense primeiro no significado em português: {meaning_intro} "
                        "Depois escolha a resposta certa quando eu falar em inglês."
                    ),
                ),
                NarrationSegment(language="en-US", text=f"Which one is it? {joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Se acertar, comemore. Se errar, tudo bem, porque aprender inglês é repetir até ficar natural.",
                ),
            ],
            6: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        f"Agora vamos montar uma frase curtinha. Primeiro pense no significado da palavra principal: {self._translation(profile, lead_word)}. "
                        "Depois eu mostro o modelo em inglês."
                    ),
                ),
                NarrationSegment(language="en-US", text=f"I like {lead_word}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Fale devagar, ouvindo o professor na sua cabeça, e depois repita com segurança.",
                ),
            ],
            7: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        f"Nesta mini-história, cada descoberta tem um significado em português: {meaning_intro} "
                        "Agora você vai ouvir tudo isso em inglês no contexto."
                    ),
                ),
                NarrationSegment(language="en-US", text=f"Look. Wow. {joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Quando você ouvir a palavra, aponte para a tela. Isso ajuda a ligar som, imagem e significado.",
                ),
            ],
            8: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        f"Agora mexa o corpo comigo. Primeiro lembre do significado: {meaning_intro} "
                        "Depois copie o som em inglês ao mesmo tempo."
                    ),
                ),
                NarrationSegment(language="en-US", text=f"Move and say: {joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Aprender com movimento ajuda o inglês a entrar na memória e melhora a resposta da aula.",
                ),
            ],
            9: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        f"Quiz rápido do professor. Eu vou pensar no significado com você: {meaning_intro} "
                        "Agora responda quando eu falar em inglês."
                    ),
                ),
                NarrationSegment(language="en-US", text=f"Say it now: {joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Boa resposta. Agora repita outra vez para fixar a pronúncia correta.",
                ),
            ],
            10: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        f"Segunda rodada do quiz. Você já sabe o significado em português: {meaning_intro} "
                        "Agora mostre que já consegue reconhecer isso em inglês."
                    ),
                ),
                NarrationSegment(language="en-US", text=f"Your turn: {joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Perfeito. O professor percebe que seu inglês já está saindo com mais naturalidade.",
                ),
            ],
            11: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        f"Vamos revisar. Em português, trabalhamos estes significados: {meaning_intro} "
                        "Agora vamos cantar e repetir tudo em inglês."
                    ),
                ),
                NarrationSegment(language="en-US", text=f"Sing with me: {joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Você mandou muito bem. Já dá para reconhecer as palavras e repetir com mais segurança.",
                ),
            ],
            12: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        f"Nossa aula terminou. Hoje você aprendeu estes significados em português: {meaning_intro} "
                        "Agora guarde também a forma em inglês na memória."
                    ),
                ),
                NarrationSegment(language="en-US", text=f"See you soon. {joined_words}. Goodbye."),
                NarrationSegment(
                    language="pt-BR",
                    text="Tchau, turma. Na próxima aula o professor volta com novas palavras, novas frases e mais prática.",
                ),
            ],
        }
        return chunks[scene_index]

    def _build_greetings_scene_narration(
        self,
        scene_index: int,
        profile: TopicProfile,
        words: list[str],
    ) -> list[NarrationSegment]:
        joined_words = ", ".join(words)
        meaning_intro = self._meaning_intro(self._meaning_list(profile, words))
        first_word = words[0]
        second_word = words[1] if len(words) > 1 else words[0]
        chunks = {
            1: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        f"Olá, turma. Hoje a nossa aula é sobre saudações. Primeiro vamos entender o significado: {meaning_intro} "
                        "Essas expressões mudam conforme o momento do dia."
                    ),
                ),
                NarrationSegment(language="en-US", text=f"Let's learn: {joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Agora escute a forma em inglês e repita como um aluno atento.",
                ),
            ],
            2: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        f"Quando chega a manhã, usamos {self._translation(profile, first_word)}. "
                        f"Quando o dia continua, usamos {self._translation(profile, second_word)}."
                    ),
                ),
                NarrationSegment(language="en-US", text=f"Good morning, class. {second_word.title()}, everyone."),
                NarrationSegment(
                    language="pt-BR",
                    text="Perceba que cada saudação combina com um horário diferente.",
                ),
            ],
            3: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        "Agora vamos praticar como em um diálogo de verdade. "
                        "Primeiro eu cumprimento, depois pergunto como a pessoa está."
                    ),
                ),
                NarrationSegment(language="en-US", speaker="teacher", text=f"{first_word.title()}, Ana. How are you?"),
                NarrationSegment(language="en-US", speaker="student", text="I'm fine, thank you."),
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        f"Muito bem. Nesse diálogo, o professor disse {self._translation(profile, first_word)}, Ana, como você está? "
                        "Depois o aluno respondeu estou bem, obrigado."
                    ),
                ),
            ],
            4: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        f"Agora pense no significado em português: {meaning_intro} "
                        "Eu vou mostrar novas formas de usar essas expressões."
                    ),
                ),
                NarrationSegment(language="en-US", text=f"Hello. {joined_words}. Goodbye."),
                NarrationSegment(
                    language="pt-BR",
                    text="Escute com calma e note como o inglês pode começar e terminar uma conversa.",
                ),
            ],
            5: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        "Jogo rápido. Eu digo o momento do dia em português e você pensa na saudação certa em inglês "
                        "antes de ouvir a resposta."
                    ),
                ),
                NarrationSegment(language="en-US", text=f"Morning? {first_word.title()}. Afternoon? {second_word.title()}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Boa. Você está ligando horário e saudação como um professor faria na sala.",
                ),
            ],
            6: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        "Agora vamos colocar a saudação dentro de uma frase curtinha de sala de aula. "
                        "Escute o modelo e depois repita."
                    ),
                ),
                NarrationSegment(language="en-US", speaker="teacher", text=f"{first_word.title()}, class. Let's study English!"),
                NarrationSegment(language="en-US", speaker="student", text=f"{first_word.title()}, teacher."),
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        f"Aqui o professor disse {self._translation(profile, first_word)}, turma. Vamos estudar inglês. "
                        f"Depois o aluno respondeu {self._translation(profile, first_word)}, professor."
                    ),
                ),
            ],
            7: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        "Na historinha, cada personagem aparece em um momento do dia. "
                        "Você vai ouvir qual saudação combina com cada cena."
                    ),
                ),
                NarrationSegment(language="en-US", text=f"Look. {joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Aponte para a cena certa quando escutar a expressão.",
                ),
            ],
            8: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        "Mexa o corpo comigo. Quando eu falar a saudação em inglês, você repete e acena com a mão."
                    ),
                ),
                NarrationSegment(language="en-US", text=f"Wave and say: {joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Falar e se mover ao mesmo tempo ajuda a memória a guardar o som certo.",
                ),
            ],
            9: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        "Quiz. Eu vou descrever o horário e você responde com a saudação correta."
                    ),
                ),
                NarrationSegment(language="en-US", text=f"Sun is up? {first_word.title()}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Muito bom. Agora vamos para mais uma rodada.",
                ),
            ],
            10: [
                NarrationSegment(
                    language="pt-BR",
                    text="Agora a segunda rodada do quiz vai mais rápido, como em uma revisão de professor.",
                ),
                NarrationSegment(language="en-US", text=f"After lunch? {second_word.title()}. Night time? {words[-1].title()}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Excelente. Você já reconhece qual saudação usar em cada parte do dia.",
                ),
            ],
            11: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        f"Vamos revisar. Em português, trabalhamos estes significados: {meaning_intro} "
                        "Agora repita tudo em inglês como no final de uma aula."
                    ),
                ),
                NarrationSegment(language="en-US", text=f"Repeat with me: {joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Muito bem. Essa repetição final deixa a saudação pronta para o dia a dia.",
                ),
            ],
            12: [
                NarrationSegment(
                    language="pt-BR",
                    text="Nossa aula terminou. Guarde a regra principal: pense no horário e escolha a saudação certa.",
                ),
                NarrationSegment(language="en-US", text=f"See you soon. {joined_words}. Goodbye."),
                NarrationSegment(
                    language="pt-BR",
                    text="Tchau, turma. Na próxima aula o professor volta com novas expressões e novos diálogos.",
                ),
            ],
        }
        return chunks[scene_index]

    def _select_vocabulary(self, profile: TopicProfile, prompt: str) -> list[str]:
        if profile.key == "greetings":
            requested = self._extract_requested_greetings(prompt)
            if requested:
                return self._pad_vocabulary(requested, profile.vocabulary)
        return profile.vocabulary

    def _primary_vocabulary(self, profile: TopicProfile, prompt: str, selected: list[str]) -> list[str]:
        if profile.key == "greetings":
            requested = self._extract_requested_greetings(prompt)
            if requested:
                return requested
        return selected[:3]

    def _extract_requested_greetings(self, prompt: str) -> list[str]:
        lowered = prompt.lower()
        ordered: list[str] = []
        greeting_map = (
            (("bom dia", "good morning"), "good morning"),
            (("boa tarde", "good afternoon"), "good afternoon"),
            (("boa noite", "good evening", "good night"), "good night"),
            (("oi", "olá", "ola", "hello"), "hello"),
            (("tchau", "adeus", "goodbye", "bye"), "goodbye"),
            (("por favor", "please"), "please"),
            (("obrigado", "obrigada", "thank you"), "thank you"),
        )

        for aliases, normalized in greeting_map:
            if any(alias in lowered for alias in aliases) and normalized not in ordered:
                ordered.append(normalized)

        return ordered

    def _pad_vocabulary(self, requested: list[str], fallback: list[str], minimum_size: int = 6) -> list[str]:
        merged = list(requested)
        for word in fallback:
            if word not in merged:
                merged.append(word)
            if len(merged) >= minimum_size:
                break
        return merged

    def _build_vocabulary_groups(self, vocabulary: list[str], primary: list[str]) -> list[list[str]]:
        if not primary:
            primary = vocabulary[:3]

        if len(primary) >= 3:
            return [
                primary[:3],
                primary[:3],
                primary[:2],
                primary[1:3],
                primary[:3],
                vocabulary,
            ]

        return [vocabulary[:3], vocabulary[3:6], vocabulary[:2], vocabulary[2:4], vocabulary[4:6], vocabulary]

    def _meaning_intro(self, meanings: list[str]) -> str:
        if not meanings:
            return "vamos aprender juntos."
        if len(meanings) == 1:
            return f"{meanings[0]}."
        if len(meanings) == 2:
            return f"{meanings[0]} e {meanings[1]}."
        return f"{', '.join(meanings[:-1])} e {meanings[-1]}."

    def _meaning_list(self, profile: TopicProfile, words: list[str]) -> list[str]:
        return [self._translation(profile, word) for word in words]

    def _translation(self, profile: TopicProfile, word: str) -> str:
        return profile.translations.get(word.lower(), word)

    def _pick_topic(self, prompt: str) -> TopicProfile:
        lowered = prompt.lower()
        for profile in TOPIC_PROFILES:
            if any(token in lowered for token in profile.matches):
                return profile
        return TOPIC_PROFILES[3]

    def _normalize_plan(self, plan: LessonPlan, request: RenderRequest) -> LessonPlan:
        target_seconds = request.duration_minutes * 60
        if not plan.scenes:
            raise ValueError("Lesson plan must include at least one scene")

        raw_total = sum(scene.duration_seconds for scene in plan.scenes)
        if raw_total <= 0:
            raise ValueError("Lesson plan must include positive scene durations")

        factor = target_seconds / raw_total
        scene_count = len(plan.scenes)
        min_duration = max(4, min(10, target_seconds // scene_count))
        raw_durations = [scene.duration_seconds * factor for scene in plan.scenes]
        durations = [max(min_duration, int(duration)) for duration in raw_durations]
        corrected_total = sum(durations)

        while corrected_total < target_seconds:
            for index in range(scene_count):
                if corrected_total >= target_seconds:
                    break
                durations[index] += 1
                corrected_total += 1

        while corrected_total > target_seconds:
            for index in range(scene_count - 1, -1, -1):
                if corrected_total <= target_seconds:
                    break
                if durations[index] > min_duration:
                    durations[index] -= 1
                    corrected_total -= 1

        normalized_scenes = []
        for index, scene in enumerate(plan.scenes, start=1):
            normalized_scenes.append(
                scene.model_copy(
                    update={
                        "scene_id": scene.scene_id or f"scene-{index:02d}",
                        "duration_seconds": durations[index - 1],
                        "background_palette": scene.background_palette or self._palette_for_scene(index),
                        "title": scene.title.strip() or f"Cena {index}",
                        "visual_prompt": scene.visual_prompt.strip() or "children classroom illustration",
                    }
                )
            )

        return plan.model_copy(
            update={
                "duration_minutes": request.duration_minutes,
                "target_age": request.target_age,
                "scenes": normalized_scenes,
            }
        )

    def _palette_for_scene(self, scene_index: int) -> list[str]:
        palettes = [
            ["#FFF1B8", "#FEC5E5", "#A7F3D0"],
            ["#BFDBFE", "#FDE68A", "#FBCFE8"],
            ["#FCD34D", "#6EE7B7", "#93C5FD"],
            ["#F9A8D4", "#C4B5FD", "#FDE68A"],
            ["#FCA5A5", "#A5F3FC", "#C7D2FE"],
            ["#FED7AA", "#BBF7D0", "#DDD6FE"],
        ]
        return palettes[(scene_index - 1) % len(palettes)]

    def _extract_json(self, text: str) -> str:
        text = text.strip()
        if text.startswith("{"):
            return text
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            return match.group(0)
        raise ValueError("Model did not return JSON")
