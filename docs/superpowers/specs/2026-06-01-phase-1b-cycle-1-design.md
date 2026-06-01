# Phase 1b cycle 1: snapshot redesign and cascades

Status: design. Approved 2026-06-01, ready to plan implementation.

Refines cycle 1 of [`2026-06-01-phase-1b-design.md`](2026-06-01-phase-1b-design.md)
(items 1–5). Settles the open questions that parent left for this cycle's
own brainstorm: exact field lists, enum encoding, currency handling, fixture
move shape.

## Why

The ported snapshot pre-aggregates closing deals into `DailyRow`, discarding
most of what MT5 emits and baking in a day-grouping assumption the exporter
has no business making. This cycle replaces aggregation with raw capture:
closed deals, open positions, cash flows — every field MT5 returns,
integers kept as integers. Consumers slice.

Side cascades land in the same cycle so the codebase stays consistent: drop
`aggregate.py`, drop runtime `FixtureSource`, flatten the now-redundant
`poll:` config section, repivot tests around snapshot + sources.

## Schema

`SCHEMA_VERSION` bumps from `1` to `2`. Still a plain integer; the
major.minor `"1.0"` stamp is cycle 4.

```
Snapshot
├── schema_version: int = 2
├── generated_at: ISO-8601 UTC string ("...Z")
├── accounts: list[AccountSnapshot]
├── closed_deals: list[ClosedDeal]
├── open_positions: list[OpenPosition]
└── cash_flows: list[CashFlow]
```

All pydantic models stay `frozen=True, extra="forbid"`. JSON Schema
regenerated via the existing `mt5-pnl-exporter schema` command;
`tests/test_schema_file.py` continues to catch drift.

### AccountSnapshot

Unchanged from today:

```
login: int
label: str
currency: str          # account's native deposit currency
balance: float
equity: float
last_success: str | None
last_error: str | None
```

No aggregate fields (win/loss/profit-factor were never on it). Currency is
recorded per account in its native deposit currency — the exporter does no
FX conversion. Consumers convert if they need a common base.

### ClosedDeal

Every field MT5's `TradeDeal` emits, plus `account` (the login, which MT5
doesn't carry on the record itself):

```
account: int           # we add this
ticket: int
order: int
position_id: int
time: int              # close time, Unix seconds
time_msc: int          # close time, Unix milliseconds
type: int              # mt5 DEAL_TYPE_*  (raw integer)
entry: int             # mt5 DEAL_ENTRY_* (raw integer)
reason: int            # mt5 DEAL_REASON_*
magic: int
volume: float
price: float
profit: float
swap: float
commission: float
fee: float
symbol: str
comment: str
external_id: str
```

Filter rule (unchanged): only `DEAL_ENTRY_OUT` / `DEAL_ENTRY_INOUT` and
non-`DEAL_TYPE_BALANCE` records land here.

Enum-ish fields (`type`, `entry`, `reason`) are kept as raw MT5 integers.
Translating to string enums would require the exporter to maintain a
mapping table and bump the schema whenever MT5 adds a value — overhead for
no real win. Consumers carry the small lookup themselves.

### OpenPosition

Every field MT5's `TradePosition` emits, plus `account`:

```
account: int           # we add this
ticket: int
identifier: int
time: int              # open time, Unix seconds
time_msc: int
time_update: int       # last update time, Unix seconds
time_update_msc: int
type: int              # mt5 POSITION_TYPE_*
reason: int            # mt5 POSITION_REASON_*
magic: int
volume: float
price_open: float
price_current: float
sl: float
tp: float
profit: float
swap: float
symbol: str
comment: str
external_id: str
```

Both `time` and `time_update` are kept — they answer different questions
("how long has this position been open?" vs "when did MT5 last touch it?")
and the raw philosophy says don't choose for the consumer.

### CashFlow

Same MT5 deal struct as `ClosedDeal`, but for balance-family records
(`DEAL_TYPE_BALANCE` and related: credit, charge, correction, bonus,
commission). Field set is identical to `ClosedDeal` — cash flows ARE deals;
the difference is the filter, not the shape. Fields that don't apply to
balance records (volume, price, symbol, entry, position_id) come through
as 0 or empty string from MT5 and are kept as-is.

## DataSource protocol and MT5Source

Protocol grows to three fetchers:

```python
class DataSource(Protocol):
    def account_info(self, login: int) -> AccountInfo: ...
    def fetch_closed_deals(self, login: int, date_from: int, date_to: int) -> list[ClosedDeal]: ...
    def fetch_open_positions(self, login: int) -> list[OpenPosition]: ...
    def fetch_cash_flows(self, login: int, date_from: int, date_to: int) -> list[CashFlow]: ...
```

The skinny `Deal` model in `sources/base.py` is removed; the protocol
returns the new snapshot models directly.

**MT5Source implementation.**

- `fetch_closed_deals`: same async-history-sync `_wait_history_synced`
  dance as today. Filter rule unchanged. For each surviving `TradeDeal`,
  copy every field 1:1; set `account=login`.
