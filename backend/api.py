import logging
import os
import shutil
import subprocess
import time
import uuid
import wave
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, request
from flask_cors import CORS

try:
    from backend.services.ollama_cli_service import (
        OllamaCliError,
        get_ollama_exe,
        get_ollama_model,
        query_ollama_cli,
    )
except ImportError:
    from services.ollama_cli_service import (
        OllamaCliError,
        get_ollama_exe,
        get_ollama_model,
        query_ollama_cli,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUDIO_OUTPUT_DIR = PROJECT_ROOT / "audio" / "output"
AUDIO_REF_DIR = PROJECT_ROOT / "audio" / "ref"
DEFAULT_PIPER_MODEL = PROJECT_ROOT / "models" / "pt_BR-faber-medium.onnx"
DEFAULT_XTTS_MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"

DEFAULT_PACKET_BYTES = 1024
MIN_PACKET_BYTES = 256
MAX_PACKET_BYTES = 8192
MIN_BITRATE_BPS = 16_000
MAX_BITRATE_BPS = 2_000_000
SUPPORTED_REF_EXTENSIONS = {".wav", ".mp3", ".flac"}

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
_xtts_model = None


def get_piper_exe() -> Path:
    configured = os.getenv("PIPER_EXE")
    if configured:
        return Path(configured)

    found = shutil.which("piper")
    if found:
        return Path(found)

    return Path(r"C:\piper\piper.exe")


def get_piper_model() -> Path:
    configured = os.getenv("PIPER_MODEL")
    if not configured:
        return DEFAULT_PIPER_MODEL

    model_path = Path(configured)
    if model_path.is_absolute():
        return model_path

    return PROJECT_ROOT / model_path


def get_xtts_model_name() -> str:
    return os.getenv("XTTS_MODEL", DEFAULT_XTTS_MODEL)


def get_tts_engine(payload: dict[str, Any] | None = None) -> str:
    configured = None
    if payload:
        configured = payload.get("tts_engine")

    engine = str(configured or os.getenv("TTS_ENGINE", "auto")).strip().lower()
    if engine not in {"auto", "xtts", "piper"}:
        raise ValueError("tts_engine deve ser 'auto', 'xtts' ou 'piper'")

    return engine


def get_reference_voice() -> Path | None:
    configured = os.getenv("VOICE_REF_WAV") or os.getenv("SPEAKER_WAV")
    if configured:
        ref_path = Path(configured)
        if not ref_path.is_absolute():
            ref_path = PROJECT_ROOT / ref_path
        return ref_path if ref_path.exists() else None

    if not AUDIO_REF_DIR.exists():
        return None

    candidates = [
        path
        for path in sorted(AUDIO_REF_DIR.iterdir())
        if path.is_file() and path.suffix.lower() in SUPPORTED_REF_EXTENSIONS
    ]
    return candidates[0] if candidates else None


def parse_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    if value is None:
        return default

    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"valor inteiro invalido: {value}") from exc

    if parsed < minimum or parsed > maximum:
        raise ValueError(f"valor fora do intervalo {minimum}-{maximum}: {parsed}")

    return parsed


def get_question(payload: dict[str, Any]) -> str:
    question = payload.get("pergunta") or payload.get("question") or payload.get("text")
    if not isinstance(question, str):
        raise ValueError("envie 'pergunta', 'question' ou 'text' como texto")

    question = question.strip()
    if not question:
        raise ValueError("pergunta vazia")

    if len(question) > 2000:
        raise ValueError("pergunta muito longa; limite atual: 2000 caracteres")

    return question


def build_medical_prompt(question: str) -> str:
    return (
        "Voce e um assistente medico local para um prototipo IoT. "
        "Responda em portugues do Brasil, de forma objetiva, segura e simples. "
        "Nao invente diagnosticos, nao prescreva medicamentos controlados e oriente "
        "procurar atendimento medico em sinais de gravidade.\n\n"
        f"Pergunta: {question}\n"
        "Resposta:"
    )


def ask_local_ai(question: str) -> str:
    logger.info("Enviando pergunta para Ollama/Mistral via CLI")
    return query_ollama_cli(build_medical_prompt(question))


def validate_piper() -> tuple[Path, Path]:
    piper_exe = get_piper_exe()
    piper_model = get_piper_model()

    if not piper_exe.exists():
        raise FileNotFoundError(f"Piper nao encontrado: {piper_exe}")

    if not piper_model.exists():
        raise FileNotFoundError(f"Modelo Piper nao encontrado: {piper_model}")

    return piper_exe, piper_model


def synthesize_audio(answer: str, engine: str | None = None) -> Path:
    engine = get_tts_engine({"tts_engine": engine}) if engine else get_tts_engine()
    reference_voice = get_reference_voice()

    if engine in {"auto", "xtts"} and reference_voice:
        try:
            return synthesize_audio_xtts(answer, reference_voice)
        except Exception:
            if engine == "xtts":
                raise
            logger.exception("XTTS falhou; usando Piper como fallback")

    return synthesize_audio_piper(answer)


def load_xtts_model():
    global _xtts_model

    if _xtts_model is None:
        from TTS.api import TTS

        logger.info("Carregando XTTS: %s", get_xtts_model_name())
        _xtts_model = TTS(model_name=get_xtts_model_name(), progress_bar=True, gpu=False)

    return _xtts_model


