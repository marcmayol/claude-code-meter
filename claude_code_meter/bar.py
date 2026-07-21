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
    ("ShowWindow", wintypes.BOOL, [wintypes.HWND, ctypes.c_int]),
    ("GetForegroundWindow", wintypes.HWND, []),
    ("GetClassNameW", ctypes.c_int, [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]),
    ("MonitorFromWindow", wintypes.HANDLE, [wintypes.HWND, wintypes.DWORD]),
    ("GetMonitorInfoW", wintypes.BOOL, [wintypes.HANDLE, ctypes.c_void_p]),
    ("GetTopWindow", wintypes.HWND, [wintypes.HWND]),
    ("GetWindow", wintypes.HWND, [wintypes.HWND, wintypes.UINT]),
    ("IsWindowVisible", wintypes.BOOL, [wintypes.HWND]),
    ("GetWindowThreadProcessId", wintypes.DWORD, [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]),
    ("GetDC", wintypes.HDC, [wintypes.HWND]),
    ("ReleaseDC", ctypes.c_int, [wintypes.HWND, wintypes.HDC]),
]:
    f = getattr(user32, fn); f.restype = res; f.argtypes = args

gdi32 = ctypes.windll.gdi32
gdi32.GetPixel.restype = wintypes.COLORREF
gdi32.GetPixel.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]

try:
    dwmapi = ctypes.windll.dwmapi
except Exception:
    dwmapi = None

GA_ROOT = 2
HWND_TOP = 0
HWND_TOPMOST = -1
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_NOSIZE = 0x0001
SW_HIDE = 0
SW_SHOWNA = 8            # mostrar sin activar/robar el foco
MONITOR_DEFAULTTONEAREST = 2
GW_HWNDNEXT = 2
DWMWA_CLOAKED = 14
CLR_INVALID = 0xFFFFFFFF

# clases del propio shell: nunca cuentan como "algo que tapa la barra"
SHELL_CLASSES = {"Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Progman", "WorkerW",
                 "NotifyIconOverflowWindow", "TopLevelWindowForOverflowXamlIsland"}


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


# SHQueryUserNotificationState: la misma API que usa Windows para silenciar las
# notificaciones cuando hay algo a pantalla completa (juegos, vídeo D3D,
# presentaciones). Es global (no depende de cuál sea la ventana con foco), por
# eso detecta reproductores que el chequeo por rect se perdía.
try:
    shell32 = ctypes.windll.shell32
    shell32.SHQueryUserNotificationState.argtypes = [ctypes.POINTER(ctypes.c_int)]
    shell32.SHQueryUserNotificationState.restype = ctypes.c_long  # HRESULT
except Exception:
    shell32 = None

QUNS_BUSY = 2                     # app a pantalla completa (p.ej. juego)
QUNS_RUNNING_D3D_FULL_SCREEN = 3  # juego D3D a pantalla completa
QUNS_PRESENTATION_MODE = 4        # modo presentación


def _shell_says_fullscreen():
    # OJO: NO usamos QUNS_BUSY (2): tras salir de un vídeo a pantalla completa
    # Windows lo mantiene ~5 s (histéresis), lo que retrasaba la reaparición del
    # widget. El vídeo en navegador/reproductor ya lo detecta el chequeo por rect
    # (instantáneo en ambos sentidos); el shell solo aporta el caso de juegos con
    # D3D exclusivo, que no arrastra esa inercia.
    if not shell32:
        return False
    try:
        state = ctypes.c_int(0)
        if shell32.SHQueryUserNotificationState(ctypes.byref(state)) == 0:  # S_OK
            return state.value in (QUNS_RUNNING_D3D_FULL_SCREEN, QUNS_PRESENTATION_MODE)
    except Exception:
        pass
    return False


def is_fullscreen_active():
    """True si hay algo a pantalla completa (peli/juego) y el widget debe
    esconderse. Combina la API del shell (fiable para vídeo/juegos, sin depender
    del foco) con un chequeo por rect de la ventana en primer plano."""
    if _shell_says_fullscreen():
        return True
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

def _cloaked(hwnd):
    """True si DWM tiene la ventana 'cloaked' (existe pero no se dibuja: apps
    UWP suspendidas, otro escritorio virtual). Están 'visibles' para user32."""
    if not dwmapi:
        return False
    try:
        v = ctypes.c_int(0)
        if dwmapi.DwmGetWindowAttribute(wintypes.HWND(hwnd), DWMWA_CLOAKED,
                                        ctypes.byref(v), ctypes.sizeof(v)) == 0:
            return v.value != 0
    except Exception:
        pass
    return False


def _class_of(hwnd):
    buf = ctypes.create_unicode_buffer(128)
    user32.GetClassNameW(hwnd, buf, 128)
    return buf.value


