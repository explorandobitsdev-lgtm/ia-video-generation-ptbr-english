from __future__ import annotations

import logging
import math
import re
import unicodedata
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
        vocabulary=["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"],
        translations={
            "one": "um",
            "two": "dois",
            "three": "três",
            "four": "quatro",
            "five": "cinco",
            "six": "seis",
            "seven": "sete",
            "eight": "oito",
            "nine": "nove",
            "ten": "dez",
        },
        visual_theme="playful counting blocks, stars and balloons",
        matches=("numero", "número", "numeros", "números", "number", "numbers", "contar"),
    ),
    TopicProfile(
        key="pronouns",
        title_pt="Pronomes em Inglês",
        focus="pronomes pessoais simples",
        vocabulary=["i", "you", "he", "she", "we", "they"],
        translations={
            "i": "eu",
            "you": "você",
            "he": "ele",
            "she": "ela",
            "we": "nós",
            "they": "eles",
        },
        visual_theme="playful classroom with character labels, arrows and bright pronoun cards",
        matches=("pronome", "pronomes", "pronoun", "pronouns"),
    ),
    TopicProfile(
        key="introductions",
        title_pt="Apresentações em Inglês",
        focus="apresentações, nomes e pequenos diálogos",
        vocabulary=["my name is", "what is your name", "nice to meet you", "i am", "teacher", "friend"],
        translations={
            "my name is": "meu nome é",
            "what is your name": "como você se chama",
            "nice to meet you": "muito prazer",
            "i am": "eu sou",
            "teacher": "professor",
            "friend": "amigo",
        },
        visual_theme="colorful classroom introductions with name tags, smiling children and speech bubbles",
        matches=(
            "apresent",
            "aprenseta",
            "introduc",
            "meu nome",
            "como voce chama",
            "como voce se chama",
            "como voc chama",
            "qual e o seu nome",
            "qual seu nome",
            "me chamo",
            "my name is",
            "what is your name",
            "what s your name",
            "i am",
            "muito prazer",
            "nice to meet you",
            "prazer em conhecer",
            "nome",
        ),
    ),
    TopicProfile(
        key="age",
        title_pt="Idade em Ingles",
        focus="perguntar e responder a idade",
        vocabulary=[
            "how old are you",
            "i'm six years old",
            "i'm seven years old",
            "i'm eight years old",
            "i'm ten years old",
            "years old",
        ],
        translations={
            "how old are you": "quantos anos voce tem",
            "i'm six years old": "eu tenho seis anos",
            "i'm seven years old": "eu tenho sete anos",
            "i'm eight years old": "eu tenho oito anos",
            "i'm ten years old": "eu tenho dez anos",
            "years old": "anos de idade",
        },
        visual_theme="happy school yard with smiling children, age cards, speech bubbles and number balloons",
        matches=("idade", "quantos anos", "age", "how old are you", "years old"),
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
        matches=(
            "saud",
            "greeting",
            "hello",
            "cumprimento",
            "bom dia",
            "boa tarde",
            "boa noite",
            "good morning",
            "good afternoon",
            "good night",
        ),
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


AGE_DEFAULT_EXAMPLES = ("six", "seven", "eight", "ten")

AGE_NUMBER_WORDS = {
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
    "10": "ten",
    "six": "six",
    "seven": "seven",
    "eight": "eight",
    "nine": "nine",
    "ten": "ten",
}

ENGLISH_HINT_WORDS = {
    "am",
    "add",
    "and",
    "answer",
    "are",
    "ask",
    "book",
    "classroom",
    "close",
    "class",
    "day",
    "days",
    "down",
    "eraser",
    "fine",
    "find",
    "friend",
    "good",
    "happy",
    "hello",
    "how",
    "i",
    "im",
    "is",
    "it",
    "listen",
    "look",
    "monday",
    "morning",
    "my",
    "name",
    "notebook",
    "old",
    "open",
    "pencil",
    "pick",
    "sad",
    "school",
    "seven",
    "show",
    "six",
    "sit",
    "stand",
    "ten",
    "thank",
    "today",
    "tuesday",
    "up",
    "very",
    "wednesday",
    "what",
    "years",
    "you",
    "your",
}

WEAK_ENGLISH_HINT_WORDS = {
    "am",
    "and",
    "are",
    "i",
    "im",
    "is",
    "it",
    "my",
    "up",
    "very",
    "you",
    "your",
}

STRUCTURED_ENGLISH_LIST_MARKERS = (
    "verbos em ingles",
    "palavras em ingles",
    "frases em ingles",
    "comandos em ingles",
)

STRUCTURED_ENGLISH_STOP_MARKERS = (
    " o video deve ",
    " o vídeo deve ",
    " estrutura do video ",
    " estrutura do vídeo ",
    " narrador ",
    " texto na tela ",
    " mostrar ",
    " mostre ",
    " criancas repetem ",
    " crianças repetem ",
    " as criancas ",
    " as crianças ",
)

ENGLISH_MULTIWORD_PHRASES = (
    "pick up",
    "sit down",
    "stand up",
    "good morning",
    "good afternoon",
    "good night",
    "thank you",
)

COMMON_CUSTOM_TRANSLATIONS = {
    "look": "olhar",
    "find": "encontrar",
    "listen": "escutar",
    "show": "mostrar",
    "add": "somar",
    "open": "abrir",
    "close": "fechar",
    "pick up": "pegar",
    "ask": "perguntar",
    "answer": "responder",
    "sit down": "sentar",
    "stand up": "levantar",
}

PORTUGUESE_HINT_WORDS = {
    "aula",
    "como",
    "crianca",
    "criancas",
    "ensinar",
    "estilo",
    "falar",
    "idade",
    "ingles",
    "narrador",
    "objetivo",
    "para",
    "perguntar",
    "portugues",
    "pratica",
    "responder",
    "significa",
    "tema",
    "vamos",
    "video",
    "visual",
    "voce",
}

ENGLISH_META_PHRASES = (
    "How old are you",
    "I'm",
    "I am",
    "I have",
    "years old",
    "My name is",
    "What is your name",
    "Nice to meet you",
    "Good morning",
    "Good afternoon",
    "Good night",
    "Hello",
    "Goodbye",
    "Please",
    "Thank you",
    "Let's learn",
    "Repeat after me",
    "Repeat with me",
    "Say it now",
    "Your turn",
    "Very good",
    "See you soon",
    "See you next class",
)

PT_BR_ACCENT_REPLACEMENTS = (
    ("a pergunta principal e", "a pergunta principal é"),
    ("acao", "ação"),
    ("acoes", "ações"),
    ("agora e sua vez", "agora é sua vez"),
    ("ja esta", "já está"),
    ("ja", "já"),
    ("o objetivo principal e", "o objetivo principal é"),
    ("ate a proxima", "até a próxima"),
    ("em ingles", "em inglês"),
    ("de ingles", "de inglês"),
    ("em portugues", "em português"),
    ("ate", "até"),
    ("alguem", "alguém"),
    ("basico", "básico"),
    ("crianca", "criança"),
    ("criancas", "crianças"),
    ("dialogo", "diálogo"),
    ("expressoes", "expressões"),
    ("facil", "fácil"),
    ("historia", "história"),
    ("ingles", "inglês"),
    ("licao", "lição"),
    ("memoria", "memória"),
    ("nao", "não"),
    ("numero", "número"),
    ("numeros", "números"),
    ("ola", "olá"),
    ("otimo", "ótimo"),
    ("portugues", "português"),
    ("pratica", "prática"),
    ("reforcar", "reforçar"),
    ("propria", "própria"),
    ("proximo", "próximo"),
    ("proxima", "próxima"),
    ("rapido", "rápido"),
    ("rapida", "rápida"),
    ("repeticao", "repetição"),
    ("revisao", "revisão"),
    ("saudacoes", "saudações"),
    ("situacao", "situação"),
    ("situacoes", "situações"),
    ("tambem", "também"),
    ("ultima", "última"),
    ("vocabulario", "vocabulário"),
    ("voce", "você"),
    ("voces", "vocês"),
)


class LessonPlanner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(self, request: RenderRequest) -> LessonPlan:
        local_profile, local_score = self._pick_topic_match(request.prompt)
        if request.planner_mode == "auto" and local_profile is not None and local_score > 0:
            return self._normalize_plan(self._generate_fallback(request, profile=local_profile), request)

        if self.settings.use_ollama and request.planner_mode != "local":
            try:
                plan = self._generate_with_ollama(request)
                return self._normalize_plan(plan, request)
            except Exception as exc:  # pragma: no cover
                logger.warning("Falling back to local planner: %s", exc)

        return self._normalize_plan(self._generate_fallback(request, profile=local_profile), request)

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

    def _generate_fallback(self, request: RenderRequest, profile: TopicProfile | None = None) -> LessonPlan:
        profile = profile or self._pick_topic(request.prompt)
        vocabulary = self._select_vocabulary(profile, request.prompt)
        primary_vocabulary = self._primary_vocabulary(profile, request.prompt, vocabulary)
        summary_focus = self._focus_summary_text(profile.focus)
        scene_count = max(4, min(len(SCENE_BLUEPRINTS), request.duration_minutes * 3))
        groups = self._build_vocabulary_groups(profile, vocabulary, primary_vocabulary, scene_count)
        scenes: list[LessonScene] = []

        for index, (scene_title, badge, decor) in enumerate(SCENE_BLUEPRINTS[:scene_count], start=1):
            current_words = groups[(index - 1) % len(groups)]
            teaching_mode = self._scene_teaching_mode(index, profile=profile)
            narration = self._build_scene_narration(index, profile, current_words, request.prompt)
            display_words = self._display_words_for_scene(
                profile=profile,
                teaching_mode=teaching_mode,
                current_words=current_words,
                full_vocabulary=vocabulary,
                narration=narration,
            )
            card_details = self._card_details_for_scene(profile, display_words)
            scenes.append(
                LessonScene(
                    scene_id=f"scene-{index:02d}",
                    title=scene_title,
                    duration_seconds=20,
                    teaching_mode=teaching_mode,
                    visual_prompt=(
                        f"{profile.visual_theme}, {decor}, children's 2D illustration, soft shadows, "
                        f"big shapes, educational video frame about {profile.focus}, male english teacher guiding students"
                    ),
                    narration=narration,
                    on_screen_text=[badge, *[self._display_phrase_case(word) for word in display_words]],
                    vocabulary=display_words,
                    card_details=card_details,
                    background_palette=self._palette_for_scene(index),
                )
            )

        return LessonPlan(
            title=f"{profile.title_pt} para Crianças",
            summary=(
                f"Aula guiada por um professor de inglês infantil com {request.duration_minutes} minutos "
                f"para ensinar {summary_focus} com apoio em português brasileiro."
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

    def _scene_teaching_mode(self, scene_index: int, profile: TopicProfile | None = None) -> str:
        if profile is not None and self._is_custom_command_lesson(profile):
            command_modes = {
                1: "intro",
                2: "vocabulary",
                3: "vocabulary",
                4: "vocabulary",
                5: "review",
                6: "review",
                7: "movement",
                8: "game",
                9: "review",
                10: "review",
                11: "review",
                12: "review",
            }
            return command_modes.get(scene_index, "review")

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
        prompt: str,
    ) -> list[NarrationSegment]:
        if profile.key == "greetings":
            return self._build_greetings_scene_narration(scene_index, profile, words)
        if profile.key == "introductions":
            return self._build_introductions_scene_narration(scene_index, profile, words, prompt)
        if profile.key == "age":
            return self._build_age_scene_narration(scene_index, profile, words, prompt)
        if profile.key == "custom":
            return self._build_custom_scene_narration(scene_index, profile, words, prompt)

        joined_words = ", ".join(words)
        echo_words = self._echo_words(words)
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
                NarrationSegment(language="en-US", text=echo_words),
            ],
            3: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        f"Vamos fazer o eco do professor. Lembre do significado em português: {meaning_intro} "
                        "Quando eu falar em inglês, você repete do mesmo jeito."
                    ),
                ),
                NarrationSegment(language="en-US", text=echo_words),
                NarrationSegment(
                    language="pt-BR",
                    text="Excelente. Mais uma vez. Aponte para cada cartão e repita comigo, ouvindo cada pedacinho da palavra.",
                ),
                NarrationSegment(language="en-US", text=echo_words),
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

    def _build_introductions_scene_narration(
        self,
        scene_index: int,
        profile: TopicProfile,
        words: list[str],
        prompt: str,
    ) -> list[NarrationSegment]:
        joined_words = ", ".join(words)
        meaning_intro = self._meaning_intro(self._meaning_list(profile, words))
        student_name = self._extract_requested_name(prompt) or "Bruno"
        chunks = {
            1: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        "Olá, turma. Hoje a nossa aula é sobre apresentações. "
                        f"Primeiro vamos entender o significado: {meaning_intro}"
                    ),
                ),
                NarrationSegment(language="en-US", text="Let's learn: my name is, what is your name, nice to meet you."),
                NarrationSegment(
                    language="pt-BR",
                    text="Agora escute a forma em inglês e repita como se estivesse conhecendo um novo amigo.",
                ),
            ],
            2: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        "Quando eu quero dizer meu nome em inglês, posso falar meu nome é "
                        f"ou eu sou {student_name}."
                    ),
                ),
                NarrationSegment(language="en-US", text=f"My name is {student_name}. I am {student_name}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Perceba que as duas frases servem para se apresentar de um jeito simples e natural.",
                ),
            ],
            3: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        "Agora vamos praticar um diálogo de apresentação. "
                        "Primeiro o professor pergunta o nome, depois o aluno responde."
                    ),
                ),
                NarrationSegment(language="en-US", speaker="teacher", text="Hello. What is your name?"),
                NarrationSegment(language="en-US", speaker="student", text=f"I am {student_name}. Nice to meet you."),
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        "Muito bem. Nesse diálogo, o professor perguntou como você se chama. "
                        f"Depois o aluno respondeu eu sou {student_name} e muito prazer."
                    ),
                ),
            ],
            4: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        f"Agora pense no significado em português: {meaning_intro} "
                        "Eu vou mostrar mais uma forma curtinha de se apresentar."
                    ),
                ),
                NarrationSegment(language="en-US", text=f"My name is {student_name}. Nice to meet you."),
                NarrationSegment(
                    language="pt-BR",
                    text="Escute com calma, repita em voz alta e imagine que está falando com um colega novo.",
                ),
            ],
            5: [
                NarrationSegment(
                    language="pt-BR",
                    text="Jogo rápido. Eu pergunto o nome em inglês e você responde antes de ouvir o modelo.",
                ),
                NarrationSegment(language="en-US", text=f"What is your name? I am {student_name}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Boa. Você está treinando pergunta e resposta como em uma conversa real.",
                ),
            ],
            6: [
                NarrationSegment(
                    language="pt-BR",
                    text="Agora vamos usar a apresentação em uma frase de sala de aula, com professor e aluno.",
                ),
                NarrationSegment(language="en-US", speaker="teacher", text="My name is Teacher Leo."),
                NarrationSegment(language="en-US", speaker="student", text=f"I am {student_name}. Nice to meet you."),
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        "Aqui o professor disse meu nome é Teacher Leo. "
                        f"Depois o aluno respondeu eu sou {student_name} e muito prazer."
                    ),
                ),
            ],
            7: [
                NarrationSegment(
                    language="pt-BR",
                    text="Na historinha, cada personagem vai dizer o nome quando encontrar um novo amigo.",
                ),
                NarrationSegment(language="en-US", text=f"Hello. My name is {student_name}. Nice to meet you."),
                NarrationSegment(
                    language="pt-BR",
                    text="Aponte para a cena quando ouvir a apresentação em inglês.",
                ),
            ],
            8: [
                NarrationSegment(
                    language="pt-BR",
                    text="Mexa o corpo comigo. Quando eu falar a frase em inglês, você aponta para si e repete.",
                ),
                NarrationSegment(language="en-US", text=f"Point to yourself and say: I am {student_name}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Falar e fazer gestos ao mesmo tempo ajuda a guardar a estrutura da frase.",
                ),
            ],
            9: [
                NarrationSegment(
                    language="pt-BR",
                    text="Quiz. Eu vou perguntar o nome e você responde com a frase correta em inglês.",
                ),
                NarrationSegment(language="en-US", text=f"What is your name? My name is {student_name}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Muito bom. Agora vamos para mais uma rodada de apresentação.",
                ),
            ],
            10: [
                NarrationSegment(
                    language="pt-BR",
                    text="Agora a segunda rodada do quiz vai mais rápido, como em uma revisão de professor.",
                ),
                NarrationSegment(language="en-US", text=f"I am {student_name}. Nice to meet you."),
                NarrationSegment(
                    language="pt-BR",
                    text="Excelente. Você já consegue se apresentar de um jeito simples em inglês.",
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
                    text="Muito bem. Essa repetição final deixa a apresentação pronta para o dia a dia.",
                ),
            ],
            12: [
                NarrationSegment(
                    language="pt-BR",
                    text="Nossa aula terminou. Guarde a regra principal: diga seu nome e depois cumprimente a outra pessoa.",
                ),
                NarrationSegment(language="en-US", text=f"My name is {student_name}. Nice to meet you. Goodbye."),
                NarrationSegment(
                    language="pt-BR",
                    text="Tchau, turma. Na próxima aula o professor volta com novas frases e novos diálogos.",
                ),
            ],
        }
        return chunks[scene_index]

    def _build_age_scene_narration(
        self,
        scene_index: int,
        profile: TopicProfile,
        words: list[str],
        prompt: str,
    ) -> list[NarrationSegment]:
        _ = words
        examples = self._select_age_examples(prompt)
        answer_age = "eight" if "eight" in examples else examples[0]
        second_age = examples[1] if len(examples) > 1 else answer_age
        third_age = examples[2] if len(examples) > 2 else second_age
        last_age = examples[-1]
        review_line = " ".join(f"I'm {age} years old." for age in examples[:4])
        answer_translation = self._translation(profile, f"I'm {answer_age} years old")
        third_translation = self._translation(profile, f"I'm {third_age} years old")

        chunks = {
            1: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        "Ola, turma. Hoje vamos aprender a perguntar e responder a idade em ingles. "
                        "A pergunta principal e How old are you. Isso significa quantos anos voce tem."
                    ),
                ),
                NarrationSegment(language="en-US", text="How old are you?"),
                NarrationSegment(
                    language="pt-BR",
                    text="Escute a pergunta em ingles e repita comigo bem devagar.",
                ),
            ],
            2: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        "Para responder a idade em ingles, usamos I am mais o numero e depois years old. "
                        "Agora veja alguns exemplos."
                    ),
                ),
                NarrationSegment(
                    language="en-US",
                    text=f"I'm {examples[0]} years old. I'm {second_age} years old. I'm {third_age} years old.",
                ),
                NarrationSegment(
                    language="pt-BR",
                    text="Muito bem. Em ingles dizemos I am eight, e nao I have eight.",
                ),
            ],
            3: [
                NarrationSegment(
                    language="pt-BR",
                    text="Agora vamos praticar um dialogo. Primeiro uma crianca pergunta a idade e depois a outra responde.",
                ),
                NarrationSegment(language="en-US", speaker="teacher", text="How old are you?"),
                NarrationSegment(language="en-US", speaker="student", text=f"I'm {answer_age} years old."),
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        "Muito bem. Nesse dialogo, a primeira crianca perguntou quantos anos voce tem. "
                        f"Depois a segunda respondeu {answer_translation}."
                    ),
                ),
            ],
            4: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        "Vamos reforcar a estrutura. Para falar a idade, usamos I am mais o numero e depois years old. "
                        "Agora e sua vez de repetir."
                    ),
                ),
                NarrationSegment(language="en-US", text=review_line),
                NarrationSegment(
                    language="pt-BR",
                    text="Quando eu perguntar How old are you, voce pode responder com a sua idade.",
                ),
            ],
            5: [
                NarrationSegment(
                    language="pt-BR",
                    text="Hora do jogo. Eu vou perguntar a idade e voce pensa na resposta antes de ouvir o modelo.",
                ),
                NarrationSegment(language="en-US", text=f"How old are you? I'm {second_age} years old."),
                NarrationSegment(
                    language="pt-BR",
                    text="Excelente. Quanto mais voce repete, mais natural essa resposta fica.",
                ),
            ],
            6: [
                NarrationSegment(
                    language="pt-BR",
                    text="Mais um dialogo. Agora o professor pergunta e o aluno responde com outra idade.",
                ),
                NarrationSegment(language="en-US", speaker="teacher", text="How old are you?"),
                NarrationSegment(language="en-US", speaker="student", text=f"I'm {third_age} years old."),
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        f"Perfeito. Dessa vez o aluno respondeu {third_translation}."
                    ),
                ),
            ],
            7: [
                NarrationSegment(
                    language="pt-BR",
                    text="Na mini-historia, duas criancas contam a propria idade em ingles.",
                ),
                NarrationSegment(language="en-US", text=f"I'm {answer_age} years old. I'm {second_age} years old."),
                NarrationSegment(
                    language="pt-BR",
                    text="Aponte para cada personagem quando ouvir a idade sendo falada.",
                ),
            ],
            8: [
                NarrationSegment(
                    language="pt-BR",
                    text="Agora mexa o corpo comigo. Quando ouvir a frase em ingles, aponte para voce e repita.",
                ),
                NarrationSegment(language="en-US", text=f"Say it now: I'm {answer_age} years old."),
                NarrationSegment(
                    language="pt-BR",
                    text="No final, troque o numero e fale a sua idade de verdade.",
                ),
            ],
            9: [
                NarrationSegment(
                    language="pt-BR",
                    text="Quiz rapido. Eu pergunto e voce responde antes do professor.",
                ),
                NarrationSegment(language="en-US", text=f"How old are you? I'm {last_age} years old."),
                NarrationSegment(
                    language="pt-BR",
                    text="Boa resposta. Agora repita outra vez para deixar a frase mais forte na memoria.",
                ),
            ],
            10: [
                NarrationSegment(
                    language="pt-BR",
                    text="Segunda rodada do quiz. Agora a resposta vem ainda mais rapida.",
                ),
                NarrationSegment(language="en-US", text=f"I'm {answer_age} years old. I'm {second_age} years old."),
                NarrationSegment(
                    language="pt-BR",
                    text="Muito bem. Voce ja entendeu como perguntar e responder a idade em ingles.",
                ),
            ],
            11: [
                NarrationSegment(
                    language="pt-BR",
                    text="Vamos revisar a pergunta e as respostas principais da aula.",
                ),
                NarrationSegment(language="en-US", text=f"How old are you? {review_line}"),
                NarrationSegment(
                    language="pt-BR",
                    text="Otimo trabalho. Agora a estrutura I am mais numero mais years old ja esta pronta para uso.",
                ),
            ],
            12: [
                NarrationSegment(
                    language="pt-BR",
                    text="Nossa aula terminou. Sempre que alguem perguntar sua idade em ingles, voce ja sabe responder.",
                ),
                NarrationSegment(language="en-US", text="How old are you? Very good! See you next class!"),
                NarrationSegment(
                    language="pt-BR",
                    text="Muito bem. Ate a proxima aula de ingles.",
                ),
            ],
        }
        return chunks[scene_index]

    def _build_custom_scene_narration(
        self,
        scene_index: int,
        profile: TopicProfile,
        words: list[str],
        prompt: str,
    ) -> list[NarrationSegment]:
        theme = self._clean_prompt_label(self._extract_lesson_theme(prompt) or profile.focus)
        selected_words = [word.strip() for word in (words or profile.vocabulary) if word.strip()]
        if not selected_words:
            selected_words = self._extract_prompt_english_phrases(prompt)[:6]
        if not selected_words:
            selected_words = ["repeat after me"]
        if self._is_custom_command_lesson(profile):
            return self._build_custom_command_scene_narration(scene_index, profile, selected_words)

        objective = self._custom_objective_summary(prompt, theme, selected_words)
        joined_words = ", ".join(selected_words)
        echo_words = self._echo_words(selected_words) or "Repeat after me."
        teacher_line, student_line = self._custom_dialogue_lines(selected_words)

        chunks = {
            1: [
                NarrationSegment(
                    language="pt-BR",
                    text=f"Ola, turma. Hoje nossa aula é sobre {theme}. O objetivo principal é {objective}.",
                ),
                NarrationSegment(language="en-US", text=f"Let's learn: {joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Escute as palavras na tela e repita comigo bem devagar.",
                ),
            ],
            2: [
                NarrationSegment(
                    language="pt-BR",
                    text=f"Agora eu vou modelar as frases principais de {theme} em ingles para voce repetir.",
                ),
                NarrationSegment(language="en-US", text=f"Repeat after me: {joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Muito bem. Agora vamos repetir mais uma vez.",
                ),
                NarrationSegment(language="en-US", text=echo_words),
            ],
            3: [
                NarrationSegment(
                    language="pt-BR",
                    text=f"Vamos praticar um dialogo curto sobre {theme}.",
                ),
                NarrationSegment(language="en-US", speaker="teacher", text=teacher_line),
                NarrationSegment(language="en-US", speaker="student", text=student_line),
                NarrationSegment(
                    language="pt-BR",
                    text="Muito bem. Primeiro o professor falou e depois o aluno respondeu.",
                ),
            ],
            4: [
                NarrationSegment(
                    language="pt-BR",
                    text=f"Agora vamos reforcar as palavras e frases mais importantes de {theme}.",
                ),
                NarrationSegment(language="en-US", text=f"New words: {joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Escute com calma e repita do seu jeito.",
                ),
            ],
            5: [
                NarrationSegment(
                    language="pt-BR",
                    text=f"Hora do jogo. Pense na resposta correta para {theme} antes de ouvir o modelo.",
                ),
                NarrationSegment(language="en-US", text=f"Which one is it? {joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Boa. Isso ajuda a ligar som, escrita e significado.",
                ),
            ],
            6: [
                NarrationSegment(
                    language="pt-BR",
                    text=f"Mais um dialogo para praticar {theme} em contexto.",
                ),
                NarrationSegment(language="en-US", speaker="teacher", text=teacher_line),
                NarrationSegment(language="en-US", speaker="student", text=student_line),
                NarrationSegment(
                    language="pt-BR",
                    text="Excelente. Voce ja esta reconhecendo a estrutura principal da aula.",
                ),
            ],
            7: [
                NarrationSegment(
                    language="pt-BR",
                    text=f"Na historinha, essas palavras aparecem em uma situacao simples de {theme}.",
                ),
                NarrationSegment(language="en-US", text=f"Look. {joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Aponte para a tela quando ouvir a palavra correta.",
                ),
            ],
            8: [
                NarrationSegment(
                    language="pt-BR",
                    text=f"Agora mexa o corpo comigo enquanto repete as frases de {theme}.",
                ),
                NarrationSegment(language="en-US", text=f"Move and say: {joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Movimento e repeticao ajudam a guardar melhor o ingles.",
                ),
            ],
            9: [
                NarrationSegment(
                    language="pt-BR",
                    text=f"Quiz rapido sobre {theme}. Responda comigo.",
                ),
                NarrationSegment(language="en-US", text=f"Say it now: {joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Boa resposta. Vamos para mais uma rodada.",
                ),
            ],
            10: [
                NarrationSegment(
                    language="pt-BR",
                    text=f"Segunda rodada de pratica para fixar {theme}.",
                ),
                NarrationSegment(language="en-US", text=f"Your turn: {joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Muito bem. Seu ouvido ja esta mais atento para essas palavras.",
                ),
            ],
            11: [
                NarrationSegment(
                    language="pt-BR",
                    text=f"Vamos revisar tudo o que aprendemos sobre {theme}.",
                ),
                NarrationSegment(language="en-US", text=f"Repeat with me: {joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Excelente revisao. Agora ficou bem mais facil reconhecer o tema em ingles.",
                ),
            ],
            12: [
                NarrationSegment(
                    language="pt-BR",
                    text=f"Nossa aula sobre {theme} terminou. Guarde essas frases para usar na proxima atividade.",
                ),
                NarrationSegment(language="en-US", text=f"Very good! {joined_words}. See you soon!"),
                NarrationSegment(
                    language="pt-BR",
                    text="Muito bem. Ate a proxima aula de ingles.",
                ),
            ],
        }
        return chunks[scene_index]

    def _build_custom_command_scene_narration(
        self,
        scene_index: int,
        profile: TopicProfile,
        words: list[str],
    ) -> list[NarrationSegment]:
        meaning_summary = self._meaning_intro(self._meaning_list(profile, words)).rstrip(".!?")
        joined_words = ", ".join(words)
        lesson_label = "comandos e ações em inglês usados na sala de aula"

        chunks = {
            1: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        "Olá, turma. Hoje vamos aprender comandos e ações em inglês usados na sala de aula. "
                        "Essas são palavras que o professor usa para orientar a turma."
                    ),
                ),
                NarrationSegment(language="en-US", text=f"{joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        f"Essas primeiras palavras significam {meaning_summary}. "
                        "Elas aparecem quando precisamos olhar, prestar atenção ou mostrar alguma coisa."
                    ),
                ),
            ],
            2: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        "Agora vamos para mais quatro comandos importantes. "
                        "Eles aparecem quando mexemos nos materiais da aula."
                    ),
                ),
                NarrationSegment(language="en-US", text=f"{joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        f"Neste grupo, as ações significam {meaning_summary}. "
                        "Por exemplo, abrir o livro, fechar o caderno ou pegar um objeto."
                    ),
                ),
            ],
            3: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        "Aqui temos outro grupo de comandos que aparecem muito na sala de aula. "
                        "Eles ajudam a turma a participar e responder."
                    ),
                ),
                NarrationSegment(language="en-US", text=f"{joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        f"Agora pense no significado: {meaning_summary}. "
                        "São ações comuns quando a criança pergunta, responde, senta ou levanta."
                    ),
                ),
            ],
            4: [
                NarrationSegment(
                    language="pt-BR",
                    text="Agora repita comigo bem devagar. Primeiro eu falo, depois você repete.",
                ),
                NarrationSegment(language="en-US", text=f"{joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        f"Muito bem. Você está repetindo ações que significam {meaning_summary}. "
                        "Repetir ajuda a guardar a pronúncia."
                    ),
                ),
            ],
            5: [
                NarrationSegment(
                    language="pt-BR",
                    text="Vamos repetir de novo para fixar melhor. Enquanto escuta, pense também no significado.",
                ),
                NarrationSegment(language="en-US", text=f"{joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text=f"Se você entendeu {meaning_summary}, já está acompanhando muito bem a aula.",
                ),
            ],
            6: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        "Agora eu vou falar os comandos e você pensa no significado em português. "
                        "Assim a palavra em inglês fica ligada à ação correta."
                    ),
                ),
                NarrationSegment(language="en-US", text=f"{joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text=f"Se você pensou em {meaning_summary}, acertou.",
                ),
            ],
            7: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        "Hora da prática. Quando eu falar o comando, faça a ação comigo. "
                        "Imagine que você está dentro da sala de aula."
                    ),
                ),
                NarrationSegment(language="en-US", text="Stand up, sit down, open your book, close your book."),
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        "Muito bem. Agora você já sabe levantar, sentar, abrir e fechar durante a aula. "
                        "Esses comandos são usados o tempo todo pelo professor."
                    ),
                ),
            ],
            8: [
                NarrationSegment(
                    language="pt-BR",
                    text="Vamos revisar mais uma vez como um professor faria em sala. Ouça, entenda e depois fale.",
                ),
                NarrationSegment(language="en-US", text=f"{joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text=f"Lembre-se: aqui nós praticamos {meaning_summary}.",
                ),
            ],
            9: [
                NarrationSegment(
                    language="pt-BR",
                    text=(
                        f"Para terminar, ouça mais alguns {lesson_label}. "
                        "Veja se você consegue entender sozinho."
                    ),
                ),
                NarrationSegment(language="en-US", text="Look, open your book, sit down, stand up. Great job!"),
                NarrationSegment(
                    language="pt-BR",
                    text="Muito bem. Hoje você aprendeu comandos usados na sala de aula em inglês e o significado de cada um.",
                ),
            ],
            10: [
                NarrationSegment(
                    language="pt-BR",
                    text="Última revisão dos comandos principais da aula.",
                ),
                NarrationSegment(language="en-US", text=f"{joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text=f"Essas palavras significam {meaning_summary}.",
                ),
            ],
            11: [
                NarrationSegment(
                    language="pt-BR",
                    text="Repita comigo pela última vez.",
                ),
                NarrationSegment(language="en-US", text=f"{joined_words}."),
                NarrationSegment(
                    language="pt-BR",
                    text="Excelente. Seu ouvido já está reconhecendo esses comandos.",
                ),
            ],
            12: [
                NarrationSegment(
                    language="pt-BR",
                    text="Nossa aula terminou. Guarde esses comandos para usar na próxima atividade.",
                ),
                NarrationSegment(language="en-US", text="Great job. See you in the next English lesson."),
                NarrationSegment(
                    language="pt-BR",
                    text="Muito bem. Até a próxima aula de inglês.",
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
        if profile.key == "introductions":
            requested = self._extract_requested_introductions(prompt)
            if requested:
                return self._pad_vocabulary(requested, profile.vocabulary)
        if profile.key == "age":
            requested = self._extract_requested_age_vocabulary(prompt)
            if requested:
                return self._pad_vocabulary(requested, profile.vocabulary)
        if profile.key == "custom":
            return profile.vocabulary
        return profile.vocabulary

    def _primary_vocabulary(self, profile: TopicProfile, prompt: str, selected: list[str]) -> list[str]:
        if profile.key == "greetings":
            requested = self._extract_requested_greetings(prompt)
            if requested:
                return requested
        if profile.key == "introductions":
            requested = self._extract_requested_introductions(prompt)
            if requested:
                return requested
        if profile.key == "age":
            requested = self._extract_requested_age_vocabulary(prompt)
            if requested:
                return requested[:3]
        if profile.key == "custom":
            return selected[:3]
        return selected[:3]

    def _extract_requested_greetings(self, prompt: str) -> list[str]:
        lowered = self._normalize_lookup_text(prompt)
        ordered: list[str] = []
        greeting_map = (
            (("bom dia", "good morning"), "good morning"),
            (("boa tarde", "good afternoon"), "good afternoon"),
            (("boa noite", "good evening", "good night"), "good night"),
            (("oi", "ola", "hello"), "hello"),
            (("tchau", "adeus", "goodbye", "bye"), "goodbye"),
            (("por favor", "please"), "please"),
            (("obrigado", "obrigada", "thank you"), "thank you"),
        )

        for aliases, normalized in greeting_map:
            if any(alias in lowered for alias in aliases) and normalized not in ordered:
                ordered.append(normalized)

        return ordered

    def _extract_requested_introductions(self, prompt: str) -> list[str]:
        lowered = self._normalize_lookup_text(prompt)
        ordered: list[str] = []
        introduction_map = (
            (("meu nome", "my name is"), "my name is"),
            (
                ("como voce chama", "como voce se chama", "como voc chama", "qual e o seu nome", "qual seu nome", "what is your name", "what s your name"),
                "what is your name",
            ),
            (("muito prazer", "nice to meet you", "prazer em conhecer"), "nice to meet you"),
        )

        for aliases, normalized in introduction_map:
            if any(alias in lowered for alias in aliases) and normalized not in ordered:
                ordered.append(normalized)

        requested_name = self._extract_requested_name(prompt)
        insert_at = 2 if len(ordered) >= 2 else len(ordered)
        if requested_name is not None:
            ordered.insert(insert_at, f"i am {requested_name.lower()}")
        elif any(alias in lowered for alias in ("eu sou", "eeu sou", "me chamo", "i am")):
            ordered.insert(insert_at, "i am")

        return ordered

    def _pad_vocabulary(self, requested: list[str], fallback: list[str], minimum_size: int = 6) -> list[str]:
        merged = list(requested)
        for word in fallback:
            if word not in merged:
                merged.append(word)
            if len(merged) >= minimum_size:
                break
        return merged

    def _is_custom_command_lesson(self, profile: TopicProfile) -> bool:
        if profile.key != "custom":
            return False

        normalized_focus = self._normalize_lookup_text(profile.focus)
        focus_hints = ("comando", "acao", "acoes", "classroom", "sala de aula")
        if any(hint in normalized_focus for hint in focus_hints):
            return True

        command_hits = sum(1 for word in profile.vocabulary if self._looks_like_command_phrase(word))
        return command_hits >= min(4, len(profile.vocabulary))

    def _build_vocabulary_groups(
        self,
        profile: TopicProfile,
        vocabulary: list[str],
        primary: list[str],
        scene_count: int,
    ) -> list[list[str]]:
        if self._is_custom_command_lesson(profile) and len(vocabulary) >= 8:
            return self._build_command_lesson_groups(vocabulary, scene_count)

        if len(vocabulary) > 6:
            max_group_size = 4 if profile.key == "custom" else 3
            return self._build_balanced_vocabulary_groups(vocabulary, scene_count, max_group_size=max_group_size)

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

    def _build_command_lesson_groups(self, vocabulary: list[str], scene_count: int) -> list[list[str]]:
        batches = [vocabulary[index : index + 4] for index in range(0, len(vocabulary), 4)]
        first_batch = batches[0] if batches else vocabulary[:4]
        second_batch = batches[1] if len(batches) > 1 else first_batch
        third_batch = batches[2] if len(batches) > 2 else second_batch
        lookup = {self._normalize_lookup_text(word): word for word in vocabulary}

        def pick(*candidates: str) -> list[str]:
            selected: list[str] = []
            for candidate in candidates:
                word = lookup.get(self._normalize_lookup_text(candidate))
                if word is not None and word not in selected:
                    selected.append(word)
            return selected

        groups = [
            first_batch,
            second_batch,
            third_batch,
            pick("look", "find", "listen", "show") or first_batch,
            pick("open", "close", "sit down", "stand up") or second_batch,
            pick("ask", "answer", "add", "pick up") or third_batch,
            pick("stand up", "sit down", "open", "close") or second_batch,
            pick("look", "show", "ask", "answer") or first_batch,
            pick("look", "open", "sit down", "stand up") or third_batch,
        ]

        while len(groups) < scene_count:
            groups.append(groups[len(groups) % max(len(batches), 1)] if batches else vocabulary[:4])
        return groups[:scene_count]

    def _build_balanced_vocabulary_groups(
        self,
        vocabulary: list[str],
        scene_count: int,
        max_group_size: int,
    ) -> list[list[str]]:
        if not vocabulary:
            return [[]]

        group_count = min(scene_count, max(1, math.ceil(len(vocabulary) / max_group_size)))
        base_size, remainder = divmod(len(vocabulary), group_count)
        groups: list[list[str]] = []
        cursor = 0

        for group_index in range(group_count):
            size = base_size + (1 if group_index < remainder else 0)
            size = min(size, max_group_size)
            groups.append(vocabulary[cursor : cursor + size])
            cursor += size

        return groups or [vocabulary[:max_group_size]]

    def _display_words_for_scene(
        self,
        profile: TopicProfile,
        teaching_mode: str,
        current_words: list[str],
        full_vocabulary: list[str],
        narration: list[NarrationSegment],
    ) -> list[str]:
        if profile.key == "age" and teaching_mode != "dialogue":
            return self._age_display_words(current_words, full_vocabulary, narration)
        return current_words

    def _card_details_for_scene(self, profile: TopicProfile, words: list[str]) -> list[str]:
        details: list[str] = []
        for word in words:
            translation = self._translation(profile, word)
            if not translation or translation.lower() == word.lower():
                details.append("")
                continue
            details.append(translation[:1].upper() + translation[1:])
        return details

    def _age_display_words(
        self,
        current_words: list[str],
        full_vocabulary: list[str],
        narration: list[NarrationSegment],
    ) -> list[str]:
        spoken: list[str] = []
        question = next((word for word in full_vocabulary if self._normalize_lookup_text(word) == "how old are you"), None)
        answers = [
            word
            for word in full_vocabulary
            if self._normalize_lookup_text(word).startswith("i m ") and self._normalize_lookup_text(word).endswith("years old")
        ]

        for segment in narration:
            if segment.language != "en-US":
                continue
            for piece in re.split(r"(?<=[.!?])\s+", segment.text):
                normalized = self._extract_age_phrase(piece)
                if normalized and normalized not in spoken:
                    spoken.append(normalized)

        display: list[str] = []
        spoken_answers = [item for item in spoken if item.startswith("i'm ")]
        if spoken_answers:
            display.extend(spoken_answers)
            for answer in answers:
                if answer not in display:
                    display.append(answer)
                if len(display) >= 4:
                    break
            if question and len(display) < 4 and question not in display:
                display.append(question)
        else:
            if question:
                display.append(question)
            for answer in answers:
                if answer not in display:
                    display.append(answer)
                if len(display) >= 4:
                    break

        for word in current_words:
            if word not in display:
                display.append(word)
            if len(display) >= 4:
                break
        return display[:4] or current_words

    def _extract_age_phrase(self, text: str) -> str | None:
        normalized = self._normalize_lookup_text(text)
        if not normalized:
            return None
        if normalized.startswith("how old are you"):
            return "how old are you"
        match = re.search(r"\bi\s*m\s+([a-z0-9]+)\s+years\s+old\b", normalized)
        if match is None:
            return None
        age = AGE_NUMBER_WORDS.get(match.group(1))
        if age is None:
            return None
        return f"i'm {age} years old"

    def _display_phrase_case(self, text: str) -> str:
        words = []
        for word in text.split():
            if "'" in word:
                head, tail = word.split("'", 1)
                words.append(f"{head[:1].upper() + head[1:].lower()}'{tail.lower()}")
            else:
                words.append(word[:1].upper() + word[1:].lower())
        return " ".join(words)

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

    def _echo_words(self, words: list[str]) -> str:
        spoken_words = [word.strip().title() for word in words if word.strip()]
        if not spoken_words:
            return ""
        return ". ".join(spoken_words) + "."

    def _translation(self, profile: TopicProfile, word: str) -> str:
        lowered = word.lower()
        direct_translation = profile.translations.get(lowered)
        if direct_translation is not None:
            return direct_translation
        if lowered.startswith("i'm "):
            if lowered.endswith(" years old"):
                return f"eu tenho {word[4:]}"
            return f"eu sou {word[4:]}"
        if lowered.startswith("i am "):
            return f"eu sou {word[5:]}"
        if lowered.startswith("my name is "):
            return f"meu nome é {word[11:]}"
        return word

    def _extract_requested_age_vocabulary(self, prompt: str) -> list[str]:
        examples = self._select_age_examples(prompt)
        return ["how old are you", *[f"i'm {age} years old" for age in examples[:4]], "years old"]

    def _select_age_examples(self, prompt: str) -> list[str]:
        lowered = self._normalize_lookup_text(prompt)
        detected: list[str] = []
        for match in re.finditer(r"i\s+m\s+([a-z0-9]+)\s+years\s+old", lowered):
            age = AGE_NUMBER_WORDS.get(match.group(1))
            if age is not None and age not in detected:
                detected.append(age)

        ordered = [age for age in AGE_DEFAULT_EXAMPLES if age in detected]
        for age in detected:
            if age not in ordered:
                ordered.append(age)
        if not ordered:
            ordered = list(AGE_DEFAULT_EXAMPLES)
        for age in AGE_DEFAULT_EXAMPLES:
            if age not in ordered:
                ordered.append(age)
        return ordered[:4]

    def _topic_detection_text(self, prompt: str) -> str:
        explicit_theme = self._extract_lesson_theme(prompt)
        if explicit_theme:
            return explicit_theme

        about_topic = self._extract_about_topic(prompt)
        if about_topic:
            return about_topic

        objective = self._extract_lesson_objective(prompt)
        return objective or prompt

    def _build_custom_topic_profile(self, prompt: str) -> TopicProfile | None:
        theme = self._extract_lesson_theme(prompt) or self._extract_about_topic(prompt)
        if theme is None:
            return None

        cleaned_theme = self._clean_prompt_label(theme)
        english_phrases = self._extract_prompt_english_phrases(prompt)
        if not english_phrases:
            return None

        visual_style = self._extract_visual_style(prompt)
        visual_theme = (
            f"{visual_style}, cheerful school scene for children about {cleaned_theme}"
            if visual_style
            else f"playful classroom for children learning {cleaned_theme}, smiling students and speech bubbles"
        )
        return TopicProfile(
            key="custom",
            title_pt=self._format_custom_title(cleaned_theme),
            focus=cleaned_theme,
            vocabulary=english_phrases[:12],
            translations=self._custom_translation_map(prompt, english_phrases[:12]),
            visual_theme=visual_theme,
            matches=(),
        )

    def _extract_lesson_theme(self, prompt: str) -> str | None:
        return self._extract_prompt_section(
            prompt,
            "tema da aula",
            ("estilo visual", "objetivo da aula", "estrutura do video", "estrutura do vídeo", "elementos visuais", "mensagem final"),
        )

    def _extract_lesson_objective(self, prompt: str) -> str | None:
        return self._extract_prompt_section(
            prompt,
            "objetivo da aula",
            ("estilo visual", "estrutura do video", "estrutura do vídeo", "elementos visuais", "mensagem final", "o video deve", "o vídeo deve"),
        )

    def _extract_visual_style(self, prompt: str) -> str | None:
        return self._extract_prompt_section(
            prompt,
            "estilo visual",
            ("objetivo da aula", "estrutura do video", "estrutura do vídeo", "elementos visuais", "mensagem final"),
        )

    def _extract_about_topic(self, prompt: str) -> str | None:
        match = re.search(
            r"\bsobre\s+(.+?)(?=\b(?:para criancas|para crianças|com narracao|com narração|tema da aula|estilo visual|objetivo da aula|estrutura do video|estrutura do vídeo|elementos visuais|mensagem final)\b|$)",
            prompt,
            flags=re.IGNORECASE,
        )
        if match is None:
            return None
        return self._clean_prompt_label(match.group(1))

    def _extract_prompt_section(self, prompt: str, label: str, stop_labels: tuple[str, ...]) -> str | None:
        lowered = prompt.lower()
        label_index = lowered.find(label.lower())
        if label_index == -1:
            return None
        start = label_index + len(label)
        while start < len(prompt) and prompt[start] in " :\n\r\t":
            start += 1

        end = len(prompt)
        for stop_label in stop_labels:
            stop_index = lowered.find(stop_label.lower(), start)
            if stop_index != -1:
                end = min(end, stop_index)
        return self._clean_prompt_label(prompt[start:end])

    def _extract_prompt_english_phrases(self, prompt: str) -> list[str]:
        candidates: list[str] = []
        for phrase in self._extract_structured_english_list(prompt):
            self._append_unique_phrase(candidates, phrase)

        for match in re.finditer(r"\"([^\"]+)\"", prompt):
            self._append_english_phrase(candidates, match.group(1))

        normalized = prompt.replace(" and ", ", ").replace(" e ", ", ")
        for chunk in re.split(r"[.;:\n]", normalized):
            for part in chunk.split(","):
                if "\"" in part:
                    continue
                self._append_english_phrase(candidates, part)
        return candidates

    def _append_english_phrase(self, phrases: list[str], candidate: str) -> None:
        cleaned = self._clean_prompt_label(candidate)
        if not cleaned:
            return
        if self._looks_like_english_phrase(cleaned):
            self._append_unique_phrase(phrases, cleaned)
            return
        for phrase in self._extract_embedded_english_phrases(cleaned):
            self._append_unique_phrase(phrases, phrase)

    def _append_unique_phrase(self, phrases: list[str], candidate: str) -> None:
        lowered = candidate.lower()
        if lowered not in {item.lower() for item in phrases}:
            phrases.append(candidate)

    def _extract_structured_english_list(self, prompt: str) -> list[str]:
        normalized = self._normalize_lookup_text(prompt)
        for marker in STRUCTURED_ENGLISH_LIST_MARKERS:
            start = normalized.find(marker)
            if start == -1:
                continue
            tail = normalized[start + len(marker) :].lstrip(" :")
            if not tail:
                continue

            end = len(tail)
            for stop_marker in STRUCTURED_ENGLISH_STOP_MARKERS:
                marker_index = tail.find(stop_marker.strip())
                if marker_index != -1:
                    end = min(end, marker_index)
            extracted = tail[:end].strip()
            phrases = self._extract_embedded_english_phrases(extracted, allow_unknown_single_words=True)
            if phrases:
                return phrases
        return []

    def _extract_embedded_english_phrases(
        self,
        text: str,
        *,
        allow_unknown_single_words: bool = False,
    ) -> list[str]:
        normalized_tokens = self._normalize_lookup_text(text).split()
        if not normalized_tokens:
            return []

        multiword_tokens = sorted(
            (phrase.split() for phrase in ENGLISH_MULTIWORD_PHRASES),
            key=len,
            reverse=True,
        )
        phrases: list[str] = []
        index = 0
        while index < len(normalized_tokens):
            matched_phrase = next(
                (
                    " ".join(tokens)
                    for tokens in multiword_tokens
                    if normalized_tokens[index : index + len(tokens)] == tokens
                ),
                None,
            )
            if matched_phrase is not None:
                phrases.append(matched_phrase)
                index += len(matched_phrase.split())
                continue

            token = normalized_tokens[index]
            if token in PORTUGUESE_HINT_WORDS:
                break
            if token in ENGLISH_HINT_WORDS and token not in WEAK_ENGLISH_HINT_WORDS:
                phrases.append(token)
            elif allow_unknown_single_words and token.isalpha() and len(token) >= 2:
                phrases.append(token)
            index += 1

        return phrases

    def _custom_translation_map(self, prompt: str, phrases: list[str]) -> dict[str, str]:
        translations: dict[str, str] = {}
        for phrase in phrases:
            match = re.search(
                rf"\b{re.escape(phrase)}\b[!\"'”’\s:,-]*significa\s+([^\.\n\r\"”']+)",
                prompt,
                flags=re.IGNORECASE,
            )
            if match is not None:
                cleaned = self._clean_prompt_label(match.group(1))
                if cleaned:
                    translations[phrase.lower()] = cleaned.lower()

        for phrase in phrases:
            lowered = phrase.lower()
            if lowered not in translations and lowered in COMMON_CUSTOM_TRANSLATIONS:
                translations[lowered] = COMMON_CUSTOM_TRANSLATIONS[lowered]
        return translations

    def _looks_like_english_phrase(self, phrase: str) -> bool:
        normalized = self._normalize_lookup_text(phrase)
        words = normalized.split()
        if not words or len(words) > 8:
            return False

        english_hits = sum(1 for word in words if word in ENGLISH_HINT_WORDS)
        strong_english_hits = sum(
            1 for word in words if word in ENGLISH_HINT_WORDS and word not in WEAK_ENGLISH_HINT_WORDS
        )
        portuguese_hits = sum(1 for word in words if word in PORTUGUESE_HINT_WORDS)
        if english_hits == 0 or strong_english_hits == 0:
            return False
        if portuguese_hits > 0:
            return False
        return True

    def _custom_dialogue_lines(self, phrases: list[str]) -> tuple[str, str]:
        cleaned = [self._clean_prompt_label(phrase) for phrase in phrases if self._clean_prompt_label(phrase)]
        if not cleaned:
            return ("Let's learn.", "Okay.")

        if len(cleaned) >= 3 and all(self._looks_like_command_phrase(phrase) for phrase in cleaned[:4]):
            midpoint = max(1, math.ceil(min(len(cleaned), 4) / 2))
            teacher_group = cleaned[:midpoint]
            student_group = cleaned[midpoint:4] or [cleaned[-1]]
            teacher_line = " ".join(self._ensure_sentence(phrase) for phrase in teacher_group)
            student_line = " ".join(self._ensure_sentence(phrase) for phrase in student_group)
            return (teacher_line, student_line)

        first = self._ensure_sentence(cleaned[0])
        if len(cleaned) == 1:
            return (f"Listen: {first}", first)

        second = self._ensure_sentence(cleaned[1])
        if self._looks_like_command_phrase(cleaned[0]) and self._looks_like_command_phrase(cleaned[1]):
            return (first, second)
        if self._looks_like_question(first):
            return (first, second)
        if len(cleaned[0].split()) <= 3:
            return (f"Look. {self._ensure_sentence(cleaned[0])}", second)
        return (first, second)

    def _looks_like_question(self, text: str) -> bool:
        normalized = self._normalize_lookup_text(text)
        return text.strip().endswith("?") or normalized.startswith(("how ", "what ", "where ", "when ", "who ", "why ", "can ", "do ", "is ", "are "))

    def _ensure_sentence(self, text: str) -> str:
        cleaned = self._clean_prompt_label(text)
        if not cleaned:
            return ""
        if cleaned[-1] in ".!?":
            return cleaned
        if self._looks_like_question(cleaned):
            return f"{cleaned}?"
        return f"{cleaned}."

    def _looks_like_command_phrase(self, text: str) -> bool:
        normalized = self._normalize_lookup_text(text)
        if not normalized:
            return False
        return normalized in COMMON_CUSTOM_TRANSLATIONS or normalized in ENGLISH_MULTIWORD_PHRASES

    def _custom_objective_summary(self, prompt: str, theme: str, selected_words: list[str]) -> str:
        raw_objective = self._clean_prompt_label(self._extract_lesson_objective(prompt) or f"aprender {theme} em ingles")
        raw_objective = raw_objective.replace('"', "").replace("'", "")
        normalized = self._normalize_lookup_text(raw_objective)
        if (
            len(raw_objective) > 120
            or ":" in raw_objective
            or any(marker in normalized for marker in STRUCTURED_ENGLISH_LIST_MARKERS)
        ):
            normalized_theme = self._normalize_lookup_text(theme)
            if any(token in normalized_theme for token in ("comando", "acao", "acoes")):
                return "aprender e praticar comandos e acoes em ingles"
            return "aprender e praticar o vocabulario principal desta aula"
        return raw_objective

    def _clean_prompt_label(self, text: str) -> str:
        cleaned = " ".join(text.strip().split())
        return cleaned.strip(" -,:;.\"'")

    def _format_custom_title(self, theme: str) -> str:
        words = self._clean_prompt_label(theme).split()
        if not words:
            return "Tema Personalizado em Ingles"
        small_words = {"de", "da", "do", "das", "dos", "e", "em"}
        formatted = [word if index > 0 and word.lower() in small_words else word.capitalize() for index, word in enumerate(words)]
        return " ".join(formatted)

    def _focus_summary_text(self, focus: str) -> str:
        normalized = self._normalize_lookup_text(focus)
        if "ingles" in normalized or "english" in normalized:
            return focus
        return f"{focus} em inglês"

    def _pick_topic(self, prompt: str) -> TopicProfile:
        best_profile, _best_score = self._pick_topic_match(prompt)
        if best_profile is not None:
            return best_profile
        custom_profile = self._build_custom_topic_profile(prompt)
        if custom_profile is not None:
            return custom_profile
        return TOPIC_PROFILES[0]

    def _pick_topic_match(self, prompt: str) -> tuple[TopicProfile | None, int]:
        lowered = self._normalize_lookup_text(self._topic_detection_text(prompt))
        best_profile: TopicProfile | None = None
        best_score = 0
        for profile in TOPIC_PROFILES:
            score = sum(1 for token in profile.matches if self._prompt_matches_token(lowered, token))
            if score > best_score:
                best_profile = profile
                best_score = score
        return best_profile, best_score

    def _prompt_matches_token(self, prompt: str, token: str) -> bool:
        normalized_token = self._normalize_lookup_text(token)
        if not normalized_token:
            return False
        if " " in normalized_token:
            return normalized_token in prompt
        return re.search(rf"\b{re.escape(normalized_token)}\w*\b", prompt) is not None

    def _extract_requested_name(self, prompt: str) -> str | None:
        lowered = self._normalize_lookup_text(prompt)
        match = re.search(r"(?:eu sou|eeu sou|me chamo|i am)\s+([a-z]{2,20})\b", lowered)
        if match is None:
            return None
        return match.group(1).title()

    def _normalize_lookup_text(self, text: str) -> str:
        lowered = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
        lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
        return " ".join(lowered.split())

    def _apply_pt_br_accents(self, text: str) -> str:
        updated = text
        for source, target in PT_BR_ACCENT_REPLACEMENTS:
            pattern = re.compile(rf"\b{re.escape(source)}\b", flags=re.IGNORECASE)
            updated = pattern.sub(lambda match: self._match_case(target, match.group(0)), updated)
        return updated

    def _match_case(self, replacement: str, original: str) -> str:
        original_words = original.split()
        replacement_words = replacement.split()
        if len(original_words) == len(replacement_words) and len(original_words) > 1:
            adjusted_words: list[str] = []
            for original_word, replacement_word in zip(original_words, replacement_words):
                if original_word.isupper():
                    adjusted_words.append(replacement_word.upper())
                elif original_word[:1].isupper():
                    adjusted_words.append(replacement_word[:1].upper() + replacement_word[1:])
                else:
                    adjusted_words.append(replacement_word)
            return " ".join(adjusted_words)
        if original.isupper():
            return replacement.upper()
        if original[:1].isupper():
            return replacement[:1].upper() + replacement[1:]
        return replacement

    def _normalize_pt_br_scene(self, scene: LessonScene) -> LessonScene:
        normalized_narration = [
            segment.model_copy(update={"text": self._apply_pt_br_accents(segment.text)})
            if segment.language == "pt-BR"
            else segment
            for segment in scene.narration
        ]
        return scene.model_copy(update={"narration": normalized_narration, "title": self._apply_pt_br_accents(scene.title.strip())})

    def _split_mixed_language_scene(self, scene: LessonScene, plan_vocabulary: list[str]) -> LessonScene:
        candidates = self._english_split_candidates(scene, plan_vocabulary)
        if not candidates:
            return scene

        normalized_narration: list[NarrationSegment] = []
        for segment in scene.narration:
            if segment.language != "pt-BR":
                normalized_narration.append(segment)
                continue
            normalized_narration.extend(self._split_pt_br_segment(segment, candidates))
        return scene.model_copy(update={"narration": normalized_narration})

    def _english_split_candidates(self, scene: LessonScene, plan_vocabulary: list[str]) -> list[str]:
        candidates: list[str] = []
        for phrase in ENGLISH_META_PHRASES:
            self._add_candidate_phrase(candidates, phrase)
        for phrase in [*plan_vocabulary, *scene.vocabulary]:
            self._add_candidate_phrase(candidates, phrase)
        for segment in scene.narration:
            if segment.language != "en-US":
                continue
            for piece in re.split(r"(?<=[.!?])\s+", segment.text):
                self._add_candidate_phrase(candidates, piece)
        return sorted(candidates, key=lambda item: (-len(item), item.lower()))

    def _add_candidate_phrase(self, candidates: list[str], phrase: str) -> None:
        cleaned = self._clean_prompt_label(phrase)
        if len(cleaned) < 2:
            return
        lowered = cleaned.lower()
        if lowered not in {item.lower() for item in candidates}:
            candidates.append(cleaned)

    def _split_pt_br_segment(self, segment: NarrationSegment, candidates: list[str]) -> list[NarrationSegment]:
        pattern = re.compile("|".join(re.escape(candidate) for candidate in candidates), flags=re.IGNORECASE)
        pieces: list[NarrationSegment] = []
        cursor = 0

        for match in pattern.finditer(segment.text):
            start = match.start()
            end = self._consume_english_trailing_punctuation(segment.text, match.end())
            before = self._clean_pt_br_fragment(segment.text[cursor:start])
            english = self._clean_english_fragment(segment.text[start:end])
            if before:
                pieces.append(segment.model_copy(update={"text": before}))
            if english:
                pieces.append(
                    NarrationSegment(
                        language="en-US",
                        speaker=segment.speaker,
                        text=english,
                    )
                )
            cursor = end

        after = self._clean_pt_br_fragment(segment.text[cursor:])
        if after:
            pieces.append(segment.model_copy(update={"text": after}))
        return pieces or [segment]

    def _consume_english_trailing_punctuation(self, text: str, end: int) -> int:
        cursor = end
        while cursor < len(text) and text[cursor] in ".!?\"'":
            cursor += 1
        return cursor

    def _clean_pt_br_fragment(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip()
        cleaned = cleaned.lstrip(",;: ")
        return cleaned

    def _clean_english_fragment(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip()
        cleaned = cleaned.strip(",;: ")
        return cleaned

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
            normalized_source_scene = self._split_mixed_language_scene(self._normalize_pt_br_scene(scene), plan.vocabulary)
            normalized_scene = normalized_source_scene.model_copy(
                update={
                    "scene_id": scene.scene_id or f"scene-{index:02d}",
                    "duration_seconds": durations[index - 1],
                    "background_palette": scene.background_palette or self._palette_for_scene(index),
                    "title": self._apply_pt_br_accents(normalized_source_scene.title.strip()) or f"Cena {index}",
                    "visual_prompt": normalized_source_scene.visual_prompt.strip() or "children classroom illustration",
                }
            )
            normalized_scenes.append(normalized_scene)

        return plan.model_copy(
            update={
                "duration_minutes": request.duration_minutes,
                "target_age": request.target_age,
                "title": self._apply_pt_br_accents(plan.title),
                "summary": self._apply_pt_br_accents(plan.summary),
                "style": self._apply_pt_br_accents(plan.style),
                "learning_objectives": [self._apply_pt_br_accents(item) for item in plan.learning_objectives],
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
