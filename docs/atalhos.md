# Configurando o atalho global (push-to-talk)

O comando a ser executado pelo atalho e sempre:

```
python -m anta run
```

O instalador detecta seu sistema e mostra a instrucao certa. Abaixo, o manual
completo por ambiente.

## Linux — KDE Plasma (Wayland)
No Wayland, apps nao podem sequestrar teclas globais; o atalho e criado pelo
proprio KDE:

1. Configuracoes do Sistema → **Atalhos**
2. **Adicionar** → **Atalho de Comando/URL**
3. No comando, cole: `python -m anta run`
4. Clique na coluna de atalho e pressione a combinacao (ex.: `Ctrl+Alt+Espaco`)
5. Aplicar

> O local onde o Plasma guarda atalhos de comando mudou do Plasma 5 para o 6,
> por isso a automacao pode falhar entre versoes — este caminho manual e o mais
> robusto.

## Linux — X11 (GNOME, XFCE, etc.)
O instalador pode registrar automaticamente (pynput). Manual:
- GNOME: Configuracoes → Teclado → Atalhos personalizados → comando acima.

## Windows
O instalador registra automaticamente (bandeja + RegisterHotKey). Manual:
- Crie um atalho `.lnk` para o comando, ou use um app de hotkey (ex.: AutoHotkey)
  apontando para `python -m anta run`.

## Modo de uso
Toggle: **1a** pressao comeca a gravar do microfone; **2a** pressao encerra e
dispara o pipeline (transcreve → decide → executa). Corte de seguranca em 60s.
