# Kids Bilingual Video Studio

Aplicacao em `FastAPI` para receber um prompt como:

`crie um video de 5 minutos sobre aula de ingles para criancas`

e transformar isso em:

- roteiro infantil bilingue com `pt-BR + English`
- narracao automatica com vozes offline
- cenas visuais coloridas
- um arquivo final `.mp4`
- condução de aula com postura de professora de ingles infantil

O projeto foi pensado para rodar em Docker e usar componentes abertos:

- `Ollama` para gerar o plano da aula com um modelo aberto
- `FFmpeg` para montar o video
- backend visual opcional `CogVideoX` para quem tiver GPU e quiser trocar as cenas estaticas por clipes gerados por IA open source

Agora a aplicacao aceita dois modos de planejamento:

- `planner_mode=local`: gera tudo sem depender do Ollama
- `planner_mode=auto`: tenta Ollama e faz fallback local se necessario

E dois presets de texto de narracao:

- `narration_style=natural`: texto mais natural
- `narration_style=animated`: texto mais animado para publico infantil

## Arquitetura

1. O usuario envia um `prompt` para `POST /api/v1/renders`.
2. O backend gera um `LessonPlan` estruturado.
   Se `Ollama` estiver indisponivel, entra um fallback local para nao travar a aplicacao.
3. Cada cena recebe:
   - condução pedagogica de professora de ingles
   - texto em `pt-BR`
   - trechos curtos em `en-US`
   - palavras na tela
   - prompt visual
4. O `Piper` gera a narracao com vozes offline em `pt-BR` e `en-US`.
5. O `FFmpeg` monta o `MP4` final com audio e destaque visual nos cards quando as palavras entram em foco.

## Rodando com Docker

Copie o arquivo de exemplo se quiser customizar variaveis:

```bash
Copy-Item .env.example .env
```

Suba a aplicacao e o Ollama:

```bash
docker compose up --build
```

Em outro terminal, puxe o modelo aberto que vai escrever o roteiro:

```bash
docker compose --profile setup run --rm ollama-pull
```

Depois abra:

`http://localhost:8000`

## Exemplo de uso via API

```bash
curl -X POST http://localhost:8000/api/v1/renders \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Crie um video de 5 minutos sobre cores em ingles para criancas de 5 a 8 anos, com narracao em pt-BR mesclando palavras e frases curtas em ingles, mini-jogos e revisao final.",
    "lesson_number": 1,
    "step_number": 1,
    "duration_minutes": 5,
    "planner_mode": "local",
    "narration_style": "natural",
    "visual_backend": "template"
  }'
```

Consultar status:

```bash
curl http://localhost:8000/api/v1/renders/<job_id>
```

Baixar video:

```bash
curl -L http://localhost:8000/api/v1/renders/<job_id>/download --output aula.mp4
```

## Backends visuais

### `template`

Modo padrao. Cria cenas infantis fixas, rapidas e leves. Este e o modo mais estavel para gerar videos de 5 minutos.

### `cogvideox`

Modo opcional para GPU. Usa `diffusers` com `CogVideoXImageToVideoPipeline` e exige build com as dependencias pesadas:

```bash
docker compose build --build-arg INSTALL_VIDEO_AI=true
```

Depois envie o request com:

```json
{
  "visual_backend": "cogvideox"
}
```

Se esse backend falhar, a aplicacao volta automaticamente para a cena estatica.

## Linha de comando

Tambem e possivel gerar video sem abrir a interface web:

```bash
python -m app.cli --prompt "Crie um video de 1 minuto sobre cores em ingles para criancas" --lesson-number 1 --step-number 1 --duration 1 --local-planner --visual-backend template --narration-style natural --json
```

Ou, se o script estiver no `PATH`:

```bash
kids-video --prompt "Crie um video de 5 minutos sobre animais em ingles para criancas" --lesson-number 1 --step-number 1 --duration 5 --local-planner --visual-backend template --narration-style animated
```

## Interface web

Para abrir a interface web local:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Depois abra `http://localhost:8000`.

Para o melhor resultado local, use:

- `Aula` e `Passo` para organizar sua serie
- `Planejador: Local rapido`
- `Narracao: Texto natural`
- `Visual backend: Template local`

## Estrutura

```text
app/
  api.py
  config.py
  job_store.py
  main.py
  narration.py
  orchestrator.py
  planner.py
  schemas.py
  video.py
  video_ai.py
  visuals.py
  web/index.html
docker/
  entrypoint.sh
tests/
  test_fallback_planner.py
```

## Observacoes praticas

- O modo `template` e o mais indicado para uso continuo e previsivel.
- O host atual precisa de `Docker`; fora do container, `ffmpeg` e `piper` precisam estar instalados.
- A aplicacao salva jobs e videos em `./data`.

## Proximos passos uteis

- adicionar trilha musical infantil com volume controlado
- gerar legendas `.srt`
- plugar um banco de dados para historico e fila distribuida
- trocar a UI estatica por dashboard de producao
