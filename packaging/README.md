# Empacotamento (M5)

Gera um **executável nativo por SO** com PyInstaller e, opcionalmente, um instalador.
Rode **uma vez em cada SO** (o binário é específico da plataforma; mesmo código-fonte).

## Como funciona

- **Entry:** [`entry.py`](entry.py) → [`anta.gui.launcher`](../anta/gui/launcher.py). O exe é
  **um só**: com argumento age como CLI (`anta config`, `anta app`, `anta run`, `anta toggle`);
  sem argumento roteia por `configured` (1ª vez → Configurador; já configurado → HUD).
- **Spec:** [`anta.spec`](anta.spec) empacota os dois `dist/` do Vite em `web/configurador` e
  `web/runtime`, mais `modes.yaml`/`config.example.toml`. No frozen, `anta.gui.assets` e
  `config.default_modes_path` resolvem tudo via `sys._MEIPASS`; `hotkey.default_command`
  usa o exe (sem `-m anta`).
- **Downloads NÃO vão no pacote:** os modelos (GBs) são baixados pelo Configurador no setup.

## Pré-requisitos (na máquina de build)

- Node/npm (para buildar os fronts).
- Python com as deps: `pip install -r requirements.txt` — o PyInstaller rastreia os
  módulos **reais**, então faster-whisper/piper/etc. precisam existir no venv.
- PyInstaller (os scripts instalam se faltar).

## Build automático (CI → Release)

`.github/workflows/release.yml` builda os dois SOs nos runners do GitHub e publica na
**Release** ao empurrar uma tag `vX.Y.Z` (`git tag v0.4.0 && git push origin v0.4.0`).
"Run workflow" (manual) só builda, sem publicar. O 1º build costuma pedir ajuste de
`hiddenimports`/backend (ver comentários no workflow).

## Build (local)

### Linux / macOS
```bash
./packaging/build.sh              # front + exe -> dist/anta/anta
./packaging/build.sh --appimage   # + AppImage -> dist/ANTA-x86_64.AppImage (precisa do appimagetool)
```

### Windows
```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1          # -> dist\anta\anta.exe
powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -Inno    # + dist\ANTA-Setup.exe (precisa do Inno Setup/ISCC)
```

## Autostart

O App de execução (`anta app`) fica residente. O instalador oferece ligar o autostart:
- **Windows:** Inno grava `HKCU\...\Run` (task "autostart", ver [`windows/anta.iss`](windows/anta.iss)).
- **Linux:** copie [`linux/anta.desktop`](linux/anta.desktop) para `~/.config/autostart/` (Exec = caminho do AppImage).
  No Wayland/KDE o atalho global chama `anta toggle` (ver `anta/platform/hotkey.py` e `docs/atalhos.md`).

## Notas

- **Ícone:** placeholder por enquanto (o `.spec`/`.iss` aceitam um `.ico`/`.png` quando houver arte).
- **Primeiro build costuma precisar de ajuste fino** de `hiddenimports`/hooks por SO (típico do
  PyInstaller com deps nativas: onnxruntime, PortAudio). O `anta.spec` já cobre os lazy-imports
  conhecidos (faster_whisper, fastembed, piper, sounddevice, pynput, pystray, webview, ...).
