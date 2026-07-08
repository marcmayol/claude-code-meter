# -*- coding: utf-8 -*-
"""
Claude Code Meter  ·  Panel flotante sobre la barra de tareas.
Muestra el consumo de tokens de Claude Code (hoy / semana / mes) leyendo
los .jsonl locales, con barras de presupuesto propio para semana y mes.

Sin dependencias externas: solo la librería estándar de Python.
"""
import os, sys, json, glob, threading, time
from datetime import datetime, date
import tkinter as tk
from tkinter import font as tkfont

# ---- Windows: nitidez en pantallas HiDPI ----------------------------------
try:
    import ctypes
    from ctypes import wintypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes = None

def data_dir():
    """Carpeta de datos del usuario (config.json, logo.png).

    Al instalarse por pip el paquete vive en site-packages (solo lectura),
    así que el estado se guarda en %APPDATA%\\ClaudeCodeMeter (o ~ como fallback).
    """
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "ClaudeCodeMeter")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        d = os.path.dirname(os.path.abspath(__file__))
    return d

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
CONFIG     = os.path.join(data_dir(), "config.json")
PROJECTS   = os.path.join(os.path.expanduser("~"), ".claude", "projects")

# ---- Colores (tema oscuro, integra con barra de tareas) -------------------
BG      = "#161616"
CARD    = "#1f1f1f"
FG      = "#e8e8e8"
MUTED   = "#8a8a8a"
ACCENT  = "#d97757"   # naranja Claude
TRACK   = "#2c2c2c"
GREEN   = "#4caf7d"
AMBER   = "#e0a63a"
RED     = "#e05a54"

DEFAULT_CFG = {
    "daily_budget":   None,          # objetivo diario; si None = semanal / 7
    "weekly_budget":  10_000_000,    # objetivo semanal en tokens (editable)
    "monthly_budget": 60_000_000,    # objetivo mensual en tokens (editable)
    "count_cache_read": False,       # NO contar relectura de caché (infla x100)
    "x": None, "y": None,            # posición guardada
    "refresh_sec": 60,
}

