<!-- Selector de idioma -->
[English](https://github.com/marcmayol/claude-code-meter/blob/main/README.md) · **Español**

# Claude Code Meter

Un medidor de **consumo de [Claude Code](https://claude.com/claude-code)** para
Windows que muestra tus **límites reales del plan** —los mismos números que ves
en `/usage`— dentro de la barra de tareas, junto al reloj:

- **`5h`** — % usado de tu ventana de **sesión** (el límite móvil de 5 horas)
- **`7d`** — % usado de tu ventana **semanal** (se reinicia solo)
- **`M`** — tu **consumo del mes**, en la misma escala de tu plan (auto-calibrado)

![Claude Code Meter integrado en la barra de tareas de Windows](https://raw.githubusercontent.com/marcmayol/claude-code-meter/main/assets/screenshot.png)

> Cada porcentaje se colorea según su nivel: 🟢 < 70 % · 🟡 < 90 % · 🔴 ≥ 90 %.
> Clic derecho para ver los tiempos de reinicio, el límite semanal calibrado y un
> **historial semanal** de las semanas anteriores.

---

## Cómo obtiene tus límites *reales*

Los porcentajes de `/usage` no se guardan en disco: llegan en los **headers de
rate-limit** de la API en cada respuesta. El medidor hace una petición mínima
(`max_tokens: 1`, ~1 token) cada pocos minutos usando el token OAuth que Claude
Code guarda en `~/.claude/.credentials.json`, y lee:

```
anthropic-ratelimit-unified-5h-utilization   → ventana de sesión (5 h)
anthropic-ratelimit-unified-7d-utilization   → ventana semanal (7 días)
anthropic-ratelimit-unified-…-reset          → marcas de reinicio automático
```

El valor `7d` coincide exactamente con tu pantalla de `/usage`.

### La cifra mensual (auto-calibrada)

Tu plan **no tiene cuota mensual**: solo las ventanas de 5 h y 7 d. Así que el
medidor *deduce* una vista mensual: sabiendo que tu semana actual va al `X%` y
cuántos tokens llevas en esa misma ventana (de los registros `.jsonl` locales),
calcula —por una simple regla de tres— a cuántos tokens equivale el `100%` de tu
límite semanal, y expresa el mes en esa escala. Guarda la **mejor** observación
en `calib.json` (cuanto mayor es la utilización, más fina la estimación) y la
afina con el tiempo. La misma regla de tres reconstruye el **historial de semanas
anteriores**, que el header ya no recuerda.

Un detalle clave: la ventana semanal se **ancla al reinicio real del plan** (p.ej.
viernes 23 h), no a la semana natural del calendario, de modo que los tokens que
cuenta cuadran con lo que el plan está midiendo de verdad.

---

## Qué mide (y qué no)

- ✅ Tus **límites reales del plan** (sesión + semana), desde los headers de la
  API, más una cifra mensual calibrada a partir de los registros locales
  (`~/.claude/projects/**/*.jsonl`).
- ❌ **No** mide Claude en la web/app ni en otros ordenadores (las cifras del plan
  son los límites de toda tu cuenta; el conteo mensual de tokens es solo local).
- ℹ️ El conteo local de tokens ignora la **relectura de caché** por defecto
  (dispararía las cifras x100 al reenviar el contexto); cuenta el trabajo real
  `input + output + cache_write`.

---

## Requisitos

- Windows 10/11
- Una **suscripción Claude** (Pro/Max): el medidor usa el token OAuth que Claude
  Code guarda en `~/.claude/.credentials.json`. Las configuraciones solo con API
  key no devuelven los headers de rate-limit unificado, así que los porcentajes
  del plan no aparecerán.
- Python 3.9+ (con `tkinter`, incluido en el instalador oficial de Python) — o
  simplemente el `.exe`.

## Instalación

### Opción A — Descargar el `.exe` (sin Python)

Descarga el
**[`claude-code-meter.exe`](https://github.com/marcmayol/claude-code-meter/releases/latest/download/claude-code-meter.exe)**
más reciente desde la página de [Releases](https://github.com/marcmayol/claude-code-meter/releases)
y haz doble clic. Aparece en la barra de tareas al momento.

### Opción B — pip (necesita Python 3.9+)

```bash
pip install claude-code-meter
```

Añade el comando `claude-code-meter` e instala las dependencias (Pillow, pystray).
El estado (`config.json`, `calib.json`, logo generado) se guarda en
`%APPDATA%\ClaudeCodeMeter`.

<sub>O desde el código: `git clone … && cd claude-code-meter && pip install -e .`</sub>

## Uso

```bash
claude-code-meter          # barra de tareas (por defecto, recomendado — la vista de límites reales)
claude-code-meter tray     # icono en la bandeja del sistema
claude-code-meter panel    # panel flotante en la esquina
```

(Equivalente: `python -m claude_code_meter.main [bar|tray|panel]`.)

Los tres estilos muestran los **mismos límites reales del plan** (5h · 7d · mes
calibrado): `bar` los incrusta en la barra de tareas, `tray` dibuja la métrica
que elijas como icono de bandeja (desglose completo en el tooltip) y `panel`
muestra tres barras de progreso en un panel flotante en la esquina.

### Configuración

`config.json` opcional en `%APPDATA%\ClaudeCodeMeter` (parte de
`config.example.json`):

```json
{
  "refresh_sec": 60,          // cada cuánto se recoloca / repinta la ventana
  "limits_refresh_sec": 300,  // cada cuánto consulta los límites a la API (~1 token)
  "count_cache_read": false,  // incluir relectura de caché en el conteo local
  "icon_metric": "week"       // icono de bandeja: "session" (5h) | "week" (7d) | "month"
}
```

La API se consulta como mucho cada `limits_refresh_sec` (5 min por defecto)
precisamente porque cada consulta cuesta ~1 token — el número refleja tu consumo
real, no uno inflado.

### Arranque automático (Windows)

Pon un acceso directo en la carpeta de Inicio (`Win+R` → `shell:startup`):

- **`.exe` descargado:** apunta el acceso directo directamente a `claude-code-meter.exe`.
- **pip install:** apúntalo a `…\Scripts\claude-code-meter.exe` con `bar` como
  argumento.

Ambos arrancan sin ventana de consola. El repo también incluye `Iniciar Meter.vbs`,
que ejecuta `pythonw -m claude_code_meter.main bar`.

## Cómo funciona la versión de barra

Windows 11 repinta la barra de tareas por encima de las ventanas insertadas con
`SetParent`, así que `bar.py` usa una ventana **topmost** colocada por coordenadas
de pantalla justo a la izquierda del reloj (`TrayNotifyWnd`) y re-elevada cada
0,7 s. Misma idea que TrafficMonitor / XMeters.

## Licencia

MIT — ver [`LICENSE`](LICENSE).
