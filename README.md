# mt5-pnl-exporter

[![Licence](https://img.shields.io/github/license/tanem/mt5-pnl-exporter)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/downloads/)
[![tests](https://github.com/tanem/mt5-pnl-exporter/actions/workflows/ci.yml/badge.svg)](https://github.com/tanem/mt5-pnl-exporter/actions/workflows/ci.yml)
[![coverage](https://codecov.io/gh/tanem/mt5-pnl-exporter/branch/main/graph/badge.svg)](https://codecov.io/gh/tanem/mt5-pnl-exporter)
[![PyPI](https://img.shields.io/pypi/v/mt5-pnl-exporter)](https://pypi.org/project/mt5-pnl-exporter/)

> A stable, typed, encrypted snapshot of your MT5 deal history. Build a CLI, a dashboard, a notebook, or an AI agent on top — the snapshot is the contract.

```
   ┌──────────────┐  writes   ┌────────────────┐  reads   ┌──────────────┐
   │ mt5-pnl-     │ ────────► │ snapshot.json  │ ───────► │ mt5-pnl-cli  │
   │ exporter     │           │ .gz.age        │          │ mt5-pnl-ui   │
   │ (this repo)  │           │ (the contract) │          │ your tools   │
   └──────┬───────┘           └────────────────┘          └──────────────┘
          ▲ MT5 deal history
   ┌──────┴───────┐
   │ Windows host │
   └──────────────┘
```

Runs on the Windows host where MT5 lives, reads deal history with a read-only investor password, writes one encrypted file. No daemon, no database, no third-party service.

## Contents

- [Why](#why)
- [Install](#install)
- [Prepare the MT5 host](#prepare-the-mt5-host)
- [Quick start](#quick-start)
- [Commands](#commands)
- [Configuration](#configuration)
- [How it works](#how-it-works)
- [Schema](#schema)
- [Snapshot size](#snapshot-size)
- [Threat model](#threat-model)
- [Contributing](#contributing)
- [Licence](#licence)

## Why

- **Self-hosted.** No myfxbook, no fxblue, no third party holds your trading data. Runs on a Windows host you control.
- **Stable contract.** One typed, versioned snapshot — build whatever frontend suits you. Schema follows `major.minor`; minor bumps add optional fields, major bumps are breaking.
- **Read-only credentials.** Investor passwords can view balances and trade history but can never place or modify a trade.
- **Encrypted at rest.** Snapshot is gzipped then `age`-encrypted under a passphrase from the OS keychain. Safe to sync via Dropbox, OneDrive, or Syncthing.

## Install

On a bare Windows host, install `uv` first:

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then install the exporter:

```bash
uv tool install "mt5-pnl-exporter[mt5]"   # Windows host with MT5
uv tool install mt5-pnl-exporter          # any OS — schema command only
```

## Prepare the MT5 host

Do this once on the Windows host, before your first export.

### A dedicated MT5 terminal

The exporter needs its **own** MT5 terminal — *not* a terminal running your EAs. `mt5.login()` switches the connected terminal's active account, so pointing the exporter at an EA terminal would log your EA out and halt trading. A dedicated, idle terminal (no EA attached) runs alongside your EA terminals without touching them. The investor login and your EA's master login are independent, concurrent sessions.

Install a second MT5 to its own path — e.g. `C:\Program Files\MT5 Exporter\` — separate from any EA terminal.

### First-run login

Launch the dedicated terminal once, manually, log in with any of your investor passwords, dismiss any first-run dialogs, then close it. This saves the server config and clears the open-account wizard. **Skip this and `export` fails with `(-10005, 'IPC timeout')`** — the wizard on a fresh install blocks the API.

### Finding your config values

- `terminal_path` — full path to the dedicated terminal's `terminal64.exe` (e.g. `C:\Program Files\MT5 Exporter\terminal64.exe`).
- `login` — the account number (the MT5 login).
- `server` — the broker server name, shown in MT5's login dialog (e.g. `BrokerName-Live`).

## Quick start

Once the [MT5 host is prepared](#prepare-the-mt5-host):

```bash
$ mt5-pnl-exporter set-investor-password 1234567
Password stored in keychain for login 1234567.

$ mt5-pnl-exporter set-encryption-passphrase
Encryption passphrase stored in keychain.

$ cp config.example.yaml config.yaml && chmod 600 config.yaml
# edit config.yaml — snapshot_path, terminal_path, accounts

$ mt5-pnl-exporter export
[INFO] [export] Trend EA (1234567): 12 closed deals, 0 open, 0 cash flows  OK
[INFO] [export] Scalper EA (7654321): 8 closed deals, 1 open, 2 cash flows  OK
[INFO] [export] wrote ~/snapshots/mt5.json.gz.age  (2026-06-04 12:00)
```

After decrypt + gunzip, the snapshot looks like:

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-06-04T12:00:00Z",
  "accounts": [
    {
      "login": 1234567,
      "label": "Trend EA",
      "currency": "USD",
      "balance": 10240.50,
      "equity": 10198.20,
      "last_success_at": "2026-06-04T12:00:00Z",
      "last_error": null
    }
  ],
  "closed_deals": [
    {
      "account": 1234567,
      "ticket": 9876543,
      "time": 1748867482,
      "symbol": "EURUSD",
      "type": 0,
      "entry": 1,
      "volume": 0.10,
      "price": 1.0834,
      "profit": 12.40,
      "swap": 0.0,
      "commission": -0.70,
      "fee": 0.0
    }
  ],
  "open_positions": [],
  "cash_flows": []
}
```

`ClosedDeal` and `OpenPosition` carry every field MT5 emits — raw `type` and `entry` integers, `time` as Unix seconds, etc. See [`schema/snapshot.schema.json`](schema/snapshot.schema.json) for the full shape.

## Commands

- `mt5-pnl-exporter export` — fetch deals from MT5 once and write `snapshot.json.gz.age` atomically.
- `mt5-pnl-exporter set-investor-password <login>` — store an investor password in the OS keychain (`keyring`).
- `mt5-pnl-exporter set-encryption-passphrase` — store the snapshot encryption passphrase in the OS keychain (entered twice).
- `mt5-pnl-exporter schema` — regenerate `schema/snapshot.schema.json` from the pydantic `Snapshot` model.

## Configuration

Copy `config.example.yaml` to `config.yaml` (gitignored) and fill in your values:

```yaml
snapshot_path: ~/snapshots/mt5.json.gz.age
terminal_path: C:\mt5-poller\terminal64.exe
accounts:
  - label: Trend EA
    login: 1234567
    server: BrokerName-Live
  - label: Scalper EA
    login: 7654321
    server: BrokerName-Live
```

On Unix hosts, run `chmod 600 config.yaml` — `export` warns when the file is group- or world-readable. Investor passwords and the encryption passphrase go in the OS keychain via `set-investor-password` and `set-encryption-passphrase`, never in this file.

## How it works

```
deals (live)    ──► Snapshot    ──► gzip      ──► age encrypt ──► snapshot.json.gz.age
MT5 terminal       pydantic         (~10× smaller)  passphrase     (atomic .tmp swap)
                   models                            from keychain
```

`export` logs into each account with its investor password, reads closed deals, open positions, and balance-family deals via the `MetaTrader5` Python API, then assembles them into a typed `Snapshot`. The full history is rebuilt each run — idempotent, so a missed run auto-backfills on the next run.

Gzip + `age` encryption is mandatory, not optional. The on-disk file is always `snapshot.json.gz.age`; readers must reverse the pipeline (`age decrypt → gunzip → json.loads`) to decrypt. Sync services (Dropbox, OneDrive, Syncthing) and backups only ever see ciphertext.

## Schema

`schema/snapshot.schema.json` is generated from the pydantic models and committed. CI (`tests/test_schema_file.py`) fails if it drifts. The on-disk file is the schema's JSON gzipped then encrypted with [age](https://age-encryption.org/) under a passphrase from the OS keychain — consumers must reverse the same pipeline to read it.

The snapshot carries one record per closed deal (`ClosedDeal`), open position (`OpenPosition`), and balance-family deal — deposit, withdrawal, credit, charge, correction, bonus, commission (`CashFlow`). Plus one `AccountSnapshot` per account with balance, equity, currency, and the last-success/last-error stamps. No pre-aggregation — consumers slice the raw records however they want.

Schema version stamping is `major.minor` (`SCHEMA_VERSION = "1.0"`). Readers accept the same major and any minor ≤ their own; minor bumps add optional fields, major bumps are breaking. Consumers vendor `schema/snapshot.schema.json` from a specific release.

## Snapshot size

The snapshot stores one record per closed deal, so it grows with trading volume. Rough sizing: ~350 bytes per closed-deal record. Ten accounts with two years of 50-deals-per-day-per-account history (~250 trading days/year) is around 90 MB; busier setups (200 deals/day) reach ~350 MB. Each `export` gzips the JSON before encrypting, so the on-disk file is roughly an order of magnitude smaller — the 350 MB worst case lands at ~35 MB on disk, which is what sync services (Dropbox, Syncthing) see.

## Threat model

The OS user account on the Windows host that runs the exporter is the trust boundary. Anyone with that account's session can read the keychain, run `export`, and read decrypted snapshots. The same applies to a consumer machine: anyone with that account's session can decrypt the snapshot. The exporter does not defend against a compromised user session on either side.

### What's protected

- **Snapshot contents at rest off the Windows host.** Sync services (Dropbox, OneDrive, Syncthing), backups, and transit only ever see the gzipped, age-encrypted file. Mandatory encryption is what gets you this.
- **Investor passwords and the encryption passphrase, on disk and in logs.** Stored only in the OS keychain. The `redact_filter` strips any registered secret from log lines.

### What's not protected

- **A compromised user session on either host.** With keychain access the snapshot decrypts to plaintext.
- **Traffic-analysis metadata.** File size, sync timing, and whether an export ran today are visible to anyone observing the transport. age hides contents, not existence.
- **Passphrase loss.** There is no recovery. The snapshot is reproducible, though — re-run `export` to rebuild it from the broker's history.
- **The broker side.** MT5 deal history lives on the broker's server and is governed by their controls, not by anything in this tool.

### Transport guidance

The file is encrypted at rest, so transport choice is a workflow decision, not a security one. scp/rsync over SSH, a synced folder (Dropbox/Syncthing/OneDrive), or reading on the same machine are all viable. Pick whichever fits.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). For security reports, see [SECURITY.md](SECURITY.md).

## Licence

MIT — see [LICENSE](LICENSE).
