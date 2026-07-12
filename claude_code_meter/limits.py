# -*- coding: utf-8 -*-
"""
Límites reales del plan de Claude Code.

En vez de estimar el consumo desde los .jsonl locales, consultamos los mismos
datos que muestra `/usage`: los headers de rate-limit unificado que devuelve la
API en cada respuesta. Con una petición mínima (max_tokens=1) obtenemos el %
usado de cada ventana y su hora de reset:

    anthropic-ratelimit-unified-5h-utilization  ->  ventana de SESIÓN (5 horas)
    anthropic-ratelimit-unified-5h-reset        ->  timestamp Unix del reset
    anthropic-ratelimit-unified-7d-utilization  ->  ventana SEMANAL (7 días)
    anthropic-ratelimit-unified-7d-reset        ->  timestamp Unix del reset

El reset es automático: cuando la ventana se reinicia, la utilización que
devuelve el header vuelve a bajar sola.

Solo librería estándar.
"""
import os, json, time, urllib.request, urllib.error


def claude_dir():
    """Carpeta de config de Claude Code. Respeta CLAUDE_CONFIG_DIR para que
    funcione en cualquier instalación, no solo la ruta por defecto ~/.claude."""
    return os.environ.get("CLAUDE_CONFIG_DIR") or \
        os.path.join(os.path.expanduser("~"), ".claude")


CREDS = os.path.join(claude_dir(), ".credentials.json")
API_URL = "https://api.anthropic.com/v1/messages"
# Modelo barato para la sonda; consume ~1 token de salida.
PROBE_MODEL = "claude-haiku-4-5-20251001"


def _read_token():
    """Lee el accessToken OAuth. Se relee en cada llamada porque Claude Code
    lo refresca en este mismo archivo cuando caduca."""
    try:
        with open(CREDS, encoding="utf-8") as f:
            oauth = json.load(f)["claudeAiOauth"]
        return oauth.get("accessToken"), oauth.get("expiresAt")
    except Exception:
        return None, None


def fetch(timeout=30):
    """Devuelve un dict con el estado de los límites o {'error': str}.

    Estructura en caso de éxito::

        {
          "ok": True,
          "at": <epoch de la consulta>,
          "windows": {
            "5h": {"used": 0.01, "reset": 1783894800, "status": "allowed"},
            "7d": {"used": 0.06, "reset": 1784322000, "status": "allowed"},
          },
        }
    """
    token, _ = _read_token()
    if not token:
        return {"ok": False, "error": "sin credenciales"}

    body = json.dumps({
        "model": PROBE_MODEL,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "hi"}],
        "system": "You are Claude Code, Anthropic's official CLI for Claude.",
    }).encode()

    req = urllib.request.Request(API_URL, data=body, method="POST")
    req.add_header("authorization", f"Bearer {token}")
    req.add_header("anthropic-version", "2023-06-01")
    req.add_header("anthropic-beta", "oauth-2025-04-20")
    req.add_header("content-type", "application/json")

    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        hdrs = r.headers
    except urllib.error.HTTPError as e:
        # Aunque la petición sea rechazada, los headers de rate-limit suelen venir.
        hdrs = e.headers
        if not hdrs or "anthropic-ratelimit-unified-5h-utilization" not in hdrs:
            return {"ok": False, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

    def num(key, cast=float, default=None):
        v = hdrs.get(key)
        if v is None:
            return default
        try:
            return cast(v)
        except Exception:
            return default

    windows = {}
    for win in ("5h", "7d"):
        used = num(f"anthropic-ratelimit-unified-{win}-utilization")
        if used is None:
            continue
        windows[win] = {
            "used": used,  # fracción 0..1 (0.06 = 6 %)
            "reset": num(f"anthropic-ratelimit-unified-{win}-reset", int),
            "status": hdrs.get(f"anthropic-ratelimit-unified-{win}-status", ""),
        }

    if not windows:
        return {"ok": False, "error": "sin headers de límite"}

    return {"ok": True, "at": int(time.time()), "windows": windows}


def human_reset(reset_ts, now=None):
    """'1783894800' -> 'en 3h 42m' / 'en 4d 6h'. '' si no hay dato."""
    if not reset_ts:
        return ""
    now = now or time.time()
    secs = int(reset_ts - now)
    if secs <= 0:
        return "reinicio inminente"
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    if d:
        return f"en {d}d {h}h"
    if h:
        return f"en {h}h {m}m"
    return f"en {m}m"


if __name__ == "__main__":
    import pprint
    res = fetch()
    pprint.pprint(res)
    if res.get("ok"):
        for win, info in res["windows"].items():
            print(f"{win}: {info['used']*100:.0f}% usado · reset {human_reset(info['reset'])}")
