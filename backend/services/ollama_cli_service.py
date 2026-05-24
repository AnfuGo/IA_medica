import os
import re
import shutil
import subprocess
from pathlib import Path


DEFAULT_OLLAMA_MODEL = "mistral:latest"
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 180
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class OllamaCliError(RuntimeError):
    """Erro ao consultar o Ollama via CLI."""


def get_ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)


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
    prompt: str,
    model: str | None = None,
    timeout_seconds: int | None = None,
) -> str:
    if not prompt.strip():
        raise OllamaCliError("prompt vazio")

    resolved_model = model or get_ollama_model()
    resolved_timeout = timeout_seconds or get_ollama_timeout()
    command = [get_ollama_exe(), "run", resolved_model, prompt]

    try:
        result = subprocess.run(
            command,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=resolved_timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise OllamaCliError(
            "Ollama CLI nao encontrado. Defina OLLAMA_EXE com o caminho do ollama.exe."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise OllamaCliError(
            f"Timeout ao consultar Ollama CLI apos {resolved_timeout} segundos"
        ) from exc

    stdout = clean_ollama_output(result.stdout)
    stderr = clean_ollama_output(result.stderr)

    if result.returncode != 0:
        detail = stderr or stdout or f"codigo de saida {result.returncode}"
        raise OllamaCliError(f"Ollama CLI falhou: {detail}")

    if not stdout:
        raise OllamaCliError("Ollama CLI retornou resposta vazia")

    return stdout
