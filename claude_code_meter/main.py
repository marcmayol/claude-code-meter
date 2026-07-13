# -*- coding: utf-8 -*-
"""
Punto de entrada de Claude Code Meter.

Elige UNA presentación (no se lanzan las tres a la vez; muestran lo mismo
de formas distintas):

    claude-code-meter          -> barra de tareas (Windows) / panel (Linux·macOS)
    claude-code-meter tray     -> icono en la bandeja del sistema (Windows)
    claude-code-meter panel    -> panel flotante en la esquina (multiplataforma)

(o `python -m claude_code_meter.main [bar|tray|panel]`)

`bar` y `tray` se incrustan en la barra de tareas de Windows; en Linux/macOS,
donde no hay una barra fija donde incrustarse, el estilo recomendado es `panel`
(y es el que se usa por defecto en esas plataformas).
"""
import sys
import importlib

IS_WIN = sys.platform.startswith("win")

USAGE = ("Uso: claude-code-meter [bar|tray|panel]   "
         f"(por defecto: {'bar' if IS_WIN else 'panel'})")


def _load(name):
    """Importa un submódulo funcione instalado (paquete) o en ejecución directa."""
    try:
        return importlib.import_module("." + name, __package__)
    except (ImportError, TypeError):
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        return importlib.import_module(name)


def main():
    default = "bar" if IS_WIN else "panel"
    choice = (sys.argv[1] if len(sys.argv) > 1 else default).lower()

    # bar/tray se incrustan en la barra de Windows: fuera de Windows -> panel
    if not IS_WIN and choice in ("bar", "barra", "tray", "bandeja"):
        print(f"El estilo '{choice}' es específico de la barra de tareas de "
              f"Windows y no está disponible en {sys.platform}. Usando 'panel'.")
        choice = "panel"

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
