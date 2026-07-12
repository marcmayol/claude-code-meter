# -*- coding: utf-8 -*-
"""
Consumo local por rango temporal + calibración del límite real del plan.

A diferencia de meter.Reader (que agrega por DÍA), aquí agregamos por HORA para
poder sumar exactamente la ventana que mide el plan: la semanal NO es
lunes→domingo, sino una ventana de 7 días anclada al reset (p.ej. vie 23:00).

Calibración
-----------
El plan no expone un límite en tokens, solo un % de utilización (header
`unified-7d-utilization`, redondeado a 2 decimales). Pero conocemos el consumo
local de esa misma ventana de 7 días, así que:

    límite_semanal_tokens ≈ tokens_de_la_ventana / utilización

Cuanto mayor es la utilización, menos pesa el redondeo → mejor calibración.
Guardamos la MEJOR observación (mayor util) en calib.json y la reusamos entre
reinicios y resets semanales, afinándola con el tiempo.

Solo librería estándar.
"""
import os, json, glob, calendar
from datetime import datetime


def _claude_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or \
        os.path.join(os.path.expanduser("~"), ".claude")


PROJECTS = os.path.join(_claude_dir(), "projects")
HOUR = 3600
DAY = 86400

# Solo confiamos en observaciones con señal suficiente: por debajo de este %,
# el redondeo del header a 2 decimales mete demasiado ruido en la división.
MIN_UTIL = 0.03
# Descartar calibraciones más viejas que esto (por si cambia el plan/tier).
MAX_AGE_DAYS = 45


# ---- lectura por hora, con caché por archivo -------------------------------
class HourlyReader:
    """Agrega tokens por hora (clave = epoch del inicio de la hora, UTC)."""
    def __init__(self):
        self.cache = {}   # path -> (mtime, size, {hour_epoch: {in,out,cw,cr}})

    def _parse_file(self, path):
        hourly = {}
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
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except Exception:
                        continue
                    hk = int(dt.timestamp() // HOUR * HOUR)
                    b = hourly.setdefault(hk, {"in": 0, "out": 0, "cw": 0, "cr": 0})
                    b["in"] += u.get("input_tokens", 0) or 0
                    b["out"] += u.get("output_tokens", 0) or 0
                    b["cw"] += u.get("cache_creation_input_tokens", 0) or 0
                    b["cr"] += u.get("cache_read_input_tokens", 0) or 0
        except Exception:
            pass
        return hourly

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
        for gone in set(self.cache) - set(files):
            del self.cache[gone]
        total = {}
        for _, _, hourly in self.cache.values():
            for hk, b in hourly.items():
                acc = total.setdefault(hk, {"in": 0, "out": 0, "cw": 0, "cr": 0})
                for k in ("in", "out", "cw", "cr"):
                    acc[k] += b[k]
        return total


def sum_range(hourly, start_epoch, end_epoch, count_cr=False):
    """Suma el consumo de las horas cuyo inicio cae en [start, end)."""
    tot = {"t": 0, "in": 0, "out": 0, "cw": 0, "cr": 0}
    for hk, b in hourly.items():
        if start_epoch <= hk < end_epoch:
            tot["in"] += b["in"]; tot["out"] += b["out"]
            tot["cw"] += b["cw"]; tot["cr"] += b["cr"]
    tot["t"] = tot["in"] + tot["out"] + tot["cw"] + (tot["cr"] if count_cr else 0)
    return tot


# ---- ventanas de tiempo (en epoch) ----------------------------------------
def today_start():
    now = datetime.now().astimezone()
    return now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()

def month_start():
    now = datetime.now().astimezone()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()

def days_in_month():
    now = datetime.now().astimezone()
    return calendar.monthrange(now.year, now.month)[1]

def plan_week_window(reset_epoch):
    """Ventana de 7 días que mide el plan: [reset-7d, reset]."""
    return reset_epoch - 7 * DAY, reset_epoch


def week_history(hourly, reset_epoch, weekly_limit, now_epoch, n=5, count_cr=False):
    """Reconstruye el % del plan de las últimas ``n`` ventanas semanales por
    regla de tres (tokens de la ventana / límite semanal calibrado). El header
    solo recuerda la ventana actual; las anteriores se sacan de los .jsonl.

    Devuelve lista de dicts: {"i", "start", "end", "tokens", "pct", "current"}.
    """
    out = []
    if not weekly_limit:
        return out
    for i in range(n):
        end = reset_epoch - i * 7 * DAY
        start = end - 7 * DAY
        if start > now_epoch:
            continue
        tok = sum_range(hourly, start, min(end, now_epoch), count_cr)["t"]
        out.append({
            "i": i,
            "start": start,
            "end": min(end, now_epoch),
            "tokens": tok,
            "pct": tok / weekly_limit * 100,
            "current": i == 0,
        })
    return out


# ---- calibración persistente ----------------------------------------------
def load_calib(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"best": None, "history": []}

def save_calib(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def update_calibration(path, util, window_tokens, now_epoch):
    """Registra una observación (si es fiable) y devuelve el límite semanal
    estimado en tokens, o None si aún no hay ninguna observación válida."""
    data = load_calib(path)
    best = data.get("best")

    # caducar la mejor si es demasiado vieja
    if best and now_epoch - best.get("at", 0) > MAX_AGE_DAYS * DAY:
        best = None

    if util >= MIN_UTIL and window_tokens > 0:
        obs = {"util": util, "tokens": window_tokens, "at": now_epoch}
        # nos quedamos con la de MAYOR util (menor error por redondeo)
        if not best or util > best["util"]:
            best = obs
        hist = data.get("history", [])
        hist.append(obs)
        data["history"] = hist[-200:]

    data["best"] = best
    save_calib(path, data)
    if best:
        return best["tokens"] / best["util"]   # límite semanal en tokens
    return None