def _visible_rect(hwnd):
    """Rect que el usuario ve realmente. GetWindowRect incluye los bordes
    invisibles de DWM (~8 px), que provocarían solapes fantasma con la barra."""
    if dwmapi:
        try:
            r = wintypes.RECT()
            if dwmapi.DwmGetWindowAttribute(wintypes.HWND(hwnd), 9,  # EXTENDED_FRAME_BOUNDS
                                            ctypes.byref(r), ctypes.sizeof(r)) == 0:
                return (r.left, r.top, r.right, r.bottom)
        except Exception:
            pass
    r = rect(hwnd)
    return (r.left, r.top, r.right, r.bottom)


def _overlaps(a, b, min_frac=0.25):
    """True si `a` pisa `b` en una fracción apreciable de su área (evita que un
    solape de unos pocos píxeles cuente como 'la barra está tapada')."""
    ow = min(a[2], b[2]) - max(a[0], b[0])
    oh = min(a[3], b[3]) - max(a[1], b[1])
    if ow <= 0 or oh <= 0:
        return False
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return area_b > 0 and (ow * oh) / area_b >= min_frac


def taskbar_covered(zone, own_pid):
    """True si alguna ventana ajena queda POR ENCIMA de la barra en el z-order
    y pisa `zone` (el rect del widget).

    Es la comprobación que faltaba: al ser TOPMOST el widget se veía flotando
    sobre cualquier cosa que cubriera la barra (juegos en ventana sin bordes,
    menú Inicio, paneles). Recorriendo el z-order desde arriba hasta encontrar
    Shell_TrayWnd sabemos si la barra sigue siendo lo visible en esa zona.
    """
    bar = taskbar_hwnd()
    if not bar:
        return False
    h = user32.GetTopWindow(None)
    guard = 0
    while h and h != bar and guard < 2000:
        guard += 1
        if user32.IsWindowVisible(h):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
            if pid.value != own_pid and _class_of(h) not in SHELL_CLASSES and not _cloaked(h):
                if _overlaps(_visible_rect(h), zone):
                    return True
        h = user32.GetWindow(h, GW_HWNDNEXT)
    return False


