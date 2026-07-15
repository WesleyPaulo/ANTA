# Configurando o atalho global (push-to-talk)

O assistente roda como um **daemon quente** (`python -m anta run`) que fica
carregado e alterna a gravacao a cada acionamento do atalho — assim o modelo
permanece quente entre comandos. Como o daemon captura o atalho depende do SO:

- **X11 / Windows:** o proprio daemon captura o atalho in-process (pynput). Basta
  ter o `anta run` rodando (o instalador o poe no autostart do login).
- **Wayland (KDE):** apps nao capturam teclas globais, entao o atalho e criado no
  SO e chama `python -m anta toggle`, que sinaliza o daemon ja em execucao.

O instalador detecta seu sistema e mostra a instrucao certa. Abaixo, o manual
completo por ambiente.

## Linux — KDE Plasma (Wayland)
O daemon `anta run` deve estar rodando (o instalador o adiciona ao autostart). O
atalho e criado pelo proprio KDE e chama o `toggle`:

1. Configuracoes do Sistema → **Atalhos**
2. **Adicionar** → **Atalho de Comando/URL**
3. No comando, cole: `python -m anta toggle`
4. Clique na coluna de atalho e pressione a combinacao (ex.: `Ctrl+Alt+Espaco`)
5. Aplicar

> O local onde o Plasma guarda atalhos de comando mudou do Plasma 5 para o 6,
> por isso a automacao pode falhar entre versoes — este caminho manual e o mais
> robusto.

## Linux — X11 (GNOME, XFCE, etc.)
O daemon `anta run` captura o atalho sozinho (pynput), sem precisar de atalho do
SO. O instalador o adiciona ao autostart. Manual: garanta que `python -m anta run`
suba no login (ex.: Aplicativos de Inicializacao do GNOME).

## Windows
O daemon `python -m anta run` captura o atalho in-process (pynput); o instalador o
registra no login (`HKCU\...\Run`). Manual: crie um atalho `.lnk` para `anta run`
na pasta Inicializar, ou use um app de hotkey (ex.: AutoHotkey) apontando para
`python -m anta toggle`.

## Modo de uso
Toggle: **1a** pressao comeca a gravar do microfone; **2a** pressao encerra e
dispara o pipeline (transcreve → decide → executa). Corte de seguranca em 60s.
