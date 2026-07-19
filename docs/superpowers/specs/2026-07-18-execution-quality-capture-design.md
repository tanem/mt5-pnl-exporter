# Execution-quality capture: entry deals, orders, symbol metadata

Date: 2026-07-18
Status: Approved (design)

## Background

The snapshot captures close-side economics well but nothing about how a
position was *opened* or *requested*. `fetch_closed_deals` (sources/mt5.py:129)
keeps only `DEAL_ENTRY_OUT` / `INOUT` / `OUT_BY` deals; the opening deal
(`DEAL_ENTRY_IN`) is filtered out, orders are never fetched
(`history_orders_get` is uncalled), and per-symbol point size is absent.

This blocks a concrete question: on multiple live accounts running the same EA
with the same settings, execution differs between accounts. The case under
investigation is **same trades, divergent fills** — both accounts take the same
signals and both fill, but at different prices. Diagnosing that needs, per
account and per trade:

- the **actual open fill** — price and millisecond time (the entry deal);
- the **originating order** — its requested price (`price_open`), the time it
  reached the server (`time_setup_msc`), completion time (`time_done_msc`), and
  `state`;
- the **symbol point size**, to express the requested-vs-filled price gap as
  slippage in points.

All of this is available read-only over an investor login. MT5 deals carry no
"signal time"; the closest server-side proxy is the order's `time_setup_msc`
(order arrival at server = EA submission + terminal→server latency). The EA's
own internal signal timestamp lives only in the EA's logs and is out of reach
here — that latency component is itself part of what differs between accounts,
so `time_setup_msc` is useful signal, not noise.

## Goals

- Add opening-deal, order, and symbol data to the snapshot as an **additive**
  schema change: `SCHEMA_VERSION` `"1.0"` → `"1.1"`.
- Keep the snapshot's design principles: one record per MT5 deal/order (no
  pre-aggregation), raw MT5 integers for enum fields, and derived quantities
  (slippage in points, latency) left to consumers.
- Existing `closed_deals` / `open_positions` / `cash_flows` shapes and the
  full-history window stay unchanged; nothing already-captured moves or changes
  meaning.

## Non-goals

- **No `mt5-pnl-cli` change in this work.** The consumer bump is a separate
  repo and PR. Because `read()` accepts only up to its own minor
  (snapshot.py:177), a 1.1 snapshot is *rejected* by a 1.0 reader with the
  readable "not supported by this reader" error — a clean failure, not
  corruption. `export` already tolerates an unreadable prior snapshot (warns
  and regenerates), so re-running is always safe. `export` is manual and
  one-shot, so nothing breaks until the new exporter is deliberately run.
- **No derived values baked into the snapshot.** Slippage-in-points and any
  latency figure are consumer computations. The exporter stores raw price,
  raw times, and `point`; it does not choose a sign or direction convention.
- **No new time window or filtering knobs.** The window stays full history
  (epoch 0 → now), identical to deals today.
- **No `INOUT` / reversal reclassification.** Reversals stay in `closed_deals`
  where they are. `entry_deals` is strictly `DEAL_ENTRY_IN`, keeping open-fill
  pairing clean.
- **No curated/pruned order or symbol field sets** beyond what is specified
  below. Orders mirror the existing "copy the whole struct" pattern; symbols
  are deliberately minimal because the rest of `symbol_info` is runtime market
  state (bid/ask/spread) meaningless at export time.

## Design

### New data (all additive, top-level on `Snapshot`)

**1. `entry_deals: list[ClosedDeal]`.** Reuse the existing `ClosedDeal` model
unchanged — an entry deal carries the same `TradeDeal` field set. A new
`fetch_entry_deals(login, date_from, date_to)` filters the shared raw history to
non-balance-family deals with `entry == DEAL_ENTRY_IN`. One record per deal, so
partial fills naturally yield multiple entry deals for a `position_id`.
Consumers pair `entry_deals` to `closed_deals` on `position_id`.

**2. `orders: list[Order]`.** A new pydantic model mirroring MT5's `TradeOrder`
verbatim (raw integers for enum-ish fields), plus `account` (login) as the
other models do — MT5 order records don't carry it. Sourced from
`history_orders_get(from, to)` over the same window. **All** orders in the
window are emitted (every `state`, not filled-only); carrying `state` costs
nothing on the same round-trip and is the only field that would later reveal a
divergence in *which* orders filled (a different failure mode than the one under
investigation). Fields to copy from `TradeOrder`: `ticket`, `time_setup`,
`time_setup_msc`, `time_done`, `time_done_msc`, `type`, `state`,
`type_filling`, `type_time`, `magic`, `position_id`, `position_by_id`, `reason`,
`volume_initial`, `volume_current`, `price_open`, `price_current`, `price_stoplimit`,
`sl`, `tp`, `symbol`, `comment`, `external_id`. (Confirm the exact attribute set
against the installed `MetaTrader5` `TradeOrder` on the Windows host during
implementation; copy every field it exposes, consistent with `ClosedDeal`'s
"every field MT5's TradeDeal emits" docstring.)

