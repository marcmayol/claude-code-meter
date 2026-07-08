# -*- coding: utf-8 -*-
"""
Punto de entrada de Claude Code Meter.

Elige UNA presentación (no se lanzan las tres a la vez; muestran lo mismo
de formas distintas):

    python main.py          -> barra de tareas (por defecto, recomendado)
    python main.py tray     -> icono en la bandeja del sistema
    python main.py panel    -> panel flotante en la esquina
"""
import sys

USAGE = "Uso: python main.py [bar|tray|panel]   (por defecto: bar)"


def main():
    choice = (sys.argv[1] if len(sys.argv) > 1 else "bar").lower()

    if choice in ("bar", "barra"):
        import bar
        bar.Bar().mainloop()
    elif choice in ("tray", "bandeja"):
        import tray
        tray.App().run()
    elif choice in ("panel", "meter", "flotante", "float"):
        import meter
        meter.Meter().mainloop()
    elif choice in ("-h", "--help", "help"):
        print(USAGE)
    else:
        print(f"Estilo desconocido: {choice!r}\n{USAGE}")
        sys.exit(1)


if __name__ == "__main__":
    main()
