#!/usr/bin/env bash
# Bootstrap de instalacao do ANTA (Linux e macOS).
#
# Instala os pre-requisitos que o pip NAO cobre (libs nativas, pandoc, Ollama),
# prepara o ambiente Python com `uv` e abre o instalador TUI (que baixa os
# modelos, salva a config e configura o atalho).
#
# Uso:   ./install.sh          (a partir da raiz do repo)
set -euo pipefail

log()  { printf '\033[1;36m[anta]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[anta]\033[0m %s\n' "$*" >&2; }
err()  { printf '\033[1;31m[anta]\033[0m %s\n' "$*" >&2; }

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

have() { command -v "$1" >/dev/null 2>&1; }

sudo_if_needed() {
  if [ "$(id -u)" -eq 0 ]; then "$@"; return; fi
  if ! have sudo; then
    err "precisa de privilegios de root: rode como root ou instale sudo. Comando: $*"
    exit 1
  fi
  sudo "$@"
}

install_sys_deps_linux() {
  # espeak-ng: fonemizacao do Piper (TTS). O wheel do piper-tts normalmente ja
  # traz os dados, mas ter o pacote do SO evita TTS mudo por falta da lib.
  if have apt-get; then
    log "instalando libs de sistema (apt)..."
    sudo_if_needed apt-get update -y
    # build-essential: gcc + headers p/ compilar evdev (dep do pynput no Linux)
    sudo_if_needed apt-get install -y \
      build-essential python3-dev libportaudio2 libsndfile1 pandoc libnotify-bin espeak-ng
  elif have dnf; then
    log "instalando libs de sistema (dnf)..."
    sudo_if_needed dnf install -y \
      gcc kernel-headers python3-devel portaudio libsndfile pandoc libnotify espeak-ng
  elif have pacman; then
    log "instalando libs de sistema (pacman)..."
    sudo_if_needed pacman -Sy --needed --noconfirm \
      base-devel portaudio libsndfile pandoc libnotify espeak-ng
  else
    warn "gerenciador de pacotes nao reconhecido."
    warn "instale manualmente: gcc + headers do Python/kernel, portaudio, libsndfile, pandoc, libnotify, espeak-ng."
  fi
}

install_sys_deps_macos() {
  if ! have brew; then
    err "Homebrew nao encontrado. Instale em https://brew.sh e rode de novo."
    exit 1
  fi
  log "instalando libs de sistema (brew)..."
  brew install portaudio libsndfile pandoc
  warn "macOS e EXPERIMENTAL: a selecao de modo por VRAM assume GPU NVIDIA; em"
  warn "Apple Silicon todos os modos aparecem como 'nao roda'. Depois de instalar"
  warn "os modelos manualmente (ollama pull ...) rode 'python -m anta run' direto."
}

install_ollama() {
  if have ollama; then
    log "Ollama ja instalado."
  else
    log "instalando Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
  fi
}

ensure_uv() {
  if have uv; then log "uv ja instalado ($(uv --version))."; return; fi
  log "instalando uv (gerencia Python + venv, sem depender de python3-venv)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  have uv || { err "uv nao ficou no PATH. Abra um novo shell e rode ./install.sh de novo."; exit 1; }
}

OS="$(uname -s)"
log "ANTA — bootstrap ($OS)"

case "$OS" in
  Linux)  install_sys_deps_linux ;;
  Darwin) install_sys_deps_macos ;;
  *) err "SO '$OS' nao suportado por este script. Veja o README."; exit 1 ;;
esac

install_ollama
ensure_uv

log "preparando o ambiente Python (.venv) com uv..."
uv venv --python 3.12 "$REPO_DIR/.venv"
VIRTUAL_ENV="$REPO_DIR/.venv" uv pip install -r "$REPO_DIR/requirements.txt"

log "tudo pronto. Abrindo o instalador (escolha o modo e o microfone)..."
exec "$REPO_DIR/.venv/bin/python" -m anta
