# -*- coding: utf-8 -*-
"""
Claude Code Meter (bandeja)  ·  Icono en la barra de tareas.
Dibuja el % de un límite REAL del plan (sesión 5h / semana 7d / mes calibrado)
como icono, con el desglose completo en el tooltip y en el menú.

Usa el estado compartido ``usage.PlanState`` (lo mismo que la versión de barra).
Requiere pystray + Pillow.
"""
import os, sys, threading, time, webbrowser

try:
    from . import meter   # instalado como paquete
    from . import usage
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import meter           # ejecución directa (python tray.py)
    import usage

from PIL import Image, ImageDraw, ImageFont
import pystray
from pystray import Menu, MenuItem as Item

GREEN = (76, 175, 125)
AMBER = (224, 166, 58)
RED   = (224, 90, 84)
GREY  = (150, 150, 150)

# métrica que se dibuja en el icono
METRICS = [("session", "Sesión (5h)"), ("week", "Semana (7d)"), ("month", "Mes")]


def load_font(size):
    for name in ("seguisb.ttf", "segoeuib.ttf", "arialbd.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def status_color(pct):
    return GREEN if pct < 70 else (AMBER if pct < 90 else RED)


def make_icon(text, color, size=64):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fs = 40
    while fs > 10:
        f = load_font(fs)
        bb = d.textbbox((0, 0), text, font=f)
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        if w <= size - 6 and h <= size - 6:
            break
        fs -= 2
    f = load_font(fs)
    bb = d.textbbox((0, 0), text, font=f)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    x = (size - w) / 2 - bb[0]
    y = (size - h) / 2 - bb[1]
    for dx in (-2, 0, 2):      # contorno para legibilidad
        for dy in (-2, 0, 2):
            if dx or dy:
                d.text((x + dx, y + dy), text, font=f, fill=(0, 0, 0, 160))
    d.text((x, y), text, font=f, fill=color + (255,))
    return img


class App:
    def __init__(self):
        self.cfg = meter.load_cfg()
        m = self.cfg.get("icon_metric", "week")
        if m not in {k for k, _ in METRICS}:   # migrar valores antiguos
            m = "month" if m == "month_pct" else "week"
        self.cfg["icon_metric"] = m
        self.state = usage.PlanState(
            os.path.join(meter.data_dir(), "calib.json"),
            self.cfg.get("limits_refresh_sec", 300))
        self.icon = pystray.Icon(
            "cc_meter",
            icon=make_icon("…", GREY),
            title="Claude Code · leyendo…",
            menu=self._menu(),
        )

    # ---- lectura del estado en textos ----
    def _metric_value(self, key):
        """Devuelve (pct|None) de la métrica: session/week/month."""
        if key == "session":
            return None if not self.state.s5h else self.state.s5h["pct"]
        if key == "week":
            return None if not self.state.s7d else self.state.s7d["pct"]
        return self.state.month_pct

    def _pct_txt(self, pct):
        return "…" if pct is None else f"{pct:.0f}%"

    def _menu(self):
        def line(label, key):
            return Item(lambda i: f"{label}: {self._pct_txt(self._metric_value(key))}",
                        None, enabled=False)

        def reset_line():
            parts = []
            for lbl, s in (("5h", self.state.s5h), ("7d", self.state.s7d)):
                if s and s.get("reset_h"):
                    parts.append(f"{lbl} {s['reset_h']}")
            return "reset · " + " · ".join(parts) if parts else "reset —"

        metric_items = tuple(
            Item(f"Icono: {label}", self._set_metric(key),
                 checked=lambda i, key=key: self.cfg["icon_metric"] == key, radio=True)
            for key, label in METRICS
        )
        return Menu(
            Item(lambda i: "Claude Code · límites del plan", None, enabled=False),
            Menu.SEPARATOR,
            line("Sesión 5h", "session"),
            line("Semana 7d", "week"),
            line("Mes      ", "month"),
            Item(lambda i: reset_line(), None, enabled=False),
            Menu.SEPARATOR,
            *metric_items,
            Menu.SEPARATOR,
            Item("Actualizar ahora", lambda i: self.refresh()),
            Item("Salir", self._quit),
        )

    def _set_metric(self, val):
        def cb(icon, item):
            self.cfg["icon_metric"] = val
            meter.save_cfg(self.cfg)
            self.refresh()
        return cb

    def _quit(self, icon, item):
        self.stop = True
        icon.stop()

    # ---- refresco ----
    def refresh(self):
        self.cfg = {**self.cfg, **meter.load_cfg()}
        self.state.limits_refresh_sec = self.cfg.get("limits_refresh_sec", 300)
        self.state.update(self.cfg.get("count_cache_read", False))

        pct = self._metric_value(self.cfg["icon_metric"])
        color = GREY if pct is None else status_color(pct)
        self.icon.icon = make_icon(self._pct_txt(pct), color)

        def tip(lbl, s):
            if not s:
                return f"{lbl} …"
            r = f"  (reset {s['reset_h']})" if s.get("reset_h") else ""
            return f"{lbl} {s['pct']:.0f}%{r}"
        mtxt = "…" if self.state.month_pct is None else f"{self.state.month_pct:.0f}%"
        self.icon.title = (
            "Claude Code · límites del plan\n"
            + tip("Sesión 5h", self.state.s5h) + "\n"
            + tip("Semana 7d", self.state.s7d) + "\n"
            + f"Mes {mtxt}"
        )
        try:
            self.icon.update_menu()
        except Exception:
            pass

    def _loop(self):
        self.stop = False
        while not getattr(self, "stop", False):
            try:
                self.refresh()
            except Exception:
                pass
            for _ in range(int(self.cfg.get("refresh_sec", 60))):
                if getattr(self, "stop", False):
                    return
                time.sleep(1)

    def run(self):
        threading.Thread(target=self._loop, daemon=True).start()
        self.icon.run()


if __name__ == "__main__":
    App().run()
