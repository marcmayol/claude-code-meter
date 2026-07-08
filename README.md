<!-- Language selector -->
**English** · [Español](https://github.com/marcmayol/claude-code-meter/blob/main/README.es.md)

# Claude Code Meter

A **[Claude Code](https://claude.com/claude-code) token-usage meter** for Windows.
It reads Claude Code's local session logs and shows how much you've spent
**today / this week / this month**, compared against a target you set yourself.

![Claude Code Meter embedded in the Windows taskbar](https://raw.githubusercontent.com/marcmayol/claude-code-meter/main/assets/screenshot.png)

> The figures (`D`ay · `W`eek · `M`onth) live inside the taskbar, next to the
> clock. Each percentage is colored by level: 🟢 < 70 % · 🟡 < 90 % · 🔴 ≥ 90 %.
> On a Spanish Windows the labels show as `D` · `S` · `M` (Día/Semana/Mes).

It ships **three presentations of the same meter**. You pick **one** (they don't
run at the same time — they show the same data in different ways):

| Style   | What it is | Looks like |
|---------|------------|------------|
| **bar** (`bar.py`)   | Figures **inside the taskbar**, next to the clock | `✳ D 77% · W 62% · M 63%` |
| **tray** (`tray.py`) | **System-tray icon** with the value drawn on it and the detail in the tooltip | `63%` |
| **panel** (`meter.py`) | **Floating panel** in the corner, with progress bars | box with TODAY/WEEK/MONTH |

`D` = today · `W` = week · `M` = month, each as a **% of its target**.
Colors update on their own: 🟢 < 70 % · 🟡 < 90 % · 🔴 ≥ 90 %.

---

## ⚠️ What it measures (and what it doesn't)

- ✅ Only the usage of **Claude Code running on this computer**, reading
  `~/.claude/projects/**/*.jsonl`.
- ❌ It does **not** measure Claude on the web/app, the API, or other computers.
- ❌ It is **not** your real subscription limit: that number lives on Anthropic's
  servers and isn't stored locally (you only see it with `/usage` inside Claude Code).

That's why "what's left" is computed against a **personal target** you define,
not against the plan's limit.

By default it **does not count cache reads** (`cache_read`), which would inflate
the numbers ~100× as the context is resent. It measures real work:
`input + output + cache_write`.

---

## Requirements

- Windows 10/11
- Python 3.9+ (with `tkinter`, included in the official Python installer)

## Install

### Option A — Download the `.exe` (no Python needed)

Download the latest
**[`claude-code-meter.exe`](https://github.com/marcmayol/claude-code-meter/releases/latest/download/claude-code-meter.exe)**
from the [Releases](https://github.com/marcmayol/claude-code-meter/releases) page
and double-click it. It shows up in the taskbar right away. To launch a different
style, run it from a terminal: `claude-code-meter.exe tray` (or `panel`).

### Option B — pip (needs Python 3.9+)

```bash
pip install claude-code-meter
```

Adds the `claude-code-meter` command and pulls in the dependencies (Pillow,
pystray). Config and the generated logo live in `%APPDATA%\ClaudeCodeMeter`.

<sub>Or from source: `git clone … && cd claude-code-meter && pip install -e .`</sub>

## Usage

Pick **one** style. With the `.exe`, just double-click it (that's the `bar`
style) or run `claude-code-meter.exe tray|panel`. If you installed with pip:

```bash
claude-code-meter          # taskbar (default, recommended)
claude-code-meter tray     # system-tray icon
claude-code-meter panel    # floating panel in the corner
```

(Equivalent: `python -m claude_code_meter.main [bar|tray|panel]`.)

### Adjusting the targets

Right-click on the figures → **Adjust target** (opens `config.json`), or create
your own `config.json` from `config.example.json`:

```json
{
  "daily_budget": null,          // daily target; null = weekly / 7
  "weekly_budget": 10000000,     // tokens/week
  "monthly_budget": 60000000,    // tokens/month
  "count_cache_read": false,     // true = include cache reads
  "refresh_sec": 60
}
```

### Auto-start (Windows)

To start it on boot, put a shortcut in the Startup folder (`Win+R` →
`shell:startup`):

- **Downloaded `.exe`:** point the shortcut straight to `claude-code-meter.exe`.
- **pip install:** point it to the installed command with `bar` as argument:
  ```
  Target:    …\Scripts\claude-code-meter.exe
  Arguments: bar
  ```

Both run without a console window. The repo also ships `Iniciar Meter.vbs`,
which runs `pythonw -m claude_code_meter.main bar`.

## How the bar version works

Windows 11 repaints the taskbar on top of windows inserted with `SetParent`, so
`bar.py` uses a **topmost** window placed by screen coordinates just left of the
clock (`TrayNotifyWnd`) and re-raised every 0.7 s. Same idea as
TrafficMonitor / XMeters.

## License

MIT — see [`LICENSE`](LICENSE).
