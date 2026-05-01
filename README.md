# Projeto IoT - Assistente Médico com ESP32 + IA Local

## Visão Geral

Este projeto cria um protótipo de assistente médico embarcado com ESP32, backend Python, IA local, síntese de voz e integração futura com sensores físicos.

A proposta é permitir que um dispositivo físico receba perguntas por voz ou texto, processe localmente com IA e responda em áudio.

---

## Arquitetura Geral

```text
ESP32
↓
Wi-Fi / Serial / HTTP
↓
Backend Python (PC ou MiniPC)
↓
Modelo LLM local (Mistral inicialmente)
↓
Resposta textual
↓
TTS (Coqui XTTS ou Piper)
↓
Áudio enviado ao alto-falante / ESP32
```

---

## Tecnologias Utilizadas

### Hardware

- ESP32 / ESP32-S3
- Microfone I2S ou USB
- Alto-falante amplificado
- Sensores diversos (temperatura, biométricos futuros)

### Software

- Python 3.11
- Flask / FastAPI
- Mistral local via Ollama
- Coqui TTS / XTTS
- Piper fallback
- Whisper opcional
- VS Code
- Git

---

## Ambiente Python

O interpretador oficial do projeto é:

```powershell
C:\IA_medica\venv311\Scripts\python.exe
```

O `venv311` depende desta instalação base do Python 3.11:

```powershell
C:\Users\clauf\AppData\Local\Programs\Python\Python311\python.exe
```

Não usar o Python global do sistema nem `C:\Python313\python.exe` para executar scripts do projeto.

Quando o sandbox bloquear acesso ao Python base ou a executáveis externos, rode o comando com permissão elevada. Isso é esperado porque a base do Python 3.11 fica fora de `C:\IA_medica`.

Validação rápida:

```powershell
C:\IA_medica\venv311\Scripts\python.exe -c "import sys; print(sys.executable); print(sys.version)"
C:\IA_medica\venv311\Scripts\python.exe -m pip check
```

---

## Instalação / Reparo do Ambiente

Se o `venv311` precisar ser recriado, use o Python 3.11 base:

```powershell
C:\Users\clauf\AppData\Local\Programs\Python\Python311\python.exe -m venv C:\IA_medica\venv311
C:\IA_medica\venv311\Scripts\python.exe -m pip install --upgrade pip
C:\IA_medica\venv311\Scripts\python.exe -m pip install -r C:\IA_medica\requirements.txt
```

Se forem necessárias todas as bibliotecas já congeladas no ambiente completo de IA/TTS:

```powershell
C:\IA_medica\venv311\Scripts\python.exe -m pip install -r C:\IA_medica\requirements
```

---

## Validações

Compilar os scripts principais:

```powershell
C:\IA_medica\venv311\Scripts\python.exe -m py_compile backend\api.py backend\test_mistral.py backend\test_tts.py backend\test_piper.py backend\test_coquitts.py backend\test_whisper.py
```

Testar importações e health check da API:

```powershell
C:\IA_medica\venv311\Scripts\python.exe -c "from backend.api import app; c=app.test_client(); r=c.get('/health'); print(r.status_code); print(r.get_json())"
```

Scripts de integração:

- `backend\test_mistral.py` exige Ollama/Mistral local ativo.
- `backend\test_piper.py` e `backend\test_tts.py` exigem Piper acessível.
- `backend\test_whisper.py` exige `audio\input\teste.wav`.
- `backend\test_coquitts.py` pode exigir cache/modelo XTTS local.

---

## Estrutura Recomendada

```text
projeto-iot/
├── backend/
│   ├── app.py
│   ├── routes/
│   ├── services/
│   ├── ia/
│   └── audio/
├── esp32/
│   └── firmware.ino
├── docs/
├── tests/
├── README.md
└── AGENTS.md
```
