# -*- coding: utf-8 -*-
"""
Punto de entrada de Claude Code Meter.

Elige UNA presentación (no se lanzan las tres a la vez; muestran lo mismo
de formas distintas):

    claude-code-meter          -> barra de tareas (por defecto, recomendado)
    claude-code-meter tray     -> icono en la bandeja del sistema
    claude-code-meter panel    -> panel flotante en la esquina

(o `python -m claude_code_meter.main [bar|tray|panel]`)
"""
import sys
import importlib

USAGE = "Uso: claude-code-meter [bar|tray|panel]   (por defecto: bar)"


def _load(name):
    """Importa un submódulo funcione instalado (paquete) o en ejecución directa."""
    try:
        return importlib.import_module("." + name, __package__)
    except (ImportError, TypeError):
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        return importlib.import_module(name)


def main():
    choice = (sys.argv[1] if len(sys.argv) > 1 else "bar").lower()

    if choice in ("bar", "barra"):
        _load("bar").Bar().mainloop()
    elif choice in ("tray", "bandeja"):
        _load("tray").App().run()
    elif choice in ("panel", "meter", "flotante", "float"):
        _load("meter").Meter().mainloop()
    elif choice in ("-h", "--help", "help"):
        print(USAGE)
    else:
        print(f"Estilo desconocido: {choice!r}\n{USAGE}")
        sys.exit(1)


if __name__ == "__main__":
    main()