- `fetch_cash_flows`: hits `history_deals_get` over the same window.
  Keeps balance-family records (`DEAL_TYPE_BALANCE` and friends). Field
  copy 1:1; `account=login`.
- `fetch_open_positions`: calls `mt5.positions_get()`. No history sync
  needed — positions are live state. Field copy 1:1; `account=login`.

**`history_deals_get` cache.** Closed deals and cash flows both come from
the same `history_deals_get` call. `MT5Source` memoises the most recent
call's result keyed by `(login, date_from, date_to)` for the duration of
the instance — so `poll`'s back-to-back calls hit MT5 once. Cache is
cleared on `shutdown()`.

**Constants.** `DEAL_TYPE_BALANCE`, `DEAL_ENTRY_OUT`, `DEAL_ENTRY_INOUT`
stay in `sources/base.py`. Add the balance-family deal-type constants
needed for cash-flow classification (credit, charge, correction, bonus,
commission).

## Cascades

### Deletes

- `aggregate.py` — no caller in the new model.
- `sources/fixture.py` — runtime source-selection is gone.
- `--source` flag on `poll` — only one source remains.
- `sources/base.py::Deal` — replaced by the snapshot models.
- `tests/test_aggregate.py` — replaced by the new tests below.
- `tests/fixtures/sample_deals.json` — replaced by `sample_snapshot.json`.

### Config flatten

```yaml
snapshot_path: ...
terminal_path: ...
accounts:
  - label: ...
    login: ...
    server: ...
```

`PollConfig` deleted. `Config` gains `terminal_path: str = ""` at the top
level. No migration shim; pydantic's `extra="forbid"` rejects any stray
`poll:` key on its own.

### `poll` rewrite (sketch)

```python
info       = src.account_info(acct.login)
deals      = src.fetch_closed_deals(acct.login, epoch_from, epoch_to)
flows      = src.fetch_cash_flows(acct.login, epoch_from, epoch_to)
positions  = src.fetch_open_positions(acct.login)
```

Three accumulators (`closed_deals_out`, `cash_flows_out`,
`open_positions_out`). Build `Snapshot(schema_version=2, ...)`. The
carry-forward-on-failure semantics for `AccountSnapshot` (keep prior
`balance`/`equity`/`currency`/`last_success`, set `last_error`) are
unchanged.

### Tests

- `tests/fixtures/sample_snapshot.json` — one canonical example of the new
  schema: a couple of accounts, ~10 closed deals, 1–2 open positions,
  1–2 cash flows. Drives snapshot round-trip and CLI tests.
- `tests/test_snapshot.py` — round-trip (write → read → equality),
  schema-version mismatch rejected, malformed JSON rejected,
  atomic-write behaviour.
- `tests/test_mt5_source.py` — fake-MT5-module pattern (already in place).
  Verifies field-copy fidelity on each fetcher, the closed-vs-cash-flow
  filter split, and the `history_deals_get` cache.
- `tests/test_cli.py` — `poll` end-to-end against an in-test fake
  `DataSource`; asserts the written snapshot matches the fixture.
- `tests/test_config.py` — covers the flattened shape. No "rejects old
  shape" case.
- `tests/test_secrets.py`, `tests/test_schema_file.py` — unchanged.
- Coverage target stays at 95%.

### Docs

Light touch in this cycle: remove `--source fixture` references in
README.md and CLAUDE.md, point at the new schema fields, add a short
"snapshot size" paragraph (see below). Full reframe and threat model
land in cycle 3.

## Snapshot size

The new snapshot carries one record per closed deal instead of one per
account-day, so the file grows 50–300× for active EAs. Rough size:
~350 bytes per `ClosedDeal` record. Ten accounts with two years of
50-deals-per-day-per-account history is ~85 MB; busier EAs at
200 deals/day reach ~350 MB.

Local exporter operation handles this fine. The pain point is transport
via sync services (Dropbox, Syncthing) that re-sync the whole file on
every poll. Mitigation lives in **cycle 2**: gzip the JSON before age
encryption. JSON with repetitive field names compresses 5–10×, so a
350 MB snapshot becomes ~35 MB. Cycle 1 leaves this for cycle 2 to
settle — flagged here so it doesn't get lost.

> **Update:** implemented in cycle 2 — see [cycle 2 spec](../specs/2026-06-01-phase-1b-cycle-2-design.md).

A `history_days` truncation knob is a 1.x option if compression turns
out to be insufficient. Not in scope for this cycle.

## Out of scope (deferred to later cycles)

- **Encryption** — cycle 2.
- **gzip-before-age transport wrapper** — cycle 2.
- **Docs reframe, threat model, keychain/perms audit** — cycle 3.
- **Major.minor `SCHEMA_VERSION = "1.0"` and release** — cycle 4.
- **`history_days` truncation** — 1.x if needed.
- **Currency conversion** — never; consumer concern.
