"""FixtureSource — loads sample deals from a JSON file. No MT5 or creds needed."""

from __future__ import annotations

import json
from pathlib import Path

from mt5_pnl_exporter.sources.base import AccountInfo, Deal

_DEFAULT_FIXTURE = (
    Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "sample_deals.json"
)

_FIXTURE_ACCOUNTS: dict[int, AccountInfo] = {
    1234567: AccountInfo(
        login=1234567, label="Trend EA", currency="USD", balance=10240.50, equity=10198.20
    ),
    7654321: AccountInfo(
        login=7654321, label="Scalper EA", currency="USD", balance=8910.00, equity=8874.50
    ),
}


class FixtureSource:
    def __init__(self, fixture_path: Path | None = None) -> None:
        path = fixture_path or _DEFAULT_FIXTURE
        raw = json.loads(path.read_text())
        self._deals = [Deal.model_validate(d) for d in raw]

    def fetch_deals(self, login: int, date_from: int, date_to: int) -> list[Deal]:
        return [d for d in self._deals if d.account == login and date_from <= d.time < date_to]

    def account_info(self, login: int) -> AccountInfo:
        if login not in _FIXTURE_ACCOUNTS:
            raise ValueError(f"No fixture account for login {login}")
        return _FIXTURE_ACCOUNTS[login]
