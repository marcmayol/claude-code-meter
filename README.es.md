<!-- Selector de idioma -->
[English](https://github.com/marcmayol/claude-code-meter/blob/main/README.md) · **Español**

# Claude Code Meter

Un medidor del **consumo de tokens de [Claude Code](https://claude.com/claude-code)** para Windows.
Lee los registros locales de sesiones de Claude Code y muestra cuánto llevas
gastado **hoy / esta semana / este mes**, comparado con un objetivo que pones tú.

![Claude Code Meter integrado en la barra de tareas de Windows](https://raw.githubusercontent.com/marcmayol/claude-code-meter/main/assets/screenshot.png)

> Las cifras (`D`ía · `S`emana · `M`es) viven dentro de la barra de tareas, junto al
> reloj. Cada porcentaje se colorea según su nivel: 🟢 < 70 % · 🟡 < 90 % · 🔴 ≥ 90 %.
> En Windows en inglés las etiquetas se muestran como `D` · `W` · `M`.

Incluye **tres presentaciones del mismo medidor**. Eliges **una** (no se ejecutan
a la vez: muestran los mismos datos de tres formas distintas):

| Estilo   | Qué es | Aspecto |
|----------|--------|---------|
| **barra** (`bar.py`)  | Cifras **dentro de la barra de tareas**, junto al reloj | `✳ D 77% · S 62% · M 63%` |
| **tray** (`tray.py`)  | **Icono en la bandeja del sistema** con el dato dibujado y el detalle en el tooltip | `63%` |
| **panel** (`meter.py`) | **Panel flotante** en la esquina, con barras de progreso | recuadro con HOY/SEM/MES |

`D` = hoy · `S` = semana · `M` = mes, cada uno en **% de su objetivo**.
Los colores cambian solos: 🟢 < 70 % · 🟡 < 90 % · 🔴 ≥ 90 %.

---

## ⚠️ Qué mide (y qué no)

- ✅ Solo el consumo de **Claude Code ejecutándose en este ordenador**, leyendo
  `~/.claude/projects/**/*.jsonl`.
- ❌ **No** mide Claude en la web/app, ni la API, ni otros ordenadores.
- ❌ **No** es el límite real de tu suscripción: ese dato lo controla el servidor
  de Anthropic y no se guarda en local (solo se ve con `/usage` dentro de Claude Code).

Por eso "lo que queda" se calcula contra un **objetivo personal** que defines tú,
no contra el límite del plan.

Por defecto **no cuenta la relectura de caché** (`cache_read`), que dispararía las
cifras x100 al reenviar el contexto. Mide el trabajo real: `input + output + cache_write`.

---

## Requisitos

- Windows 10/11
- Python 3.9+ (con `tkinter`, incluido en el instalador oficial de Python)

## Instalación

```bash
pip install claude-code-meter
```

Instala las dependencias (Pillow, pystray) y añade el comando `claude-code-meter`.
La configuración y el logo generado se guardan en `%APPDATA%\ClaudeCodeMeter`.

<sub>O desde el código: `git clone … && cd claude-code-meter && pip install -e .`</sub>

## Uso

Un solo comando lanza el estilo que elijas. **No hay que ejecutar varias cosas**:
escoge uno.

```bash
claude-code-meter          # barra de tareas (por defecto, recomendado)
claude-code-meter tray     # icono en la bandeja del sistema
claude-code-meter panel    # panel flotante en la esquina
```

(Equivalente: `python -m claude_code_meter.main [bar|tray|panel]`.)

### Ajustar los objetivos

Clic derecho sobre las cifras → **Ajustar objetivo** (abre `config.json`), o crea
tu `config.json` a partir de `config.example.json`:

```json
{
  "daily_budget": null,          // objetivo diario; null = semanal / 7
  "weekly_budget": 10000000,     // tokens/semana
  "monthly_budget": 60000000,    // tokens/mes
  "count_cache_read": false,     // true = incluir relectura de caché
  "refresh_sec": 60
}
```

### Arranque automático (Windows)

Para que arranque al encender, pon un acceso directo en la carpeta de Inicio
(`Win+R` → `shell:startup`) apuntando al comando instalado:

```
Destino:    …\Scripts\claude-code-meter.exe
Argumentos: bar
```

(`claude-code-meter` es un GUI script, así que arranca sin ventana de consola. El
repo también incluye `Iniciar Meter.vbs`, que ejecuta `pythonw -m claude_code_meter.main bar`.)

## Cómo funciona la versión de barra

Windows 11 repinta la barra de tareas por encima de las ventanas insertadas con
`SetParent`, así que `bar.py` usa una ventana **topmost** colocada por coordenadas
de pantalla justo a la izquierda del reloj (`TrayNotifyWnd`) y re-elevada cada
0,7 s. Misma idea que TrafficMonitor / XMeters.

## Licencia

MIT — ver [`LICENSE`](LICENSE).
