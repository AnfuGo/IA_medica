import os
import re
import shutil
from pathlib import Path

import requests


DEFAULT_OLLAMA_MODEL = "mistral:latest"
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 600
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class OllamaCliError(RuntimeError):
    """Erro ao consultar o Ollama via CLI."""


def get_ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)


def get_ollama_base_url() -> str:
    configured = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
    return configured.rstrip("/")


def _path_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def get_ollama_exe() -> str:
    configured = os.getenv("OLLAMA_EXE")
    if configured:
        return configured

    found = shutil.which("ollama")
    if found:
        return found

    candidates: list[Path] = []
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        candidates.extend(
            [
                Path(local_app_data) / "Programs" / "Ollama" / "ollama.exe",
                Path(local_app_data) / "Ollama" / "ollama.exe",
            ]
        )

    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        base_dir = os.getenv(env_name)
        if base_dir:
            candidates.append(Path(base_dir) / "Ollama" / "ollama.exe")

    for candidate in candidates:
        if _path_exists(candidate):
            return str(candidate)

    return "ollama"


def get_ollama_timeout(default: int = DEFAULT_OLLAMA_TIMEOUT_SECONDS) -> int:
    configured = os.getenv("OLLAMA_CLI_TIMEOUT")
    if not configured:
        return default

    try:
        timeout = int(float(configured))
    except ValueError as exc:
        raise OllamaCliError(f"OLLAMA_CLI_TIMEOUT invalido: {configured}") from exc

    if timeout <= 0:
        raise OllamaCliError("OLLAMA_CLI_TIMEOUT deve ser maior que zero")

    return timeout


def clean_ollama_output(text: str) -> str:
    cleaned = ANSI_ESCAPE_RE.sub("", text).replace("\r", "\n")
    lines = []

    for line in cleaned.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(">>>"):
            continue
        lines.append(stripped)

    return "\n".join(lines).strip()


def query_ollama_cli(
    prompt: str | None = None,
    model: str | None = None,
    timeout_seconds: int | None = None,
    max_tokens: int = 48,
    messages: list[dict[str, str]] | None = None,
) -> str:
    resolved_model = model or get_ollama_model()
    resolved_timeout = timeout_seconds or get_ollama_timeout()
    url = f"{get_ollama_base_url()}/api/chat"

    if messages is None:
        if prompt is None or not prompt.strip():
            raise OllamaCliError("prompt vazio")
        messages_payload = [
            {
                "role": "user",
                "content": prompt,
            }
        ]
    else:
        messages_payload = []
        for message in messages:
            if not isinstance(message, dict):
                raise OllamaCliError("messages deve conter dicionarios")

            role = str(message.get("role") or "").strip()
            content = str(message.get("content") or "").strip()
            if not role or not content:
                continue
            messages_payload.append(
                {
                    "role": role,
                    "content": content,
                }
            )

        if not messages_payload:
            raise OllamaCliError("messages vazias")

    payload = {
        "model": resolved_model,
        "messages": messages_payload,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
        },
        "keep_alive": "5m",
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=resolved_timeout,
        )
    except requests.RequestException as exc:
        raise OllamaCliError(
            f"Falha ao consultar Ollama via API HTTP em {url}"
        ) from exc

    if response.status_code >= 400:
        detail = clean_ollama_output(response.text) or f"codigo de saida HTTP {response.status_code}"
        raise OllamaCliError(f"Ollama API falhou: {detail}")

    try:
        data = response.json()
    except ValueError as exc:
        raise OllamaCliError("Ollama API retornou JSON invalido") from exc

    message = data.get("message") or {}
    stdout = clean_ollama_output(
        str(message.get("content") or data.get("response") or "")
    )

    if not stdout:
        raise OllamaCliError("Ollama API retornou resposta vazia")

    return stdout
