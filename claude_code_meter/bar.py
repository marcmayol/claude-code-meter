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
    """Genera el destello (sunburst) de Claude como PNG transparente.

    Réplica vectorial del isotipo de Claude: 11 rayos finos y afilados que
    parten del centro, con la longitud alternando levemente para dar el aspecto
    orgánico de destello del logo real. Se dibuja en código (no un PNG externo)
    para que el paquete sea autocontenido y portable."""
    size = max(int(size), 14)
    S = size * 4  # supersampling para bordes suaves
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = S / 2
    rays = 11
    for i in range(rays):
        ang = math.pi * 2 * i / rays - math.pi / 2
        ux, uy = math.cos(ang), math.sin(ang)   # eje del rayo
        px, py = -uy, ux                         # perpendicular
        base, mid, tip = S * 0.05, S * 0.27, S * 0.48
        hw = S * 0.045                           # semiancho (fino) en el punto medio
        pts = [
            (cx + ux * base, cy + uy * base),                   # cuello, cerca del centro
            (cx + ux * mid + px * hw, cy + uy * mid + py * hw),  # ancho en el medio
            (cx + ux * tip, cy + uy * tip),                     # punta afilada
            (cx + ux * mid - px * hw, cy + uy * mid - py * hw),  # ancho en el medio (otro lado)
        ]
        d.polygon(pts, fill=color + (255,))
    # núcleo pequeño para que los rayos converjan limpio
    c = S * 0.05
    d.ellipse([cx - c, cy - c, cx + c, cy + c], fill=color + (255,))
    img.resize((size, size), Image.LANCZOS).save(path)

try:
    from . import meter          # instalado como paquete
    from . import limits
    from . import usage
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import meter                 # ejecución directa (python bar.py)
    import limits
    import usage

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
    ("GetForegroundWindow", wintypes.HWND, []),
    ("GetClassNameW", ctypes.c_int, [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]),
    ("MonitorFromWindow", wintypes.HANDLE, [wintypes.HWND, wintypes.DWORD]),
    ("GetMonitorInfoW", wintypes.BOOL, [wintypes.HANDLE, ctypes.c_void_p]),
]:
    f = getattr(user32, fn); f.restype = res; f.argtypes = args

GA_ROOT = 2
HWND_TOP = 0
HWND_TOPMOST = -1
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_NOSIZE = 0x0001
MONITOR_DEFAULTTONEAREST = 2


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


