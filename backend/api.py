from email.mime import audio
import logging
import os
import shutil
import subprocess
import time
import uuid
import wave
import re
from pathlib import Path
from typing import Any
import whisper
import threading
from collections import deque
from flask import Flask, Response, jsonify, request, send_file
from flask_cors import CORS
from pydub import AudioSegment
from datetime import datetime

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
SUPPORTED_REF_EXTENSIONS = {".wav", ".mp3", ".flac"}

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(message)s")
logger = logging.getLogger(__name__)

_xtts_model = None
_whisper_model = None

# Variáveis globais de controle do fluxo
audio_queue = deque()
transcription_text = ""
conversation_text = ""
recording_active = False
processing = False
last_response = None

# Locks para concorrência (Thread-safe)
conversation_lock = threading.Lock()
audio_lock = threading.Lock()
text_lock = threading.Lock()

def get_piper_exe() -> Path:
    configured = os.getenv("PIPER_EXE")
    if configured: return Path(configured)
    found = shutil.which("piper")
    if found: return Path(found)
    return Path(r"C:\piper\piper.exe")

def load_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        logger.info("Carregando Whisper...")
        _whisper_model = whisper.load_model("base")
    return _whisper_model

def push_audio_chunk(audio_bytes: bytes):
    with audio_lock:
        audio_queue.append(audio_bytes)

def consume_transcription():
    global transcription_text
    with text_lock:
        text = transcription_text.strip()
        transcription_text = ""
    return text

def append_conversation(question: str, answer: str):
    global conversation_text
    with conversation_lock:
        conversation_text += f"\nPACIENTE: {question}\nASSISTENTE: {answer}\n"

def get_conversation_text() -> str:
    with conversation_lock:
        return conversation_text.strip()

def clear_conversation():
    global conversation_text
    with conversation_lock:
        conversation_text = ""

def pcm_chunks_to_wav() -> Path | None:
    with audio_lock:
        if not audio_queue:
            return None
        audio_data = b"".join(audio_queue)
        audio_queue.clear()

    AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    wav_path = AUDIO_OUTPUT_DIR / f"gravacao_{uuid.uuid4().hex}.wav"

    with wave.open(str(wav_path), "wb") as wav_file:
        wav_file.setnchannels(1)      # mono
        wav_file.setsampwidth(2)      # 16 bits
        wav_file.setframerate(16000)  # 16 kHz
        wav_file.writeframes(audio_data)

    logger.info("WAV criado do ESP32: %s (%d bytes)", wav_path, len(audio_data))
    return wav_path

def process_audio_queue():
    global transcription_text
    global recording_active

    model = load_whisper_model()
    while True:
        if recording_active or not audio_queue:
            time.sleep(0.2)
            continue

        try:
            temp_file = pcm_chunks_to_wav()
            if temp_file is None:
                continue

            logger.info("Processando áudio completo combinado com Whisper...")
            result = model.transcribe(str(temp_file), language="pt")
            text = result["text"].strip()
            
            if text:
                with text_lock:
                    transcription_text += " " + text
                logger.info("Whisper (Resultado Transcrição): %s", text)
        except Exception:
            logger.exception("Erro no Whisper")

def get_piper_model() -> Path:
    configured = os.getenv("PIPER_MODEL")
    if not configured: return DEFAULT_PIPER_MODEL
    model_path = Path(configured)
    return model_path if model_path.is_absolute() else PROJECT_ROOT / model_path

def get_xtts_model_name() -> str:
    return os.getenv("XTTS_MODEL", DEFAULT_XTTS_MODEL)

def get_tts_engine() -> str:
    engine = str(os.getenv("TTS_ENGINE", "auto")).strip().lower()
    if engine not in {"auto", "xtts", "piper"}:
        raise ValueError("tts_engine deve ser 'auto', 'xtts' ou 'piper'")
    return engine

def get_reference_voice() -> Path | None:
    configured = os.getenv("VOICE_REF_WAV") or os.getenv("SPEAKER_WAV")
    if configured:
        ref_path = Path(configured)
        return ref_path if ref_path.is_absolute() else PROJECT_ROOT / ref_path
    if not AUDIO_REF_DIR.exists(): return None
    candidates = [p for p in sorted(AUDIO_REF_DIR.iterdir()) if p.is_file() and p.suffix.lower() in SUPPORTED_REF_EXTENSIONS]
    return candidates[0] if candidates else None

