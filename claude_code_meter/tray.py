# -*- coding: utf-8 -*-
"""
Claude Code Meter (bandeja)  ·  Icono DENTRO de la barra de tareas.
Dibuja el dato elegido (tokens de hoy o % del objetivo mensual) como icono,
con el desglose hoy/semana/mes en el tooltip y un menú para ajustar/salir.

Reutiliza la lógica de lectura de meter.py. Requiere pystray + Pillow.
"""
import os, sys, threading, time, webbrowser
from datetime import datetime

try:
    from . import meter  # instalado como paquete
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import meter          # ejecución directa (python tray.py)

from PIL import Image, ImageDraw, ImageFont
import pystray
from pystray import Menu, MenuItem as Item

GREEN = (76, 175, 125)
AMBER = (224, 166, 58)
RED   = (224, 90, 84)

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
    # contorno para legibilidad sobre barras claras u oscuras
    for dx in (-2, 0, 2):
        for dy in (-2, 0, 2):
            if dx or dy:
                d.text((x + dx, y + dy), text, font=f, fill=(0, 0, 0, 160))
    d.text((x, y), text, font=f, fill=color + (255,))
    return img


class App:
    def __init__(self):
        self.cfg = meter.load_cfg()
        self.cfg.setdefault("icon_metric", "month_pct")  # "today" | "month_pct"
        self.reader = meter.Reader()
        self.d = self.w = self.m = {"t": 0, "in": 0, "out": 0, "cw": 0, "cr": 0}
        self.icon = pystray.Icon(
            "cc_meter",
            icon=make_icon("…", (150, 150, 150)),
            title="Claude Code · leyendo…",
            menu=self._menu(),
        )

    # ---- textos ----
    def _pct(self, used, budget):
        return 0 if budget <= 0 else used / budget * 100

    def _menu(self):
        def line(label, get):
            return Item(lambda i: f"{label}: {get()}", None, enabled=False)
        return Menu(
            Item(lambda i: "Claude Code · tokens (trabajo real)", None, enabled=False),
            Menu.SEPARATOR,
            line("Hoy   ", lambda: meter.fmt(self.d["t"])),
            line("Semana", lambda: f"{meter.fmt(self.w['t'])} / {meter.fmt(self.cfg['weekly_budget'])}"
                                   f"  ({self._pct(self.w['t'], self.cfg['weekly_budget']):.0f}%)"),
            line("Mes   ", lambda: f"{meter.fmt(self.m['t'])} / {meter.fmt(self.cfg['monthly_budget'])}"
                                   f"  ({self._pct(self.m['t'], self.cfg['monthly_budget']):.0f}%)"),
            Menu.SEPARATOR,
            Item("Mostrar en icono: tokens de hoy",
                 self._set_metric("today"),
                 checked=lambda i: self.cfg["icon_metric"] == "today", radio=True),
            Item("Mostrar en icono: % del mes",
                 self._set_metric("month_pct"),
                 checked=lambda i: self.cfg["icon_metric"] == "month_pct", radio=True),
            Menu.SEPARATOR,
            Item("Ajustar objetivo (abrir config)…", self._edit),
            Item("Actualizar ahora", lambda i: self.refresh()),
            Item("Salir", self._quit),
        )

    def _set_metric(self, val):
        def cb(icon, item):
            self.cfg["icon_metric"] = val
            meter.save_cfg(self.cfg)
            self.refresh()
        return cb

    def _edit(self, icon, item):
        # asegurar que el archivo existe, y abrirlo con el editor por defecto
        meter.save_cfg(self.cfg)
        try:
            os.startfile(meter.CONFIG)  # type: ignore[attr-defined]
        except Exception:
            webbrowser.open(meter.CONFIG)

    def _quit(self, icon, item):
        self.stop = True
        icon.stop()

    # ---- refresco ----
    def refresh(self):
        # relee config por si el usuario editó el archivo a mano
        self.cfg = {**self.cfg, **meter.load_cfg()}
        self.cfg.setdefault("icon_metric", "month_pct")
        daily = self.reader.collect()
        today = datetime.now().astimezone().date()
        cr = self.cfg["count_cache_read"]
        self.d = meter.sum_period(daily, [today.isoformat()], cr)
        self.w = meter.sum_period(daily, meter.days_of_week(today), cr)
        self.m = meter.sum_period(daily, meter.days_of_month(today), cr)

        pct_m = self._pct(self.m["t"], self.cfg["monthly_budget"])
        color = status_color(pct_m)
        if self.cfg["icon_metric"] == "month_pct":
            txt = f"{pct_m:.0f}%"
        else:
            txt = meter.fmt(self.d["t"])
        self.icon.icon = make_icon(txt, color)
        self.icon.title = (
            "Claude Code · tokens (trabajo real)\n"
            f"Hoy {meter.fmt(self.d['t'])}\n"
            f"Semana {meter.fmt(self.w['t'])} / {meter.fmt(self.cfg['weekly_budget'])}"
            f" ({self._pct(self.w['t'], self.cfg['weekly_budget']):.0f}%)\n"
            f"Mes {meter.fmt(self.m['t'])} / {meter.fmt(self.cfg['monthly_budget'])}"
            f" ({pct_m:.0f}%)"
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
