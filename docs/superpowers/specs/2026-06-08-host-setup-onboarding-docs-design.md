# MT5 host-setup onboarding docs

Date: 2026-06-08
Status: Approved (design)

## Background

The README's software-install story is tight (`uv tool install`, the
quick-start command sequence, config example), but it assumes the MT5 side of
the host is already prepared and jumps straight to `set-investor-password`.
The producer-host prerequisites — stand up a dedicated MT5 terminal, log in
once manually, clear the first-run dialogs — exist only as a one-line gotcha in
`CLAUDE.md` ("a dedicated MT5 terminal is required: `mt5.login()` switches the
terminal's active account").

For a first-timer this is the friction point most likely to fail. Skipping the
first-run login leaves the open-account wizard up, which blocks
`mt5.initialize()` with a `(-10005, 'IPC timeout')` error — an opaque failure
with no breadcrumb back to the cause. Pointing the exporter at an existing EA
terminal would log that EA out and halt trading.

The original `mt5-pnl` repo documented all of this in a "Dedicated terminal
requirement" section and a Windows bootstrap block; the content was dropped
during the port. This change reintroduces it, adapted to the new repo (PyPI
install, renamed commands, mandatory encryption, manual-only v1).

## Goals

- Document the once-per-host MT5 preparation so a first-timer can follow the
  README top-to-bottom: prepare terminal → install exporter → set secrets →
  configure → export.
- Name the dedicated-terminal rationale, the first-run ritual, and the
  `-10005 IPC timeout` failure mode explicitly.
- Tell the reader where to find their `terminal_path`, `login`, and `server`
  values.
- Fix the `config.example.yaml` `terminal_path`, which currently points at the
  default MetaTrader 5 install dir — almost certainly the user's EA terminal,
  contradicting the dedicated-terminal rule.

## Non-goals

- No full PowerShell bootstrap block from the old repo. End users install via
  `uv tool install "mt5-pnl-exporter[mt5]"` from PyPI — no `git clone`, no
  `uv sync`. The only bootstrap addition is a one-line "install uv on Windows"
  pointer.
- No scheduling / Task Scheduler recipe — v1 is manual on-demand by design
  (see [`2026-06-07-cli-naming-cleanup-design.md`](2026-06-07-cli-naming-cleanup-design.md)).
- No code, schema, or behaviour change. Docs only.
- No change to the dedicated-terminal gotcha already in `CLAUDE.md` beyond
  confirming it doesn't contradict the new README wording.

## Changes

### A. New README section — "Prepare the MT5 host"

Inserted after **Install**, before **Quick start**. Added to the Contents list.

> ## Prepare the MT5 host
>
> Do this once on the Windows host, before your first export.
>
> ### A dedicated MT5 terminal
>
> The exporter needs its **own** MT5 terminal — *not* a terminal running your
> EAs. `mt5.login()` switches the connected terminal's active account, so
> pointing the exporter at an EA terminal would log your EA out and halt
> trading. A dedicated, idle terminal (no EA attached) runs alongside your EA
> terminals without touching them. The investor login and your EA's master
> login are independent, concurrent sessions.
>
> Install a second MT5 to its own path — e.g. `C:\Program Files\MT5 Exporter\`
> — separate from any EA terminal.
>
> ### First-run login
>
> Launch the dedicated terminal once, manually, log in with any of your
> investor passwords, dismiss any first-run dialogs, then close it. This saves
> the server config and clears the open-account wizard. **Skip this and
> `export` fails with `(-10005, 'IPC timeout')`** — the wizard on a fresh
> install blocks the API.
>
> ### Finding your config values
>
> - `terminal_path` — full path to the dedicated terminal's `terminal64.exe`
>   (e.g. `C:\Program Files\MT5 Exporter\terminal64.exe`).
> - `login` — the account number (the MT5 login).
> - `server` — the broker server name, shown in MT5's login dialog (e.g.
>   `BrokerName-Live`).

### B. Install section — Windows `uv` one-liner

Add above the existing `uv tool install` block:

> On a bare Windows host, install `uv` first:
> ```powershell
> powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
> ```

### C. Quick start — make the prerequisite explicit

Add a lead-in line before the existing command sequence (which is otherwise
unchanged):

> Once the [MT5 host is prepared](#prepare-the-mt5-host):

### D. config.example.yaml — fix terminal_path

Change `terminal_path: C:\Program Files\MetaTrader 5\terminal64.exe` to
`terminal_path: C:\Program Files\MT5 Exporter\terminal64.exe`, so the example
points at a dedicated terminal rather than the default install. The README
Configuration block carries a third, also-stale value
(`terminal_path: C:\mt5-poller\terminal64.exe`); align it to the same
`C:\Program Files\MT5 Exporter\terminal64.exe` so README and the example config
agree.

## Affected files / ripple

- `README.md` — new "Prepare the MT5 host" section; Contents-list entry;
  Install-section `uv` one-liner; Quick-start lead-in; Configuration-block
  `terminal_path` (currently `C:\mt5-poller\terminal64.exe`) aligned to
  `C:\Program Files\MT5 Exporter\terminal64.exe`.
- `config.example.yaml` — `terminal_path` fix.
- `CLAUDE.md` — confirm the existing dedicated-terminal gotcha doesn't
  contradict the new wording; no edit expected.

## Verification

- Anchor check: the `#prepare-the-mt5-host` link resolves to the new heading;
  the Contents entry matches.
- `grep` confirms neither stale `terminal_path` value
  (`C:\Program Files\MetaTrader 5\`, `C:\mt5-poller\`) remains in `README.md`
  or `config.example.yaml`, and that `C:\Program Files\MT5 Exporter\` is the
  single consistent value across both files.
- No tests, schema, or code touched — `uv run pytest` unaffected (docs-only).
