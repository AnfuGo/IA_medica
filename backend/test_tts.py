import subprocess

texto = "Olá, este é um teste de voz"

cmd = [
    "piper",
    "--model",
    "models/pt_BR-faber-medium.onnx",
    "--output_file",
    "audio/output/voz.wav"
]

p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
p.communicate(input=texto.encode())