def build_medical_prompt(question: str, historico: str) -> str:
    # IMPORTANTE: Agora passamos o histórico da conversa para manter o contexto!
    return (
        "Voce e um assistente medico local para um prototipo IoT. "
        "Responda em portugues do Brasil, de forma objetiva, segura e simples. "
        "Responda com no maximo 50 palavras. "
        "Nao invente diagnosticos e nao prescreva medicamentos.\n\n"
        "REGRA SOBRE A PALAVRA FIM:\n"
        "Escreva a palavra FIM em uma linha separada quando entender que a consulta terminou.\n\n"
        f"HISTORICO DA CONVERSA:\n{historico}\n\n"
        f"Nova Pergunta do Paciente: {question}\n"
        "Resposta:"
    )

def build_pdf_prompt(conversation: str) -> str:
    return (
        "Voce e um sistema de geracao de prontuario medico.\n\n"
        "Analise toda a conversa abaixo e gere SOMENTE o relatorio "
        "estruturado exatamente no formato solicitado.\n\n"
        "Nao invente informacoes.\n"
        "Quando nao houver informacao disponivel, escreva "
        "'Nao informado'.\n\n"

        "FORMATO OBRIGATORIO:\n\n"

        "Nome do paciente:\n"
        "Data da consulta:\n"
        "CPF:\n"
        "RG:\n"
        "Idade:\n"
        "Sexo:\n"
        "Temperatura corporal:\n"
        "Pressao arterial:\n"
        "Frequencia cardiaca:\n"
        "Saturacao de oxigenio:\n"
        "Peso:\n"
        "Altura:\n\n"

        "Sintomas principais:\n"
        "- item 1\n"
        "- item 2\n\n"

        "Tempo de evolucao dos sintomas:\n\n"

        "Medicamentos em uso:\n\n"

        "Alergias:\n\n"

        "Doencas pre-existentes:\n\n"

        "Gravidade:\n"
        "(Baixa, Media ou Alta)\n\n"

        "Possiveis doencas:\n"
        "- hipotese 1\n"
        "- hipotese 2\n\n"

        "Recomendacao:\n\n"

        "Resumo clinico:\n\n"

        f"CONVERSA:\n{conversation}"
    )

def ask_local_ai(text: str, fim: bool = False, historico: str = "") -> str:
    logger.info("Enviando dados para o Ollama...")
    prompt = build_pdf_prompt(text) if fim else build_medical_prompt(text, historico)
    return query_ollama_cli(prompt)

def preencher_data_consulta(relatorio: str) -> str:
    data_atual = datetime.now().strftime("%d/%m/%Y %H:%M")
    linha_nova = f"Data da consulta: {data_atual}"

    padrao = re.compile(r"^Data da consulta:.*$", flags=re.IGNORECASE | re.MULTILINE)

    if padrao.search(relatorio):
        return padrao.sub(linha_nova, relatorio, count=1)

    return f"{linha_nova}\n{relatorio}"

def sanitize_answer_for_tts(text: str) -> str:
    if not text: return ""
    text = re.sub(r"FIM", "", text, flags=re.IGNORECASE) # Remove a palavra FIM para não ser falada
    text = re.sub(r"[.,;:!?()\[\]{}\"']", " ", text)
    text = re.sub(r"\s+", " ", text)
    words = text.split()
    if not words: return ""
    filtered = [words[0]]
    for word in words[1:]:
        if word.lower() != filtered[-1].lower():
            filtered.append(word)
    return " ".join(filtered).strip()

def synthesize_audio(answer: str) -> Path:
    engine = get_tts_engine()
    reference_voice = get_reference_voice()
    if engine in {"auto", "xtts"} and reference_voice:
        try:
            return synthesize_audio_xtts(answer, reference_voice)
        except Exception:
            logger.exception("XTTS falhou; usando Piper como fallback")
    return synthesize_audio_piper(answer)

def load_xtts_model():
    global _xtts_model
    if _xtts_model is None:
        from TTS.api import TTS
        _xtts_model = TTS(model_name=get_xtts_model_name(), progress_bar=True, gpu=False)
    return _xtts_model

def synthesize_audio_xtts(answer: str, reference_voice: Path) -> Path:
    AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = AUDIO_OUTPUT_DIR / f"resposta_xtts_{uuid.uuid4().hex}.wav"
    tts = load_xtts_model()
    tts.tts_to_file(text=answer, speaker_wav=str(reference_voice), language="pt", file_path=str(output_path))
    return output_path

def synthesize_audio_piper(answer: str) -> Path:
    piper_exe = get_piper_exe()
    piper_model = get_piper_model()
    AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = AUDIO_OUTPUT_DIR / f"resposta_piper_{uuid.uuid4().hex}.wav"
    
    subprocess.run(
        [str(piper_exe), "--model", str(piper_model), "--output_file", str(output_path)],
        input=answer, text=True, encoding="utf-8", capture_output=True, timeout=120
    )
    return output_path


