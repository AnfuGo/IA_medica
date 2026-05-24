from pathlib import Path
import sys
import subprocess

BASE = Path(__file__).resolve().parent.parent

ref = BASE / "audio" / "ref" / "ref.wav"
out = BASE / "audio" / "output" / "teste_coquitt.wav"

cmd = [
    sys.executable,
    "-m",
    "TTS.bin.synthesize",
    "--model_name",
    "tts_models/multilingual/multi-dataset/xtts_v2",
    "--text",
    "Olá este é um teste de voz de beta",
    "--speaker_wav",
    str(ref),
    "--language_idx",
    "pt",
    "--out_path",
    str(out)
]
subprocess.run(cmd, check=True)