def is_fullscreen_active():
    """True si la ventana en primer plano ocupa TODO el monitor (peli/juego a
    pantalla completa). No cuenta el escritorio, la shell ni ventanas maximizadas
    normales (esas respetan el área de trabajo y dejan ver la barra)."""
    fg = user32.GetForegroundWindow()
    if not fg:
        return False
    buf = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(fg, buf, 64)
    if buf.value in ("WorkerW", "Progman", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
        return False
    r = wintypes.RECT()
    if not user32.GetWindowRect(fg, ctypes.byref(r)):
        return False
    mon = user32.MonitorFromWindow(fg, MONITOR_DEFAULTTONEAREST)
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    if not user32.GetMonitorInfoW(mon, ctypes.byref(mi)):
        return False
    m = mi.rcMonitor
    return (r.left <= m.left and r.top <= m.top
            and r.right >= m.right and r.bottom >= m.bottom)

BG    = "#000000"   # negro para fundir con la barra oscura
FG    = "#f0f0f0"
MUTED = "#9a9a9a"
ACCENT = "#d97757"

def is_spanish_ui():
    """True si el idioma de Windows es español (para D/S/M vs D/W/M)."""
    try:
        buf = ctypes.create_unicode_buffer(85)
        ctypes.windll.kernel32.GetUserDefaultLocaleName(buf, 85)
        return buf.value.lower().startswith("es")
    except Exception:
        return False


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

        self._limits = None       # último resultado de limits.fetch()
        self._limits_at = 0.0     # epoch de la última consulta con éxito
        self._limits_err = None
        self._month_pct = None    # % del mes en la escala calibrada del plan
        self._weekly_limit = None # límite semanal estimado (tokens)
        self._week_hist = []      # % del plan de las últimas semanas (regla de 3)
        self.hreader = usage.HourlyReader()
        self._calib_path = os.path.join(meter.data_dir(), "calib.json")

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
        logo_path = os.path.join(meter.data_dir(), "logo.png")
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
        # Límites reales del plan: 5h = ventana de sesión · 7d = ventana semanal
        self.v5h = block("5h")
        self.v7d = block("7d")
        # M = cuota mensual propia (NO es límite del plan; consumo local del mes)
        self.vm = block("M")

        # menú contextual: info (reset + calibración), historial y acciones
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="reset —", state="disabled")   # info de reset
        self.menu.add_command(label="límite semanal —", state="disabled")  # calibración
        self.menu.add_separator()
        self.hist_menu = tk.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="Historial semanal", menu=self.hist_menu)
        self.menu.add_separator()
        self.menu.add_command(label="Actualizar ahora", command=self.refresh)
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
        self._hidden = False
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
        # ocultar sobre apps a pantalla completa (pelis, juegos); si no,
        # re-elevar por encima de la barra y recolocar (la barra es topmost)
        if is_fullscreen_active():
            if not self._hidden:
                self.withdraw()
                self._hidden = True
        else:
            if self._hidden:
                self.deiconify()
                self._hidden = False
            self._reposition()
        self.after(700, self._keep)

    # ---- datos ----
    def refresh(self):
        def work():
            # Los límites del plan se consultan a la API con moderación (cada
            # ~5 min): cada consulta gasta ~1 token. Entre medias reusamos el
            # último resultado; solo se recoloca la ventana en cada ciclo.
            every = self.cfg.get("limits_refresh_sec", 300)
            if time.time() - self._limits_at >= every:
                res = limits.fetch()
                if res.get("ok"):
                    self._limits = res
                    self._limits_at = time.time()
                    self._limits_err = None
                else:
                    self._limits_err = res.get("error", "?")

            # Mes en la escala REAL del plan (auto-calibrado). El consumo se lee
            # por hora de los .jsonl locales (barato, cada ciclo).
            self.cfg = {**self.cfg, **meter.load_cfg()}
            cr = self.cfg.get("count_cache_read", False)
            hourly = self.hreader.collect()
            now = time.time()
            w7d = (self._limits or {}).get("windows", {}).get("7d") if self._limits else None
            if w7d and w7d.get("reset"):
                # tokens de la ventana que el plan mide AHORA (anclada al reset)
                w_start, _ = usage.plan_week_window(w7d["reset"])
                wtok = usage.sum_range(hourly, w_start, now, cr)
                self._weekly_limit = usage.update_calibration(
                    self._calib_path, w7d["used"], wtok["t"], int(now))
            if self._weekly_limit:
                mtok = usage.sum_range(hourly, usage.month_start(), now, cr)
                budget = self._weekly_limit * usage.days_in_month() / 7
                self._month_pct = 0 if budget <= 0 else mtok["t"] / budget * 100
                if w7d and w7d.get("reset"):
                    # % de las semanas anteriores por regla de tres (el header
                    # solo recuerda la actual; el resto sale de los .jsonl)
                    self._week_hist = usage.week_history(
                        hourly, w7d["reset"], self._weekly_limit, now, n=6, count_cr=cr)
            self.after(0, self._render)
        threading.Thread(target=work, daemon=True).start()
        self.after(self.cfg.get("refresh_sec", 60) * 1000, self.refresh)

    def _render(self):
        # M = consumo del mes en la escala calibrada del plan. Se pinta en cuanto
        # hay calibración; hasta entonces "…".
        if self._month_pct is not None:
            self.vm.config(text=f"{self._month_pct:.0f}%", fg=meter_color(self._month_pct))

        res = self._limits
        if not res:
            txt = "…" if not self._limits_err else "!"
            self.v5h.config(text=txt, fg=MUTED)
            self.v7d.config(text=txt, fg=MUTED)
            self._reposition()
            return
        wins = res.get("windows", {})
        resets = []
        for lbl, key in (("5h", self.v5h), ("7d", self.v7d)):
            w = wins.get(lbl)
            if not w:
                key.config(text="—", fg=MUTED)
                continue
            pct = w["used"] * 100
            key.config(text=f"{pct:.0f}%", fg=meter_color(pct))
            r = limits.human_reset(w.get("reset"))
            if r:
                resets.append(f"{lbl} {r}")
        if resets:
            self.menu.entryconfig(0, label="reset · " + " · ".join(resets))
        if self._weekly_limit:
            wl = self._weekly_limit
            txt = f"{wl/1e9:.1f}B" if wl >= 1e9 else f"{wl/1e6:.0f}M"
            self.menu.entryconfig(1, label=f"límite sem. ≈ {txt} tok (calibrado)")
        self._fill_history()
        self._reposition()

    def _fill_history(self):
        self.hist_menu.delete(0, "end")
        if not self._week_hist:
            self.hist_menu.add_command(label="(calibrando…)", state="disabled")
            return
        for h in self._week_hist:
            d0 = datetime.fromtimestamp(h["start"]).strftime("%d %b")
            d1 = datetime.fromtimestamp(h["end"]).strftime("%d %b")
            tag = "esta sem" if h["current"] else f"hace {h['i']}"
            self.hist_menu.add_command(
                label=f"{tag:<8} {d0}–{d1}   {h['pct']:.0f}%", state="disabled")


def meter_color(pct):
    return "#4caf7d" if pct < 70 else ("#e0a63a" if pct < 90 else "#e05a54")


if __name__ == "__main__":
    Bar().mainloop()
