import subprocess

texto = "Olá, este é um teste do sistema de voz"

cmd = [
    "piper",
    "--model",
    "models/pt_BR-faber-medium.onnx",
    "--output_file",
    "audio/output/teste.wav"
]

p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
p.communicate(input=texto.encode())