**3. `symbols: list[SymbolInfo]`.** A new minimal model: `name`, `point`,
`digits`, `trade_contract_size`. One record per **distinct symbol** appearing in
the window's deals/orders, via `mt5.symbol_info(symbol)`. This is the raw
material for converting a price gap to points and (via contract size) to
per-lot value later. Consumers compute slippage-in-points themselves.

### Source layer (`sources/mt5.py`, `sources/base.py`)

- Add `DEAL_ENTRY_IN = 0` to `base.py` (alongside the existing `OUT` / `INOUT`
  / `OUT_BY` constants and their comment).
- Extend the `DataSource` protocol in `base.py` with `fetch_entry_deals`,
  `fetch_orders`, and `fetch_symbols` (naming/signatures matching the existing
  fetchers), and import/re-export the new `Order` / `SymbolInfo` models.
- `fetch_entry_deals` reuses `_get_history_raw` — no extra MT5 round-trip; it
  shares the memoised `history_deals_get` result with the closed/cash fetchers.
- Add an orders analogue: a memoised `history_orders_get` per
  `(login, date_from, date_to)` (parallel to `_history_cache`), fetched inside
  the same connect + `_wait_history_synced` cycle. History sync already gates
  deals; orders download on the same sync, so no new wait logic is needed —
  reuse the existing settle before the orders call.
- `fetch_symbols` collects the distinct symbol names from the window's deals and
  orders and calls `symbol_info` once per name. Guard `None` returns (unknown/
  unavailable symbol) the way other fetchers guard `None`.
- Clear the new order cache in `shutdown()` alongside `_history_cache`.

### Snapshot model + schema (`snapshot.py`, `schema/`)

- Add `Order` and `SymbolInfo` models (frozen, `extra="forbid"`, matching the
  existing models).
- Add `entry_deals`, `orders`, `symbols` to `Snapshot`.
- Bump `schema_version` `Literal` and `SCHEMA_VERSION` to `"1.1"`; `_MINOR` → 1.
  `read()`'s same-major/up-to-own-minor rule then accepts both 1.0 and 1.1.
- Regenerate `schema/snapshot.schema.json` via `mt5-pnl-exporter schema`.

### CLI (`cli.py`)

- Call the three new fetchers per account inside the existing per-account
  try/except (alongside `fetch_closed_deals` etc.), accumulate into new lists,
  and pass them to the `Snapshot(...)` construction. A per-account failure keeps
  its existing behaviour (carry-forward account row, `last_error`), and the new
  lists simply omit that account's rows for the run.
- No change to the window (`epoch_from = 0`, `epoch_to = now`), the prior-read
  resilience, or the all-fail logic.

## Testing (TDD)

- Extend the fake `MetaTrader5` module (in the `sources/mt5.py` tests) with
  `history_orders_get` and `symbol_info`, returning fake `TradeOrder` /
  `SymbolInfo`-shaped objects, mirroring how `history_deals_get` is faked today.
- `sources/mt5.py` tests: call-shape + field-copy fidelity for `fetch_orders`
  (every field copied, right types), `fetch_symbols` (distinct-symbol dedup, one
  `symbol_info` call per name, `None`-guard), and `fetch_entry_deals`
  (`DEAL_ENTRY_IN`-only filter; shares the memoised history round-trip — assert
  `history_deals_get` is not re-called).
- `snapshot.py` tests: round-trip the new lists through `write`/`read`; assert a
  1.1 snapshot round-trips and that a 1.0 snapshot still reads (back-compat).
- `test_schema_file.py` catches the regenerated schema; update the committed
  `snapshot.schema.json`.
- End-to-end CLI test: the in-test fake `DataSource` returns entry deals,
  orders, and symbols; assert they land in the written snapshot.
- Coverage gate stays 100%.

## Affected files / ripple

- `src/mt5_pnl_exporter/sources/base.py` — `DEAL_ENTRY_IN`, protocol methods,
  model re-exports.
- `src/mt5_pnl_exporter/sources/mt5.py` — three fetchers, orders cache, symbol
  collection.
- `src/mt5_pnl_exporter/snapshot.py` — `Order`, `SymbolInfo`, `Snapshot` fields,
  version bump.
- `src/mt5_pnl_exporter/cli.py` — fetch + accumulate + construct.
- `schema/snapshot.schema.json` — regenerated.
- `tests/` — fake-module extension and new coverage across the above.
- `README.md` and `CLAUDE.md` — document the new snapshot lists, the 1.1 bump,
  the `DEAL_ENTRY_IN` classification, and note the cli must be bumped to read
  1.1 (per the existing "update this file and README.md in the same change"
  convention).

## Verification

- `uv run pytest` — new tests pass; 100% coverage holds.
- `uv run ruff check src/ tests/` and `uv run mypy src/mt5_pnl_exporter` clean.
- `uv run mt5-pnl-exporter schema` produces no diff after commit
  (`test_schema_file.py` green).
- Manual narrative (Windows host, two live accounts on the same EA): run
  `export`, decrypt the snapshot, and confirm each closed deal pairs to an entry
  deal and an order by `position_id`; compute `order.price_open` −
  `entry_deal.price` over `symbol.point` per account and compare — the number
  that answers "why do these accounts fill differently".
