# mt5-pnl-exporter

Polls MT5 deal history on a Windows VPS and writes `snapshot.json`. Part of the
[mt5-pnl](https://github.com/tanem/mt5-pnl) tool family — see
[`docs/superpowers/specs/2026-05-31-repo-split-design.md`](docs/superpowers/specs/2026-05-31-repo-split-design.md)
for the contract.

## Install

```bash
uv tool install "mt5-pnl-exporter[mt5]"
```

## Commands

- `mt5-pnl-exporter poll` — fetch deals from MT5 and write `snapshot.json`.
- `mt5-pnl-exporter set-password <login>` — store an investor password in the OS keychain.
- `mt5-pnl-exporter schema` — regenerate `schema/snapshot.schema.json` from the pydantic models.

(Full docs to follow as the port lands.)
