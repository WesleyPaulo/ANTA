"""Script de entrada do PyInstaller (aponta pro launcher).

Fica fora do pacote de proposito: o PyInstaller quer um SCRIPT como entrypoint,
nao um modulo. Toda a logica esta em anta.gui.launcher (testavel).
"""
from anta.gui.launcher import main

if __name__ == "__main__":
    main()
