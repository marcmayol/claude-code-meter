# -*- coding: utf-8 -*-
"""Punto de entrada para el ejecutable .exe (PyInstaller).

Doble clic -> arranca el estilo barra. También acepta argumento:
    claude-code-meter.exe tray|panel
"""
from claude_code_meter.main import main

if __name__ == "__main__":
    main()
