from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import Settings, get_settings
from app.job_store import JobStore
from app.orchestrator import RenderOrchestrator
from app.schemas import JobStatus, RenderRequest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gera videos infantis bilingues via prompt sem depender da interface web."
    )
    parser.add_argument("--prompt", required=True, help="Pedido da aula em linguagem natural.")
    parser.add_argument("--duration", type=int, default=5, help="Duracao total em minutos.")
    parser.add_argument("--target-age", default="5-8", help="Faixa etaria alvo.")
    parser.add_argument("--lesson-number", type=int, default=1, help="Numero da aula.")
    parser.add_argument("--step-number", type=int, default=1, help="Numero do passo do video.")
    parser.add_argument(
        "--visual-backend",
        default="template",
        choices=["template", "cogvideox"],
        help="Backend visual do render.",
    )
    parser.add_argument(
        "--local-planner",
        action="store_true",
        help="Desliga o Ollama e usa o planejador local.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Imprime o resultado completo em JSON.",
    )
    parser.add_argument(
        "--narration-style",
        default="natural",
        choices=["natural", "animated"],
        help="Preset de narracao.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    base_settings = get_settings()
    settings = Settings(**base_settings.model_dump())
    if args.local_planner:
        settings = settings.model_copy(update={"use_ollama": False})
    settings.ensure_directories()

    orchestrator = RenderOrchestrator(settings, JobStore(settings))
    request = RenderRequest(
        prompt=args.prompt,
        duration_minutes=args.duration,
        target_age=args.target_age,
        lesson_number=args.lesson_number,
        step_number=args.step_number,
        planner_mode="local" if args.local_planner else "auto",
        visual_backend=args.visual_backend,
        narration_style=args.narration_style,
    )
    job = orchestrator.run_sync(request)
    payload = job.model_dump(mode="json")

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"job_id={job.job_id}")
        print(f"status={job.status}")
        if job.output_video_path:
            print(f"video={job.output_video_path}")
        if job.error:
            print(job.error)

    return 0 if job.status == JobStatus.completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
