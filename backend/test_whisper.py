import whisper
from pathlib import Path

model = whisper.load_model("base")

audio_path = (
    Path(__file__).resolve().parent.parent
    / "audio"
    / "input"
    / "audio_5.wav"
)

result = model.transcribe(str(audio_path))

print(result["text"])
