# -*- coding: utf-8 -*-
"""
Claude Code Meter (incrustado)  ·  Cifras DENTRO de la barra de tareas.
Se inserta en la barra (Shell_TrayWnd) a la izquierda del reloj mediante
SetParent, mostrando D (hoy) · S (semana) · M (mes) siempre visibles.

Misma técnica que TrafficMonitor. Reutiliza la lógica de meter.py.
Cerrar: clic derecho sobre las cifras -> Salir  (o matar el proceso).
"""
import os, sys, threading, time, math
import ctypes
from ctypes import wintypes
from datetime import datetime
import tkinter as tk
from tkinter import font as tkfont
from PIL import Image, ImageDraw

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def make_claude_logo(size, path, color=(217, 119, 87)):
    """Genera el destello (sunburst) de Claude como PNG transparente."""
    size = max(int(size), 14)
    S = size * 4  # supersampling para bordes suaves
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = S / 2
    rays = 11
    for i in range(rays):
        ang = math.pi * 2 * i / rays - math.pi / 2
        ux, uy = math.cos(ang), math.sin(ang)   # eje del pétalo
        px, py = -uy, ux                         # perpendicular
        base, tip, mid = S * 0.04, S * 0.47, S * 0.26
        hw = S * 0.055                           # semiancho en el medio
        pts = [
            (cx + ux * base, cy + uy * base),
            (cx + ux * mid + px * hw, cy + uy * mid + py * hw),
            (cx + ux * tip, cy + uy * tip),
            (cx + ux * mid - px * hw, cy + uy * mid - py * hw),
        ]
        d.polygon(pts, fill=color + (255,))
    c = S * 0.07
    d.ellipse([cx - c, cy - c, cx + c, cy + c], fill=color + (255,))
    img.resize((size, size), Image.LANCZOS).save(path)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import meter  # Reader, sum_period, days_of_week/month, fmt, load_cfg, CONFIG, colores

user32 = ctypes.windll.user32
for fn, res, args in [
    ("FindWindowW", wintypes.HWND, [wintypes.LPCWSTR, wintypes.LPCWSTR]),
    ("FindWindowExW", wintypes.HWND, [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]),
    ("SetParent", wintypes.HWND, [wintypes.HWND, wintypes.HWND]),
    ("GetParent", wintypes.HWND, [wintypes.HWND]),
    ("GetWindowRect", wintypes.BOOL, [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]),
    ("SetWindowPos", wintypes.BOOL, [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                     ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]),
    ("GetAncestor", wintypes.HWND, [wintypes.HWND, wintypes.UINT]),
]:
    f = getattr(user32, fn); f.restype = res; f.argtypes = args

GA_ROOT = 2
HWND_TOP = 0
HWND_TOPMOST = -1
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_NOSIZE = 0x0001

BG    = "#000000"   # negro para fundir con la barra oscura
FG    = "#f0f0f0"
MUTED = "#9a9a9a"
ACCENT = "#d97757"

def taskbar_hwnd():
    return user32.FindWindowW("Shell_TrayWnd", None)

def traynotify_rect(bar):
    tn = user32.FindWindowExW(bar, None, "TrayNotifyWnd", None)
    r = wintypes.RECT()
    if tn and user32.GetWindowRect(tn, ctypes.byref(r)):
        return r
    return None

def rect(hwnd):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r


