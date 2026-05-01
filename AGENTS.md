# AGENTS.md

## Objetivo do Agente

Este repositório contém um projeto IoT de assistente médico embarcado com ESP32 e IA local.
Agentes de IA que atuarem aqui devem preservar modularidade, segurança e simplicidade operacional.

---

## Regras Gerais

1. Nunca quebrar código existente sem necessidade.
2. Priorizar soluções simples e funcionais.
3. Manter compatibilidade com Windows.
4. Sempre comentar integrações ESP32 ↔ Python.
5. Separar lógica por módulos.
6. Usar permissão elevada quando o sandbox bloquear acesso ao Python base, ao Piper ou a outros executáveis fora de `C:\IA_medica`.

---

## Stack Principal

- Python 3.11 via `C:\IA_medica\venv311\Scripts\python.exe`
- Python base 3.11 em `C:\Users\clauf\AppData\Local\Programs\Python\Python311\python.exe`
- Flask ou FastAPI
- ESP32 / ESP32-S3
- Mistral local
- Coqui XTTS
- Whisper opcional

---

## Ambiente Python

O ambiente Python oficial do projeto é o virtualenv local `venv311`.

Sempre executar scripts Python usando:

```powershell
C:\IA_medica\venv311\Scripts\python.exe caminho\do\script.py
```

Não assumir o `python` global do Windows como interpretador do projeto.
Não usar `C:\Python313\python.exe` para este projeto.

O `venv311` depende da instalação base:

```powershell
C:\Users\clauf\AppData\Local\Programs\Python\Python311\python.exe
```

Se o ambiente retornar erro como `No Python at ...` ou `Acesso negado`, repetir o comando com permissão elevada. Isso pode ser necessário porque o `venv311` fica em `C:\IA_medica`, mas a instalação base do Python fica fora do workspace.

Validação rápida:

```powershell
C:\IA_medica\venv311\Scripts\python.exe -c "import sys; print(sys.executable); print(sys.version)"
C:\IA_medica\venv311\Scripts\python.exe -m pip check
```

---

## Recriação do venv311

Recriar o ambiente virtual somente se o `venv311` estiver realmente quebrado.

Antes de remover o ambiente antigo, confirmar que o caminho resolvido é exatamente:

```text
C:\IA_medica\venv311
```

Comandos recomendados:

```powershell
C:\Users\clauf\AppData\Local\Programs\Python\Python311\python.exe -m venv C:\IA_medica\venv311
C:\IA_medica\venv311\Scripts\python.exe -m pip install --upgrade pip
C:\IA_medica\venv311\Scripts\python.exe -m pip install -r C:\IA_medica\requirements.txt
```

Se faltarem bibliotecas já presentes no ambiente completo de IA, usar também o arquivo `requirements`, que contém o congelamento maior do ambiente:

```powershell
C:\IA_medica\venv311\Scripts\python.exe -m pip install -r C:\IA_medica\requirements
```

---

## Permissão Elevada

Usar permissão elevada quando:

- O comando precisa executar `C:\Users\clauf\AppData\Local\Programs\Python\Python311\python.exe`.
- O `venv311` falha porque não consegue acessar a instalação base do Python 3.11.
- O teste precisa chamar executáveis externos, como `C:\piper\piper.exe`.
- A instalação de dependências precisa baixar pacotes da internet.

Não usar permissão elevada para operações destrutivas sem confirmar o caminho absoluto do alvo.

---

## Testes e Validações

Validações leves recomendadas:

```powershell
C:\IA_medica\venv311\Scripts\python.exe -m py_compile backend\api.py backend\test_mistral.py backend\test_tts.py backend\test_piper.py backend\test_coquitts.py backend\test_whisper.py
C:\IA_medica\venv311\Scripts\python.exe -m pip check
C:\IA_medica\venv311\Scripts\python.exe -c "from backend.api import app; c=app.test_client(); r=c.get('/health'); print(r.status_code); print(r.get_json())"
```

Scripts de integração podem depender de serviços ou arquivos externos:

- `backend\test_mistral.py` precisa do Ollama/Mistral local ativo.
- `backend\test_piper.py` e `backend\test_tts.py` precisam do Piper acessível.
- `backend\test_whisper.py` precisa de `audio\input\teste.wav`.
- `backend\test_coquitts.py` pode carregar modelo XTTS e exigir cache/modelos locais.

---

## Organização Esperada

### Backend

- `routes/` → endpoints API
- `services/` → regras de negócio
- `ia/` → integração com modelos
- `audio/` → TTS / reprodução

### Firmware

- `esp32/firmware.ino`

---

## Diretrizes de Código

### Python

- Preferir funções pequenas.
- Usar tipagem quando possível.
- Manter logs claros.
- Evitar arquivos gigantes.

### ESP32

- Código leve.
- Não bloquear loop principal.
- Reconexão automática Wi-Fi.
- Timeout em requests.

---

## IA Local

Prioridade atual:

1. Mistral
2. Ollama wrappers
3. Tiny models offline

---

## TTS

Prioridade atual:

1. XTTS
2. Coqui standard
3. Piper fallback

---

## Segurança

Nunca implementar:

- Execução remota de shell sem autenticação.
- Exposição pública sem proteção.
- Armazenamento inseguro de credenciais.

---

## Ao Criar Novos Arquivos

Sempre manter nomes claros:

- `audio_service.py`
- `llm_service.py`
- `esp32_client.ino`

---

## Ao Refatorar

Pode refatorar desde que:

- preserve comportamento atual
- reduza complexidade
- aumente legibilidade

---

## Missão Atual do Projeto

Construir protótipo funcional onde:

```text
ESP32 envia pergunta → Python processa IA → retorna áudio.
```

---

## Resumo Operacional

Use sempre o Python do projeto em `C:\IA_medica\venv311\Scripts\python.exe`, que depende do Python 3.11 base em `C:\Users\clauf\AppData\Local\Programs\Python\Python311\python.exe`. Se o sandbox bloquear esse acesso, execute com permissão elevada. Só recrie o `venv311` quando ele estiver realmente quebrado, reinstalando primeiro `requirements.txt` e depois `requirements` se forem necessárias as bibliotecas completas de IA/TTS. Preserve a arquitetura simples: ESP32 envia a pergunta, o backend Python consulta a IA local, gera TTS e retorna o áudio.