def sample_bar_color(points):
    """Color medio real de la barra en esos puntos de pantalla.

    La barra de Windows 11 es translúcida: su color depende del fondo de
    escritorio y del tema, así que pintar negro fijo dejaba un recuadro visible.
    Se muestrea fuera del rect del widget para no leerse a sí mismo."""
    hdc = user32.GetDC(None)
    if not hdc:
        return None
    try:
        vals = []
        for x, y in points:
            c = gdi32.GetPixel(hdc, int(x), int(y))
            if c != CLR_INVALID:
                vals.append((c & 0xFF, (c >> 8) & 0xFF, (c >> 16) & 0xFF))
    finally:
        user32.ReleaseDC(None, hdc)
    if not vals:
        return None
    # mediana por canal: inmune a que un punto caiga sobre un icono
    med = [sorted(v[i] for v in vals)[len(vals) // 2] for i in range(3)]
    return "#%02x%02x%02x" % tuple(med)


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

        # estado compartido (límites reales del plan + mes calibrado + historial)
        self.state = usage.PlanState(
            os.path.join(meter.data_dir(), "calib.json"),
            self.cfg.get("limits_refresh_sec", 300))

        self.hwnd = None
        self.pid = os.getpid()
        self._zone = None
        self._bg = BG
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

        self.tags = []          # etiquetas 5h/7d/M (color atenuado)
        self.vals = {}          # valor -> último pct pintado, para recolorear

        def block(letter):
            t = tk.Label(row, text=letter, fg=MUTED, bg=BG, font=self.f)
            t.pack(side="left")
            self.tags.append(t)
            v = tk.Label(row, text="—", fg=FG, bg=BG, font=self.fb)
            v.pack(side="left", padx=(2, 10))
            self.vals[v] = None
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
        self._sync_color()
        self.after(350, self._keep)

    def _reposition(self):
        bar = taskbar_hwnd()
        if not bar or not self.hwnd:
            return
        br = rect(bar)               # coords de PANTALLA (proceso DPI-aware)
        bar_h = br.bottom - br.top
        self.update_idletasks()
        w = max(self.winfo_reqwidth(), 120)
        # se respeta el filete superior que dibuja la barra: si lo tapamos, la
        # línea del borde aparece cortada justo donde está el widget
        edge = max(1, bar_h // 36)
        h = bar_h - edge
        tn = traynotify_rect(bar)
        if tn:
            x = tn.left - w - 12     # justo a la izquierda del reloj/bandeja
        else:
            x = br.right - w - 220
        x = max(x, br.left)
        y = br.top + edge
        self._zone = (x, y, x + w, y + h)
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, x, y, w, h,
                            SWP_NOACTIVATE | SWP_SHOWWINDOW)

    # ---- fundirse con el color real de la barra ----
    def _light_bar(self):
        """True si la barra es clara (tema claro): hay que oscurecer el texto."""
        c = self._bg.lstrip("#")
        r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
        return (0.299 * r + 0.587 * g + 0.114 * b) > 140

    def _set_value(self, box, pct):
        self.vals[box] = pct
        box.config(text=f"{pct:.0f}%", fg=meter_color(pct, self._light_bar()))

    def _apply_bg(self, color):
        if color == self._bg:
            return
        was_light = self._light_bar()
        self._bg = color
        if self._light_bar() != was_light:   # el tema ha cambiado: repintar texto
            fg = "#1a1a1a" if self._light_bar() else FG
            muted = "#5c5c5c" if self._light_bar() else MUTED
            for t in self.tags:
                t.config(fg=muted)
            for box, pct in self.vals.items():
                box.config(fg=fg if pct is None else meter_color(pct, self._light_bar()))
        stack = [self]
        while stack:
            w = stack.pop()
            try:
                w.configure(bg=color)
            except tk.TclError:
                pass
            stack.extend(w.winfo_children())

    def _sync_color(self):
        # se muestrea a los lados del widget (zona vacía de la barra), nunca
        # dentro, para no leer el propio fondo que acabamos de pintar
        if self._zone and not self._hidden:
            x0, y0, x1, y1 = self._zone
            ym = (y0 + y1) // 2
            c = sample_bar_color([(x0 - 20, ym), (x0 - 44, ym), (x1 + 6, ym)])
            if c:
                self._apply_bg(c)
        self.after(2000, self._sync_color)

    def _keep(self):
        # ocultar cuando la barra deja de ser lo visible en esa zona: apps a
        # pantalla completa (pelis, juegos) y también cualquier ventana que
        # quede por encima de la barra en el z-order (juego en ventana sin
        # bordes, menú Inicio, paneles). Sin esto el widget, al ser TOPMOST,
        # se veía flotando sobre todo en vez de formar parte de la barra.
        # Usamos ShowWindow(Win32) en vez de withdraw()/deiconify() de tkinter:
        # con overrideredirect, withdraw() deja de ocultar de forma fiable tras
        # el primer deiconify(), y el widget reaparecía sobre el vídeo al volver.
        hide = is_fullscreen_active() or (
            self._zone is not None and taskbar_covered(self._zone, self.pid))
        if hide:
            if not self._hidden:
                user32.ShowWindow(self.hwnd, SW_HIDE)
                self._hidden = True
        else:
            if self._hidden:
                user32.ShowWindow(self.hwnd, SW_SHOWNA)
                self._hidden = False
            self._reposition()
        self.after(350, self._keep)

    # ---- datos ----
    def refresh(self):
        def work():
            self.cfg = {**self.cfg, **meter.load_cfg()}
            self.state.limits_refresh_sec = self.cfg.get("limits_refresh_sec", 300)
            self.state.update(self.cfg.get("count_cache_read", False))
            self.after(0, self._render)
        threading.Thread(target=work, daemon=True).start()
        self.after(self.cfg.get("refresh_sec", 60) * 1000, self.refresh)

    def _render(self):
        st = self.state
        if st.month_pct is not None:
            self._set_value(self.vm, st.month_pct)

        resets = []
        for s, box in ((st.s5h, self.v5h), (st.s7d, self.v7d)):
            if not s:
                self.vals[box] = None
                box.config(text=("!" if st.error else "…"),
                           fg="#5c5c5c" if self._light_bar() else MUTED)
                continue
            self._set_value(box, s["pct"])
        for lbl, s in (("5h", st.s5h), ("7d", st.s7d)):
            if s and s.get("reset_h"):
                resets.append(f"{lbl} {s['reset_h']}")
        if resets:
            self.menu.entryconfig(0, label="reset · " + " · ".join(resets))
        if st.weekly_limit:
            wl = st.weekly_limit
            txt = f"{wl/1e9:.1f}B" if wl >= 1e9 else f"{wl/1e6:.0f}M"
            self.menu.entryconfig(1, label=f"límite sem. ≈ {txt} tok (calibrado)")
        self._fill_history()
        self._reposition()

    def _fill_history(self):
        self.hist_menu.delete(0, "end")
        if not self.state.week_hist:
            self.hist_menu.add_command(label="(calibrando…)", state="disabled")
            return
        for h in self.state.week_hist:
            d0 = datetime.fromtimestamp(h["start"]).strftime("%d %b")
            d1 = datetime.fromtimestamp(h["end"]).strftime("%d %b")
            tag = "esta sem" if h["current"] else f"hace {h['i']}"
            self.hist_menu.add_command(
                label=f"{tag:<8} {d0}–{d1}   {h['pct']:.0f}%", state="disabled")


def meter_color(pct, light_bg=False):
    if light_bg:   # tonos más oscuros para que contrasten sobre barra clara
        return "#1e7a4d" if pct < 70 else ("#8a5a00" if pct < 90 else "#b3241d")
    return "#4caf7d" if pct < 70 else ("#e0a63a" if pct < 90 else "#e05a54")


if __name__ == "__main__":
    Bar().mainloop()
