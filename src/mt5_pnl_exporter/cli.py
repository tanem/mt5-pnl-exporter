"""mt5-pnl-exporter CLI — poll | set-password | schema"""

from __future__ import annotations

import datetime
import json
import logging
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from mt5_pnl_exporter import snapshot
from mt5_pnl_exporter.config import check_file_perms, load_config, resolve_passwords
from mt5_pnl_exporter.secrets import (
    get_encryption_passphrase,
    redact_filter,
    set_encryption_passphrase,
    set_investor_password,
)
from mt5_pnl_exporter.snapshot import (
    AccountSnapshot,
    CashFlow,
    ClosedDeal,
    OpenPosition,
    Snapshot,
)
from mt5_pnl_exporter.sources.mt5 import MT5Source

app = typer.Typer(
    help="MT5 P&L exporter — poll deal history, write snapshot.json.",
    add_completion=False,
)
err = Console(stderr=True)


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler(sys.stderr)
    handler.addFilter(redact_filter)
    logging.basicConfig(level=level, handlers=[handler], format="[%(levelname)s] %(message)s")


@app.command()
def poll(
    config_path: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Fetch deal history + open positions from MT5 and write snapshot.json."""
    _setup_logging(verbose)
    log = logging.getLogger(__name__)

    check_file_perms(config_path or Path("config.yaml"))
    cfg = load_config(config_path)

    encryption_passphrase = get_encryption_passphrase()
    if not encryption_passphrase:
        err.print(
            "[red]Error: no encryption passphrase set in keychain.[/red]\n"
            "Run 'mt5-pnl-exporter set-encryption-passphrase' first."
        )
        raise SystemExit(1)
    redact_filter.register(encryption_passphrase)

    snap_path = Path(cfg.snapshot_path)
    snap_path.parent.mkdir(parents=True, exist_ok=True)

    passwords = resolve_passwords(cfg)
    servers = {a.login: a.server for a in cfg.accounts}
    src = MT5Source(cfg.terminal_path, passwords, servers)

    now = datetime.datetime.now(tz=datetime.UTC)
    epoch_from = 0
    epoch_to = int(now.timestamp())

    prior_by_login: dict[int, AccountSnapshot] = {}
    try:
        prior = snapshot.read(snap_path, encryption_passphrase)
        prior_by_login = {a.login: a for a in prior.accounts}
    except FileNotFoundError:
        pass

    accounts_out: list[AccountSnapshot] = []
    closed_deals_out: list[ClosedDeal] = []
    open_positions_out: list[OpenPosition] = []
    cash_flows_out: list[CashFlow] = []
    error_count = 0

    for acct in cfg.accounts:
        try:
            info = src.account_info(acct.login)
            deals = src.fetch_closed_deals(acct.login, epoch_from, epoch_to)
            flows = src.fetch_cash_flows(acct.login, epoch_from, epoch_to)
            positions = src.fetch_open_positions(acct.login)

            closed_deals_out.extend(deals)
            cash_flows_out.extend(flows)
            open_positions_out.extend(positions)
            accounts_out.append(
                AccountSnapshot(
                    login=acct.login,
                    label=acct.label,
                    currency=info.currency,
                    balance=info.balance,
                    equity=info.equity,
                    last_success=now.isoformat().replace("+00:00", "Z"),
                    last_error=None,
                )
            )
            log.info(
                f"[poll] {acct.label} ({acct.login}): "
                f"{len(deals)} closed deals, {len(positions)} open, "
                f"{len(flows)} cash flows  OK"
            )
        except Exception as exc:
            error_count += 1
            log.error(f"[poll] {acct.label} ({acct.login}): FAILED — {exc}")
            prior_acct = prior_by_login.get(acct.login)
            accounts_out.append(
                AccountSnapshot(
                    login=acct.login,
                    label=acct.label,
                    currency=prior_acct.currency if prior_acct else "",
                    balance=prior_acct.balance if prior_acct else 0.0,
                    equity=prior_acct.equity if prior_acct else 0.0,
                    last_success=prior_acct.last_success if prior_acct else None,
                    last_error=str(exc),
                )
            )

    try:
        if error_count == len(cfg.accounts) and prior_by_login:
            log.error(
                f"[poll] All {error_count} accounts failed; "
                f"keeping previous snapshot at {snap_path}."
            )
            raise SystemExit(1)

        snap = Snapshot(
            schema_version=2,
            generated_at=now.isoformat().replace("+00:00", "Z"),
            accounts=accounts_out,
            closed_deals=closed_deals_out,
            open_positions=open_positions_out,
            cash_flows=cash_flows_out,
        )
        snapshot.write(snap_path, snap, encryption_passphrase)
        log.info(f"[poll] wrote {snap_path}  ({now.strftime('%Y-%m-%d %H:%M')})")
    finally:
        src.shutdown()

    if error_count:
        raise SystemExit(1)


@app.command("set-password")
def set_password(
    login: Annotated[int, typer.Argument(help="MT5 account login number")],
) -> None:
    """Store an investor password in the OS keychain (never echoed to terminal)."""
    import getpass

    pw = getpass.getpass(f"Investor password for login {login}: ")
    if not pw:
        err.print("[red]Password cannot be empty.[/red]")
        raise SystemExit(1)
    set_investor_password(login, pw)
    err.print(f"[green]Password stored in keychain for login {login}.[/green]")


@app.command("set-encryption-passphrase")
def set_encryption_passphrase_cmd() -> None:
    """Store the snapshot encryption passphrase in the OS keychain (entered twice)."""
    import getpass

    pw = getpass.getpass("Encryption passphrase: ")
    if not pw:
        err.print("[red]Passphrase cannot be empty.[/red]")
        raise SystemExit(1)
    confirm = getpass.getpass("Confirm passphrase: ")
    if pw != confirm:
        err.print("[red]Passphrases do not match.[/red]")
        raise SystemExit(1)
    set_encryption_passphrase(pw)
    err.print("[green]Encryption passphrase stored in keychain.[/green]")


@app.command()
def schema(
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Where to write the JSON Schema file.")
    ] = Path("schema/snapshot.schema.json"),
) -> None:
    """Regenerate the JSON Schema for snapshot.json from the pydantic models."""
    schema_dict = Snapshot.model_json_schema()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(schema_dict, indent=2) + "\n")
    err.print(f"[green]Wrote {output}[/green]")