def synthesize_audio_xtts(answer: str, reference_voice: Path) -> Path:
    if not reference_voice.exists():
        raise FileNotFoundError(f"Voz de referencia nao encontrada: {reference_voice}")

    AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = AUDIO_OUTPUT_DIR / f"resposta_xtts_{uuid.uuid4().hex}.wav"

    logger.info("Gerando audio com XTTS usando voz de referencia: %s", reference_voice)
    tts = load_xtts_model()
    tts.tts_to_file(
        text=answer,
        speaker_wav=str(reference_voice),
        language="pt",
        file_path=str(output_path),
    )

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("XTTS nao gerou arquivo de audio valido")

    return output_path


def synthesize_audio_piper(answer: str) -> Path:
    piper_exe, piper_model = validate_piper()
    AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_path = AUDIO_OUTPUT_DIR / f"resposta_piper_{uuid.uuid4().hex}.wav"
    command = [
        str(piper_exe),
        "--model",
        str(piper_model),
        "--output_file",
        str(output_path),
    ]

    logger.info("Gerando audio com Piper")
    result = subprocess.run(
        command,
        input=answer,
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=120,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Piper falhou: {result.stderr.strip()}")

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("Piper nao gerou arquivo de audio valido")

    return output_path


def detect_wav_bitrate(audio_path: Path) -> int:
    try:
        with wave.open(str(audio_path), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            frame_rate = wav_file.getframerate()
            return channels * sample_width * 8 * frame_rate
    except wave.Error:
        return 256_000


def audio_packets(audio_path: Path, packet_bytes: int, bitrate_bps: int):
    started_at = time.monotonic()
    sent_bytes = 0

    try:
        with audio_path.open("rb") as file:
            while True:
                packet = file.read(packet_bytes)
                if not packet:
                    break

                yield packet
                sent_bytes += len(packet)
                expected_elapsed = sent_bytes * 8 / bitrate_bps
                sleep_seconds = expected_elapsed - (time.monotonic() - started_at)
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)
    finally:
        try:
            audio_path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Nao foi possivel remover audio temporario %s: %s", audio_path, exc)


@app.get("/health")
def health():
    reference_voice = get_reference_voice()
    return jsonify(
        {
            "status": "ok",
            "ollama_model": get_ollama_model(),
            "ollama_mode": "cli_subprocess",
            "ollama_exe": get_ollama_exe(),
            "tts_engine": get_tts_engine(),
            "xtts_model": get_xtts_model_name(),
            "voice_reference": str(reference_voice) if reference_voice else None,
            "piper_exe": str(get_piper_exe()),
            "piper_model": str(get_piper_model()),
        }
    )


@app.post("/api/pergunta/audio")
@app.post("/api/ask/audio")
def ask_audio():
    # Integracao ESP32 -> Python:
    # O ESP32 envia JSON com a pergunta e recebe um WAV em pacotes binarios,
    # com ritmo de envio controlado por bitrate_bps para facilitar o playback.
    raw_payload = request.get_json(silent=True) or {}

    try:
        if not isinstance(raw_payload, dict):
            raise ValueError("JSON deve ser um objeto")

        payload = raw_payload
        question = get_question(payload)
        tts_engine = get_tts_engine(payload)
        packet_bytes = parse_int(
            payload.get("packet_bytes"),
            DEFAULT_PACKET_BYTES,
            MIN_PACKET_BYTES,
            MAX_PACKET_BYTES,
        )
        bitrate_override = None
        if payload.get("bitrate_bps") is not None:
            bitrate_override = parse_int(
                payload.get("bitrate_bps"),
                0,
                MIN_BITRATE_BPS,
                MAX_BITRATE_BPS,
            )

        answer = ask_local_ai(question)
        audio_path = synthesize_audio(answer, tts_engine)
        detected_bitrate = detect_wav_bitrate(audio_path)
        bitrate_bps = bitrate_override or detected_bitrate
        used_tts_engine = "xtts" if "_xtts_" in audio_path.name else "piper"
        reference_voice = get_reference_voice()

        logger.info(
            "Transmitindo audio: arquivo=%s packet_bytes=%s bitrate_bps=%s",
            audio_path.name,
            packet_bytes,
            bitrate_bps,
        )

        return Response(
            audio_packets(audio_path, packet_bytes, bitrate_bps),
            mimetype="audio/wav",
            headers={
                "X-Audio-Packet-Bytes": str(packet_bytes),
                "X-Audio-Bitrate-Bps": str(bitrate_bps),
                "X-LLM-Model": get_ollama_model(),
                "X-TTS-Engine": used_tts_engine,
                "X-Voice-Reference": str(reference_voice) if reference_voice else "",
            },
            direct_passthrough=True,
        )
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400
    except OllamaCliError as exc:
        logger.exception("Falha ao chamar Ollama via CLI")
        return jsonify({"erro": "falha ao chamar IA local", "detalhe": str(exc)}), 502
    except Exception as exc:
        logger.exception("Falha ao processar pergunta")
        return jsonify({"erro": "falha ao gerar resposta em audio", "detalhe": str(exc)}), 500


if __name__ == "__main__":
    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "5000"))
    app.run(host=host, port=port, threaded=True)
