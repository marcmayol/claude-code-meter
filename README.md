<!-- Language selector -->
**English** · [Español](https://github.com/marcmayol/claude-code-meter/blob/main/README.es.md)

# Claude Code Meter

A **[Claude Code](https://claude.com/claude-code) usage meter** for Windows that
shows your **real plan limits** — the same numbers you see in `/usage` — right
inside the taskbar, next to the clock:

- **`5h`** — % used of your **session** window (the rolling 5-hour limit)
- **`7d`** — % used of your **weekly** window (resets on its own)
- **`M`** — your **month-to-date** usage, on the same scale as your plan (auto-calibrated)

![Claude Code Meter embedded in the Windows taskbar](https://raw.githubusercontent.com/marcmayol/claude-code-meter/main/assets/screenshot.png)

> Each percentage is colored by level: 🟢 < 70 % · 🟡 < 90 % · 🔴 ≥ 90 %.
> Right-click for reset times, the calibrated weekly limit, and a **weekly
> history** of previous weeks.

---

## How it gets your *real* limits

The percentages in `/usage` aren't stored on disk — they arrive in the API's
**rate-limit headers** on every response. The meter makes a tiny probe request
(`max_tokens: 1`, ~1 token) every few minutes using the OAuth token Claude Code
keeps in `~/.claude/.credentials.json`, and reads:

```
anthropic-ratelimit-unified-5h-utilization   → session window (5 h)
anthropic-ratelimit-unified-7d-utilization   → weekly window (7 days)
anthropic-ratelimit-unified-…-reset          → auto-reset timestamps
```

The `7d` value matches your `/usage` screen exactly.

### The monthly figure (auto-calibrated)

Your plan has **no monthly quota** — only the 5 h and 7 d windows. So the meter
*derives* a monthly view: knowing that your current week is at `X%` and how many
tokens you've used in that same window (from the local `.jsonl` logs), it works
out — by simple proportion — how many tokens `100%` of your weekly limit is, and
expresses the month on that scale. It saves the **best** observation to
`calib.json` (the higher the utilization, the sharper the estimate) and refines
it over time. The same rule of three reconstructs the **history of previous
weeks**, which the header no longer remembers.

Importantly, the weekly window is **anchored to the plan's real reset** (e.g.
Friday 11 pm), not the calendar week — so the tokens it counts line up with what
the plan is actually measuring.

---

## What it measures (and what it doesn't)

- ✅ Your **real plan limits** (session + weekly), from the API headers, plus a
  calibrated month-to-date figure from local logs
  (`~/.claude/projects/**/*.jsonl`).
- ❌ It does **not** track Claude on the web/app or other computers (the plan
  figures are your account-wide limits; the monthly token count is local-only).
- ℹ️ Local token counts ignore **cache reads** by default (they'd inflate the
  numbers ~100× as context is resent); it counts real work
  `input + output + cache_write`.

---

## Requirements

- Windows 10/11
- A **Claude subscription** (Pro/Max): the meter uses the OAuth token Claude Code
  stores in `~/.claude/.credentials.json`. API-key-only setups don't return the
  unified rate-limit headers, so the plan percentages won't show.
- Python 3.9+ (with `tkinter`, included in the official Python installer) — or
  just the `.exe`.

## Install

### Option A — Download the `.exe` (no Python needed)

Download the latest
**[`claude-code-meter.exe`](https://github.com/marcmayol/claude-code-meter/releases/latest/download/claude-code-meter.exe)**
from the [Releases](https://github.com/marcmayol/claude-code-meter/releases) page
and double-click it. It shows up in the taskbar right away.

### Option B — pip (needs Python 3.9+)

```bash
pip install claude-code-meter
```

Adds the `claude-code-meter` command and pulls in the dependencies (Pillow,
pystray). State (`config.json`, `calib.json`, generated logo) lives in
`%APPDATA%\ClaudeCodeMeter`.

<sub>Or from source: `git clone … && cd claude-code-meter && pip install -e .`</sub>

## Usage

```bash
claude-code-meter          # taskbar (default, recommended — the real-limits view)
claude-code-meter tray     # system-tray icon
claude-code-meter panel    # floating panel in the corner
```

(Equivalent: `python -m claude_code_meter.main [bar|tray|panel]`.)

All three styles show the **same real plan limits** (5h · 7d · calibrated month):
`bar` embeds them in the taskbar, `tray` draws one chosen metric as a tray icon
(full breakdown in the tooltip), and `panel` shows three progress bars in a
floating corner panel.

### Configuration

Optional `config.json` in `%APPDATA%\ClaudeCodeMeter` (start from
`config.example.json`):

```json
{
  "refresh_sec": 60,          // how often the window repositions / repaints
  "limits_refresh_sec": 300,  // how often it probes the API for plan limits (~1 token each)
  "count_cache_read": false,  // include cache reads in local token counts
  "icon_metric": "week"       // tray icon: "session" (5h) | "week" (7d) | "month"
}
```

The API is probed at most every `limits_refresh_sec` (default 5 min) precisely
because each probe costs ~1 token — the number reflects your real usage, not an
inflated one.

### Auto-start (Windows)

Put a shortcut in the Startup folder (`Win+R` → `shell:startup`):

- **Downloaded `.exe`:** point the shortcut straight to `claude-code-meter.exe`.
- **pip install:** point it to `…\Scripts\claude-code-meter.exe` with `bar` as
  the argument.

Both run without a console window. The repo also ships `Iniciar Meter.vbs`, which
runs `pythonw -m claude_code_meter.main bar`.

## How the bar version works

Windows 11 repaints the taskbar on top of windows inserted with `SetParent`, so
`bar.py` uses a **topmost** window placed by screen coordinates just left of the
clock (`TrayNotifyWnd`) and re-raised every 0.7 s. Same idea as
TrafficMonitor / XMeters.

## License

MIT — see [`LICENSE`](LICENSE).
