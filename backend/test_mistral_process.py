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

import requests


def build_prompt(question: str) -> str:
    return (
        "Voce e um assistente medico local para um prototipo IoT. "
        "Responda em portugues do Brasil, com objetividade e seguranca. "
        "Nao invente diagnosticos e oriente procurar atendimento medico "
        "em sinais de gravidade.\n\n"
        f"Pergunta: {question}\n"
        "Resposta:"
    )


def main() -> int:
    # Integracao Python -> Ollama/Mistral:
    # este processo filho valida a IA local sem carregar TTS nem Flask.
    ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
    model = os.getenv("OLLAMA_MODEL", "mistral:latest")
    question = os.getenv("MISTRAL_TEST_QUESTION", "Explique em uma frase o que e gripe.")
    read_timeout = float(os.getenv("OLLAMA_READ_TIMEOUT", "90"))

    payload = {
        "model": model,
        "prompt": build_prompt(question),
        "stream": False,
        "options": {"temperature": 0.2},
    }

    started_at = time.monotonic()
    response = requests.post(ollama_url, json=payload, timeout=(5, read_timeout))
    response.raise_for_status()

    data = response.json()
    answer = str(data.get("response", "")).strip()
    elapsed = time.monotonic() - started_at

    if not answer:
        raise RuntimeError("Ollama retornou resposta vazia")

    print(json.dumps(
        {
            "status": "ok",
            "model": model,
            "ollama_url": ollama_url,
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
        print(f"Erro ao testar Mistral/Ollama: {exc}", file=sys.stderr)
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
    return parser.parse_args()


def run_mistral_process(question: str, timeout: int, python_exe: str) -> subprocess.CompletedProcess[str]:
    child_env = os.environ.copy()
    child_env["MISTRAL_TEST_QUESTION"] = question

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
        result = run_mistral_process(args.question, args.timeout, str(python_path))
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
