# ANTA no Windows — checklist de validação (v0.2)

O código é cross-platform desde a v0.1 (detecção de SO, VRAM via NVIDIA, atalho
in-process, config em `%APPDATA%`), mas o alvo testado era Linux. A v0.2 corrige
o quoting do interpretador no autostart e usa este checklist para validar o
runtime ponta-a-ponta em **Windows + GPU NVIDIA**.

## Pré-requisitos
- Windows 10/11, GPU NVIDIA com driver atualizado (o gating de VRAM usa `nvidia-smi`).
- `winget` disponível (para pandoc e Ollama).

## Passos

1. **Instalar**
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1
   ```
   Espera-se: `uv` instala, `winget` traz pandoc e Ollama, cria `.venv` (Python
   3.12), instala `requirements.txt` (inclui `piper-tts`) e abre a TUI.

2. **Configurar (TUI)** — escolher um modo verde/amarelo, o microfone e, se
   quiser voz, marcar **"Falar respostas (TTS)"**. Confirmar em "Instalar".
   Espera-se: `ollama pull <llm>`, download do Whisper, (se TTS) download da voz
   PT-BR, `config.toml` salvo em `%APPDATA%\anta\config.toml`, atalho registrado
   no login (`HKCU\...\Run`).

3. **Autostart com caminho com espaços** — confirmar que o valor gravado no
   Run-key vem com o interpretador **entre aspas** (`"C:\...\python.exe" -m anta run`).
   Sem aspas, um caminho com espaço (ex.: `C:\Users\Nome Sobrenome\...`) quebra.
   (Corrigido em `hotkey.default_command`.)

4. **Rodar o daemon**
   ```powershell
   .\.venv\Scripts\python.exe -m anta run
   ```
   Espera-se: carrega os modelos, fixa o LLM na VRAM (keep-alive no boot) e passa
   a ouvir `ctrl+alt+space` in-process (pynput). `anta toggle` **não** se aplica
   no Windows (o próprio `run` captura a tecla).

5. **Ações** — testar por voz: criar nota, criar documento (pandoc no PATH da
   sessão após o reload de PATH), abrir app da whitelist, e uma pergunta
   (resposta por voz se TTS ligado).

6. **TTS** — confirmar que a resposta é reproduzida (wheel `piper-tts` traz o
   onnxruntime; o `sounddevice` usa o PortAudio do próprio wheel).

## Limitações conhecidas
- **Notificações**: no Windows o feedback vai só para o `print` no terminal
  (sem `notify-send`). Um toast nativo fica para depois (fora do escopo v0.2).
- **macOS** permanece não suportado (gating de VRAM assume NVIDIA).

Registrar aqui qualquer bug encontrado durante a validação.