# ---------------------------------------------------------------------------
def load_cfg():
    cfg = dict(DEFAULT_CFG)
    try:
        with open(CONFIG, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg

def save_cfg(cfg):
    try:
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

def fmt(n):
    """1234567 -> '1.23M'  ·  12345 -> '12.3K'."""
    n = float(n)
    if n >= 1_000_000_000: return f"{n/1_000_000_000:.2f}B"
    if n >= 1_000_000:     return f"{n/1_000_000:.2f}M"
    if n >= 1_000:         return f"{n/1_000:.1f}K"
    return f"{int(n)}"

# ---- Lectura de los JSONL con caché por archivo ---------------------------
class Reader:
    """Agrega tokens por día. Reparsea solo los archivos que han cambiado."""
    def __init__(self):
        self.cache = {}   # path -> (mtime, size, {dia: {t,in,out,cw,cr}})

    def _parse_file(self, path):
        daily = {}
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if '"usage"' not in line:
                        continue
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue
                    msg = d.get("message")
                    if not isinstance(msg, dict):
                        continue
                    u = msg.get("usage")
                    ts = d.get("timestamp")
                    if not isinstance(u, dict) or not ts:
                        continue
                    try:
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
                    except Exception:
                        continue
                    key = dt.date().isoformat()
                    b = daily.setdefault(key, {"t": 0, "in": 0, "out": 0, "cw": 0, "cr": 0})
                    i  = u.get("input_tokens", 0) or 0
                    o  = u.get("output_tokens", 0) or 0
                    cw = u.get("cache_creation_input_tokens", 0) or 0
                    cr = u.get("cache_read_input_tokens", 0) or 0
                    b["in"] += i; b["out"] += o; b["cw"] += cw; b["cr"] += cr
        except Exception:
            pass
        return daily

    def collect(self):
        files = glob.glob(os.path.join(PROJECTS, "**", "*.jsonl"), recursive=True)
        for path in files:
            try:
                st = os.stat(path)
            except OSError:
                continue
            sig = (st.st_mtime, st.st_size)
            cached = self.cache.get(path)
            if not cached or cached[0] != sig[0] or cached[1] != sig[1]:
                self.cache[path] = (sig[0], sig[1], self._parse_file(path))
        # borrar del cache archivos ya inexistentes
        for gone in set(self.cache) - set(files):
            del self.cache[gone]
        # combinar
        total = {}
        for _, _, daily in self.cache.values():
            for day, b in daily.items():
                acc = total.setdefault(day, {"in": 0, "out": 0, "cw": 0, "cr": 0})
                for k in ("in", "out", "cw", "cr"):
                    acc[k] += b[k]
        return total

def sum_period(daily, days, count_cr):
    tot = {"t": 0, "in": 0, "out": 0, "cw": 0, "cr": 0}
    for d in days:
        b = daily.get(d)
        if not b:
            continue
        tot["in"] += b["in"]; tot["out"] += b["out"]
        tot["cw"] += b["cw"]; tot["cr"] += b["cr"]
    tot["t"] = tot["in"] + tot["out"] + tot["cw"] + (tot["cr"] if count_cr else 0)
    return tot

def days_of_week(today):
    iso_y, iso_w, iso_d = today.isocalendar()
    monday = date.fromordinal(today.toordinal() - (iso_d - 1))
    return [(date.fromordinal(monday.toordinal() + i)).isoformat() for i in range(7)]

def days_of_month(today):
    import calendar
    n = calendar.monthrange(today.year, today.month)[1]
    return [date(today.year, today.month, d).isoformat() for d in range(1, n + 1)]

# ---------------------------------------------------------------------------
class Meter(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = load_cfg()
        self.reader = Reader()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=BG)
        try:
            dpi = ctypes.windll.user32.GetDpiForSystem() if ctypes else 96
            self.tk.call("tk", "scaling", dpi / 72.0)
        except Exception:
            pass

        self.f_title = tkfont.Font(family="Segoe UI", size=8, weight="bold")
        self.f_lbl   = tkfont.Font(family="Segoe UI", size=8)
        self.f_big   = tkfont.Font(family="Segoe UI Semibold", size=13)
        self.f_small = tkfont.Font(family="Segoe UI", size=7)

        self._build()
        self._place_initial()
        self._bind_drag()
        self.refresh(initial=True)

    # ---- UI ----
    def _build(self):
        pad = 8
        root = tk.Frame(self, bg=BG, highlightbackground="#333", highlightthickness=1)
        root.pack(fill="both", expand=True)
        self.root_frame = root

        head = tk.Frame(root, bg=BG)
        head.pack(fill="x", padx=pad, pady=(pad, 2))
        tk.Label(head, text="●", fg=ACCENT, bg=BG, font=self.f_title).pack(side="left")
        tk.Label(head, text=" Claude Code · tokens", fg=FG, bg=BG,
                 font=self.f_title).pack(side="left")
        close = tk.Label(head, text="✕", fg=MUTED, bg=BG, font=self.f_title, cursor="hand2")
        close.pack(side="right"); close.bind("<Button-1>", lambda e: self.destroy())
        gear = tk.Label(head, text="⚙", fg=MUTED, bg=BG, font=self.f_title, cursor="hand2")
        gear.pack(side="right", padx=(0, 6)); gear.bind("<Button-1>", lambda e: self.edit_budget())

        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True, padx=pad, pady=(2, pad))

        # HOY  (solo cifra)
        row = tk.Frame(body, bg=BG); row.pack(fill="x")
        tk.Label(row, text="HOY", fg=MUTED, bg=BG, font=self.f_lbl, width=5, anchor="w").pack(side="left")
        self.today_big = tk.Label(row, text="—", fg=FG, bg=BG, font=self.f_big, anchor="w")
        self.today_big.pack(side="left")
        self.today_sub = tk.Label(body, text="", fg=MUTED, bg=BG, font=self.f_small, anchor="w")
        self.today_sub.pack(fill="x", padx=(40, 0))

        # SEMANA y MES con barra
        self.week = self._budget_row(body, "SEM")
        self.month = self._budget_row(body, "MES")

    def _budget_row(self, parent, label):
        wrap = tk.Frame(parent, bg=BG); wrap.pack(fill="x", pady=(6, 0))
        top = tk.Frame(wrap, bg=BG); top.pack(fill="x")
        tk.Label(top, text=label, fg=MUTED, bg=BG, font=self.f_lbl, width=5, anchor="w").pack(side="left")
        val = tk.Label(top, text="—", fg=FG, bg=BG, font=self.f_lbl, anchor="w")
        val.pack(side="left")
        pct = tk.Label(top, text="", fg=MUTED, bg=BG, font=self.f_small, anchor="e")
        pct.pack(side="right")
        cv = tk.Canvas(wrap, height=6, bg=TRACK, highlightthickness=0)
        cv.pack(fill="x", pady=(3, 0))
        bar = cv.create_rectangle(0, 0, 0, 6, fill=GREEN, width=0)
        return {"val": val, "pct": pct, "cv": cv, "bar": bar}

    def _set_bar(self, row, used, budget):
        row["val"].config(text=f"{fmt(used)} / {fmt(budget)}")
        frac = 0 if budget <= 0 else min(used / budget, 1.0)
        pct = 0 if budget <= 0 else used / budget * 100
        row["pct"].config(text=f"{pct:.0f}%")
        color = GREEN if pct < 70 else (AMBER if pct < 90 else RED)
        w = max(row["cv"].winfo_width(), 1)
        row["cv"].coords(row["bar"], 0, 0, int(w * frac), 6)
        row["cv"].itemconfig(row["bar"], fill=color)

    # ---- posición y arrastre ----
    def _work_area(self):
        try:
            SPI = 0x0030
            r = wintypes.RECT()
            ctypes.windll.user32.SystemParametersInfoW(SPI, 0, ctypes.byref(r), 0)
            return r.right, r.bottom
        except Exception:
            return self.winfo_screenwidth(), self.winfo_screenheight()

    def _place_initial(self):
        self.update_idletasks()
        w = self.winfo_reqwidth(); h = self.winfo_reqheight()
        w = max(w, 230)
        if self.cfg.get("x") is not None and self.cfg.get("y") is not None:
            x, y = self.cfg["x"], self.cfg["y"]
        else:
            rx, ry = self._work_area()
            x = rx - w - 8
            y = ry - h - 8
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _bind_drag(self):
        for widget in (self, self.root_frame):
            widget.bind("<Button-1>", self._start)
            widget.bind("<B1-Motion>", self._drag)
            widget.bind("<ButtonRelease-1>", self._end)
        self._dx = self._dy = 0

    def _start(self, e): self._dx, self._dy = e.x, e.y
    def _drag(self, e):
        x = self.winfo_x() + e.x - self._dx
        y = self.winfo_y() + e.y - self._dy
        self.geometry(f"+{x}+{y}")
    def _end(self, e):
        self.cfg["x"], self.cfg["y"] = self.winfo_x(), self.winfo_y()
        save_cfg(self.cfg)

    # ---- edición de presupuesto ----
    def edit_budget(self):
        win = tk.Toplevel(self); win.configure(bg=CARD)
        win.title("Presupuesto"); win.attributes("-topmost", True)
        win.resizable(False, False)
        tk.Label(win, text="Objetivo personal de tokens\n(NO es el límite de tu plan Claude)",
                 fg=FG, bg=CARD, justify="center",
                 font=self.f_title).grid(row=0, column=0, columnspan=2, padx=12, pady=(12, 8))

        def field(r, text, val):
            tk.Label(win, text=text, fg=FG, bg=CARD, font=self.f_lbl).grid(
                row=r, column=0, sticky="w", padx=12, pady=4)
            e = tk.Entry(win, width=16, justify="right")
            e.insert(0, str(val)); e.grid(row=r, column=1, padx=12, pady=4)
            return e
        e_w = field(1, "Semanal", self.cfg["weekly_budget"])
        e_m = field(2, "Mensual", self.cfg["monthly_budget"])

        cr = tk.BooleanVar(value=self.cfg["count_cache_read"])
        tk.Checkbutton(win, text="Contar tokens de lectura de caché", variable=cr,
                       fg=FG, bg=CARD, selectcolor=CARD, activebackground=CARD,
                       font=self.f_small).grid(row=3, column=0, columnspan=2, sticky="w", padx=12)

        info = tk.Label(win, text="Tip: escribe p.ej. 50000000 (=50M)", fg=MUTED, bg=CARD,
                        font=self.f_small)
        info.grid(row=4, column=0, columnspan=2, padx=12, pady=(0, 4))

        def apply():
            def parse(s):
                s = s.strip().upper().replace(" ", "")
                mult = 1
                if s.endswith("M"): mult, s = 1_000_000, s[:-1]
                elif s.endswith("K"): mult, s = 1_000, s[:-1]
                elif s.endswith("B"): mult, s = 1_000_000_000, s[:-1]
                try: return int(float(s) * mult)
                except Exception: return None
            wv, mv = parse(e_w.get()), parse(e_m.get())
            if wv: self.cfg["weekly_budget"] = wv
            if mv: self.cfg["monthly_budget"] = mv
            self.cfg["count_cache_read"] = cr.get()
            save_cfg(self.cfg); win.destroy(); self.refresh()
        tk.Button(win, text="Guardar", command=apply).grid(
            row=5, column=0, columnspan=2, pady=(4, 12))

    # ---- refresco ----
    def refresh(self, initial=False):
        def work():
            daily = self.reader.collect()
            today = datetime.now().astimezone().date()
            cr = self.cfg["count_cache_read"]
            d = sum_period(daily, [today.isoformat()], cr)
            w = sum_period(daily, days_of_week(today), cr)
            m = sum_period(daily, days_of_month(today), cr)
            self.after(0, lambda: self._render(d, w, m))
        threading.Thread(target=work, daemon=True).start()
        self.after(self.cfg.get("refresh_sec", 60) * 1000, self.refresh)

    def _render(self, d, w, m):
        self.today_big.config(text=fmt(d["t"]))
        cr_txt = f" · read {fmt(d['cr'])}" if self.cfg["count_cache_read"] else ""
        self.today_sub.config(text=f"in {fmt(d['in'])} · out {fmt(d['out'])} · "
                                   f"cache-w {fmt(d['cw'])}{cr_txt}")
        self.update_idletasks()
        self._set_bar(self.week,  w["t"], self.cfg["weekly_budget"])
        self._set_bar(self.month, m["t"], self.cfg["monthly_budget"])

if __name__ == "__main__":
    Meter().mainloop()
