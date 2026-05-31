"""Config loading: pydantic models, keyring-first secret resolution."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from mt5_pnl_exporter.secrets import get_investor_password, redact_filter

_DEFAULT_CONFIG_PATH = Path("config.yaml")


class AccountConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    login: int
    server: str


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    snapshot_path: str
    terminal_path: str = ""
    accounts: list[AccountConfig]

    @field_validator("terminal_path", mode="before")
    @classmethod
    def _terminal_path_none_to_empty(cls, v: Any) -> str:
        return v or ""

    @field_validator("accounts")
    @classmethod
    def accounts_not_empty(cls, v: list[AccountConfig]) -> list[AccountConfig]:
        if not v:
            raise ValueError("accounts list must not be empty")
        return v

    @model_validator(mode="after")
    def _labels_unique(self) -> Config:
        labels = [a.label for a in self.accounts]
        if len(set(labels)) != len(labels):
            raise ValueError("account labels must be unique")
        return self


def check_file_perms(path: Path) -> None:
    """Warn if config has group/other-readable bits. Only call from poll."""
    if os.name == "nt":
        return
    mode = path.stat().st_mode & 0o777
    if mode & 0o077:
        from rich.console import Console

        Console(stderr=True).print(
            f"[yellow]Warning: {path} has permissions {oct(mode)} — should be 600. "
            "Run: chmod 600 config.yaml[/yellow]"
        )


def load_config(config_path: Path | None = None) -> Config:
    path = config_path or _DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}\n"
            "Copy config.example.yaml to config.yaml and fill in your values."
        )
    with path.open() as f:
        raw: dict[str, Any] = yaml.safe_load(f)
    return Config.model_validate(raw)


def resolve_passwords(cfg: Config) -> dict[int, str]:
    """Return {login: investor_password} from keyring; raise if any missing."""
    passwords: dict[int, str] = {}
    missing: list[str] = []
    for acct in cfg.accounts:
        pw = get_investor_password(acct.login)
        if not pw:
            missing.append(f"{acct.label} (login {acct.login})")
        else:
            redact_filter.register(pw)
            passwords[acct.login] = pw
    if missing:
        raise RuntimeError(
            "Investor password not found in keyring for: "
            + ", ".join(missing)
            + "\nRun: mt5-pnl-exporter set-password <login>"
        )
    return passwords
