import argparse
import os
import subprocess
import sys
import textwrap
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_PYTHON = PROJECT_ROOT / "venv311" / "Scripts" / "python.exe"
DEFAULT_TIMEOUT_SECONDS = 120


CHILD_CODE = r"""
import json
import os
import sys
import time

from backend.services.ollama_cli_service import (
    OllamaCliError,
    get_ollama_exe,
    get_ollama_model,
    query_ollama_cli,
)


def build_prompt(question: str, max_tokens: int) -> str:
    return (
        "Voce e um assistente medico local para um prototipo IoT. "
        "Responda em portugues do Brasil, com objetividade e seguranca. "
        "Nao invente diagnosticos e oriente procurar atendimento medico "
        "em sinais de gravidade.\n\n"
        f"Use no maximo {max_tokens} tokens.\n"
        f"Pergunta: {question}\n"
        "Resposta:"
    )


def main() -> int:
    # Integracao Python -> Ollama/Mistral via CLI:
    # este processo filho valida a IA local sem carregar TTS nem Flask.
    model = os.getenv("OLLAMA_MODEL", get_ollama_model())
    question = os.getenv("MISTRAL_TEST_QUESTION", "Explique em uma frase o que e gripe.")
    cli_timeout = int(float(os.getenv("OLLAMA_CLI_TIMEOUT", "90")))
    max_tokens = int(os.getenv("MISTRAL_TEST_MAX_TOKENS", "48"))

    started_at = time.monotonic()
    answer = query_ollama_cli(
        build_prompt(question, max_tokens),
        model=model,
        timeout_seconds=cli_timeout,
    )
    elapsed = time.monotonic() - started_at

    if not answer:
        raise RuntimeError("Ollama CLI retornou resposta vazia")

    print(json.dumps(
        {
            "status": "ok",
            "model": model,
            "ollama_exe": get_ollama_exe(),
            "ollama_mode": "cli_subprocess",
            "elapsed_seconds": round(elapsed, 2),
            "question": question,
            "answer": answer,
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Erro ao testar Mistral/Ollama via CLI: {exc}", file=sys.stderr)
        raise SystemExit(1)
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Testa o modelo Mistral/Ollama em um processo Python filho."
    )
    parser.add_argument(
        "--question",
        default="Explique em uma frase o que e gripe.",
        help="Pergunta enviada ao modelo Mistral.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Timeout total do processo filho em segundos.",
    )
    parser.add_argument(
        "--python",
        default=str(PROJECT_PYTHON),
        help="Interpretador Python usado no processo filho.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=48,
        help="Limite de tokens da resposta gerada pelo Mistral.",
    )
    parser.add_argument(
        "--ollama-exe",
        default="",
        help="Caminho opcional para o ollama.exe. Tambem pode usar OLLAMA_EXE.",
    )
    parser.add_argument(
        "--model",
        default="",
        help="Modelo Ollama usado no teste. Padrao: OLLAMA_MODEL ou mistral:latest.",
    )
    parser.add_argument(
        "--cli-timeout",
        type=int,
        default=90,
        help="Timeout da chamada 'ollama run' em segundos.",
    )
    return parser.parse_args()


def run_mistral_process(
    question: str,
    timeout: int,
    python_exe: str,
    max_tokens: int,
    ollama_exe: str,
    model: str,
    cli_timeout: int,
) -> subprocess.CompletedProcess[str]:
    child_env = os.environ.copy()
    child_env["MISTRAL_TEST_QUESTION"] = question
    child_env["MISTRAL_TEST_MAX_TOKENS"] = str(max_tokens)
    child_env["OLLAMA_CLI_TIMEOUT"] = str(cli_timeout)
    if ollama_exe:
        child_env["OLLAMA_EXE"] = ollama_exe
    if model:
        child_env["OLLAMA_MODEL"] = model

    command = [
        python_exe,
        "-c",
        textwrap.dedent(CHILD_CODE),
    ]

    return subprocess.run(
        command,
        cwd=str(PROJECT_ROOT),
        env=child_env,
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def main() -> int:
    args = parse_args()
    python_path = Path(args.python)

    if not python_path.exists():
        print(f"Python do projeto nao encontrado: {python_path}", file=sys.stderr)
        return 1

    try:
        result = run_mistral_process(
            args.question,
            args.timeout,
            str(python_path),
            args.max_tokens,
            args.ollama_exe,
            args.model,
            args.cli_timeout,
        )
    except subprocess.TimeoutExpired:
        print(
            f"Timeout ao testar Mistral/Ollama apos {args.timeout} segundos.",
            file=sys.stderr,
        )
        return 124

    if result.stdout:
        print(result.stdout.strip())

    if result.stderr:
        print(result.stderr.strip(), file=sys.stderr)

    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