class Bar(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = meter.load_cfg()
        self.reader = meter.Reader()
        self.overrideredirect(True)
        self.configure(bg=BG)
        self.attributes("-topmost", True)
        try:
            dpi = user32.GetDpiForSystem()
            self.tk.call("tk", "scaling", dpi / 72.0)
        except Exception:
            pass
        self.f  = tkfont.Font(family="Segoe UI", size=9)
        self.fb = tkfont.Font(family="Segoe UI Semibold", size=9)

        self.hwnd = None
        self._build()
        self.after(200, self._embed)
        self.refresh()

    def _build(self):
        row = tk.Frame(self, bg=BG)
        row.pack(fill="both", expand=True, padx=8)
        self.row = row
        # logo de Claude (sunburst) escalado al alto del texto
        lh = int(self.fb.metrics("linespace") * 1.15)
        logo_path = os.path.join(BASE_DIR, "logo.png")
        try:
            make_claude_logo(lh, logo_path)
            self.logo = tk.PhotoImage(file=logo_path)
            tk.Label(row, image=self.logo, bg=BG).pack(side="left", padx=(0, 6))
        except Exception:
            tk.Label(row, text="✳", fg=ACCENT, bg=BG, font=self.fb).pack(side="left", padx=(0, 6))

        def block(letter):
            tk.Label(row, text=letter, fg=MUTED, bg=BG, font=self.f).pack(side="left")
            v = tk.Label(row, text="—", fg=FG, bg=BG, font=self.fb)
            v.pack(side="left", padx=(2, 10))
            return v
        self.vd = block("D")
        self.vs = block("S")
        self.vm = block("M")

        # menú contextual para salir / ajustar
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Ajustar objetivo…", command=self._edit)
        self.menu.add_command(label="Actualizar ahora", command=self.refresh)
        self.menu.add_separator()
        self.menu.add_command(label="Salir", command=self.destroy)
        for w in (self, row):
            w.bind("<Button-3>", self._popup)

    def _popup(self, e):
        try:
            self.menu.tk_popup(e.x_root, e.y_root)
        finally:
            self.menu.grab_release()

    def _edit(self):
        meter.save_cfg(self.cfg)
        try:
            os.startfile(meter.CONFIG)
        except Exception:
            pass

    # ---- superponer sobre la franja de la barra (topmost, sin SetParent) ----
    # En Windows 11 la barra repinta encima de las ventanas hijas, así que en
    # vez de incrustar con SetParent mantenemos una ventana TOPMOST colocada
    # exactamente sobre el hueco de la barra, a la izquierda del reloj.
    def _embed(self):
        self.update_idletasks()
        self.hwnd = user32.GetAncestor(self.winfo_id(), GA_ROOT)
        self._reposition()
        self.after(700, self._keep)

    def _reposition(self):
        bar = taskbar_hwnd()
        if not bar or not self.hwnd:
            return
        br = rect(bar)               # coords de PANTALLA (proceso DPI-aware)
        bar_h = br.bottom - br.top
        self.update_idletasks()
        w = max(self.winfo_reqwidth(), 120)
        h = bar_h
        tn = traynotify_rect(bar)
        if tn:
            x = tn.left - w - 12     # justo a la izquierda del reloj/bandeja
        else:
            x = br.right - w - 220
        x = max(x, br.left)
        y = br.top
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, x, y, w, h,
                            SWP_NOACTIVATE | SWP_SHOWWINDOW)

    def _keep(self):
        # re-elevar por encima de la barra y recolocar (la barra es topmost)
        self._reposition()
        self.after(700, self._keep)

    # ---- datos ----
    def refresh(self):
        def work():
            daily = self.reader.collect()
            today = datetime.now().astimezone().date()
            cr = self.cfg.get("count_cache_read", False)
            d = meter.sum_period(daily, [today.isoformat()], cr)
            w = meter.sum_period(daily, meter.days_of_week(today), cr)
            m = meter.sum_period(daily, meter.days_of_month(today), cr)
            self.after(0, lambda: self._render(d, w, m))
        threading.Thread(target=work, daemon=True).start()
        self.after(self.cfg.get("refresh_sec", 60) * 1000, self.refresh)

    def _color(self, used, budget):
        pct = 0 if budget <= 0 else used / budget * 100
        return meter_color(pct)

    def _render(self, d, w, m):
        self.cfg = {**self.cfg, **meter.load_cfg()}
        wb = self.cfg["weekly_budget"]; mb = self.cfg["monthly_budget"]
        db = self.cfg.get("daily_budget") or (wb / 7 if wb else 0)
        def pct(u, b):
            return 0 if b <= 0 else u / b * 100
        self.vd.config(text=f"{pct(d['t'], db):.0f}%", fg=self._color(d["t"], db))
        self.vs.config(text=f"{pct(w['t'], wb):.0f}%", fg=self._color(w["t"], wb))
        self.vm.config(text=f"{pct(m['t'], mb):.0f}%", fg=self._color(m["t"], mb))
        self._reposition()


def meter_color(pct):
    return "#4caf7d" if pct < 70 else ("#e0a63a" if pct < 90 else "#e05a54")


if __name__ == "__main__":
    Bar().mainloop()
