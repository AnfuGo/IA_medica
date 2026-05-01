from TTS.api import TTS

tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2")

tts.tts_to_file(
    text="Olá, este é um teste de voz feminina.",
    speaker="female",
    language="pt",
    file_path="teste.wav"
)