def consulta_finalizada(answer: str) -> bool:
    if not answer:
        return False
# Olha apenas o final da resposta, onde o FIM deveria aparecer
    trecho_final = answer.strip()[-60:]
    return bool(re.search(r"\bFIM\b", trecho_final, flags=re.IGNORECASE))


PALAVRAS_DESPEDIDA = {
    "tchau", "obrigado", "obrigada", "valeu", "ate mais", "ate logo",
    "so isso", "era so isso", "nada mais", "pode ser so isso"
}

def paciente_se_despediu(pergunta: str) -> bool:
    texto = pergunta.strip().lower()
    return any(palavra in texto for palavra in PALAVRAS_DESPEDIDA)

@app.post("/api/audio/chunk")
def receive_audio_chunk():
    global recording_active
    try:
        is_reset = request.headers.get("X-Chunk-Reset", "").lower() == "true"
        is_final = request.headers.get("X-Chunk-Final", "").lower() == "true"

        if is_reset:
            with audio_lock:
                audio_queue.clear()

        recording_active = True 
        chunk = request.data
        if not chunk: return jsonify({"erro": "chunk vazio"}), 400

        push_audio_chunk(chunk)

        if is_final:
            recording_active = False 

        return jsonify({"status": "recebido", "bytes": len(chunk), "final": is_final})
    except Exception as exc:
        return jsonify({"erro": str(exc)}), 500

response_version = 0
last_response = None

@app.get("/api/transcricao/processar")
def process_transcription():
    global processing, last_response
 
    try:
        # Já existe um processamento em andamento (chamado por outro poll) -> aguarda
        if processing:
            return jsonify({"status": "processando"}), 202
 
        # Verifica se chegou uma pergunta nova do Whisper
        question = consume_transcription()
 
        if not question:
            # Não há pergunta nova. Se já existe uma resposta anterior pronta,
            # continua entregando ela (sem apagar) para qualquer cliente que pedir.
            if last_response is not None:
                return jsonify(last_response)
            return jsonify({"status": "aguardando"}), 202
 
        # Há uma pergunta nova -> processa e SUBSTITUI last_response
        processing = True
        logger.info("Pergunta processada: %s", question)
 
        historico_atual = get_conversation_text()
        answer = ask_local_ai(question, fim=False, historico=historico_atual)
 
        fim = consulta_finalizada(answer) and paciente_se_despediu(question)
 
        append_conversation(question, answer)
 
        tts_answer = sanitize_answer_for_tts(answer)
        audio_path = synthesize_audio(tts_answer)
 
        audio = AudioSegment.from_wav(str(audio_path))
        audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        audio.export(str(audio_path), format="wav")
 
        response = {
            "pergunta": question,
            "resposta": answer,
            "audio_url": f"/api/audio/{audio_path.name}",
            "tts_engine": "xtts" if "_xtts_" in audio_path.name else "piper",
            "fim": fim,
            "relatorio": None
        }
 
        if fim:
            logger.info("Identificado encerramento da conversa. Gerando prontuário...")
            conversa_completa = get_conversation_text()
            relatorio = ask_local_ai(conversa_completa, fim=True)
            relatorio = preencher_data_consulta(relatorio)
            response["relatorio"] = relatorio
            clear_conversation()
 
        # Sobrescreve a resposta anterior com a nova.
        # A partir daqui, QUALQUER cliente (ESP32, frontend, etc.) que fizer
        # polling vai receber esta mesma resposta repetidamente, até que
        # uma nova pergunta seja transcrita e processada.
        last_response = response
        processing = False
 
        return jsonify({"status": "processando"}), 202
 
    except Exception as exc:
        processing = False
        logger.exception("Falha ao processar transcricao")
        return jsonify({"erro": str(exc)}), 500

@app.get("/api/audio/<filename>")
def get_audio_file(filename):
    audio_path = AUDIO_OUTPUT_DIR / filename
    if not audio_path.exists(): return jsonify({"erro": "arquivo nao encontrado"}), 404
    return send_file(audio_path, mimetype="audio/wav")

# Inicialização da Thread do Whisper
worker = threading.Thread(target=process_audio_queue, daemon=True)
worker.start()

if __name__ == "__main__":
    app.run(host=os.getenv("API_HOST", "0.0.0.0"), port=int(os.getenv("API_PORT", "5000")), threaded=True)