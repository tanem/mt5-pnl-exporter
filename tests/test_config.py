"""Tests for config loading and the POSIX perms check."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


def _write_cfg(path: Path, snapshot_path: str) -> None:
    path.write_text(
        f"snapshot_path: '{snapshot_path}'\n"
        "accounts:\n"
        "  - label: 'Test'\n"
        "    login: 1234567\n"
        "    server: 'TestBroker-Live'\n"
    )


def test_perms_check_warns_when_world_readable(tmp_path, capsys):
    cfg_path = tmp_path / "config.yaml"
    _write_cfg(cfg_path, str(tmp_path / "snapshot.json"))
    os.chmod(cfg_path, 0o644)  # group/other readable — should warn

    from mt5_pnl_exporter.config import check_file_perms

    check_file_perms(cfg_path)
    captured = capsys.readouterr()
    # Rich Console(stderr=True) writes to sys.stderr; collapse wrapping
    assert "chmod 600" in captured.err.replace("\n", " "), captured.err


def test_perms_check_silent_when_600(tmp_path, capsys):
    cfg_path = tmp_path / "config.yaml"
    _write_cfg(cfg_path, str(tmp_path / "snapshot.json"))
    os.chmod(cfg_path, 0o600)

    from mt5_pnl_exporter.config import check_file_perms

    check_file_perms(cfg_path)
    captured = capsys.readouterr()
    assert "chmod 600" not in captured.err, captured.err


def test_perms_check_skipped_on_windows(tmp_path, monkeypatch, capsys):
    # monkeypatch os.name to "nt" — safe here because cfg_path is already
    # a PosixPath and check_file_perms doesn't construct new Path objects.
    monkeypatch.setattr(os, "name", "nt")
    cfg_path = tmp_path / "config.yaml"
    _write_cfg(cfg_path, str(tmp_path / "snapshot.json"))
    # Even with world-readable bits, Windows path should NOT warn —
    # NTFS ACLs handle file security, st_mode is synthesised.
    os.chmod(cfg_path, 0o666)

    from mt5_pnl_exporter.config import check_file_perms

    check_file_perms(cfg_path)
    captured = capsys.readouterr()
    assert "chmod 600" not in captured.err, captured.err


def test_terminal_path_null_coerced_to_empty():
    from mt5_pnl_exporter.config import Config

    cfg = Config.model_validate(
        {
            "snapshot_path": "/irrelevant",
            "accounts": [{"label": "Test", "login": 1234567, "server": "TestBroker-Live"}],
            "poll": {"terminal_path": None},
        }
    )
    assert cfg.poll.terminal_path == ""


def test_poll_section_optional():
    from mt5_pnl_exporter.config import Config

    cfg = Config.model_validate(
        {
            "snapshot_path": "/irrelevant",
            "accounts": [{"label": "Test", "login": 1234567, "server": "TestBroker-Live"}],
        }
    )
    assert cfg.poll.terminal_path == ""


def test_missing_config_raises(tmp_path):
    from mt5_pnl_exporter.config import load_config

    with pytest.raises(FileNotFoundError, match="Config file not found"):
        load_config(tmp_path / "missing.yaml")


def test_duplicate_account_labels_rejected():
    from pydantic import ValidationError

    from mt5_pnl_exporter.config import Config

    with pytest.raises(ValidationError, match="labels must be unique"):
        Config.model_validate(
            {
                "snapshot_path": "/irrelevant",
                "accounts": [
                    {"label": "alpha", "login": 1, "server": "X"},
                    {"label": "alpha", "login": 2, "server": "X"},
                ],
            }
        )


def test_empty_accounts_rejected():
    from pydantic import ValidationError

    from mt5_pnl_exporter.config import Config

    with pytest.raises(ValidationError, match="accounts list must not be empty"):
        Config.model_validate(
            {
                "snapshot_path": "/irrelevant",
                "accounts": [],
            }
        )


def test_resolve_passwords_missing_raises(monkeypatch):
    import mt5_pnl_exporter.config as config_mod
    from mt5_pnl_exporter.config import Config, resolve_passwords

    monkeypatch.setattr(config_mod, "get_investor_password", lambda login: None)
    cfg = Config.model_validate(
        {
            "snapshot_path": "/irrelevant",
            "accounts": [{"label": "alpha", "login": 1, "server": "X"}],
        }
    )
    with pytest.raises(RuntimeError, match="Investor password not found in keyring"):
        resolve_passwords(cfg)


def test_resolve_passwords_returns_map(monkeypatch):
    import mt5_pnl_exporter.config as config_mod
    from mt5_pnl_exporter.config import Config, resolve_passwords

    monkeypatch.setattr(config_mod, "get_investor_password", lambda login: "secret123")
    cfg = Config.model_validate(
        {
            "snapshot_path": "/irrelevant",
            "accounts": [
                {"label": "alpha", "login": 1, "server": "X"},
                {"label": "beta", "login": 2, "server": "X"},
            ],
        }
    )
    result = resolve_passwords(cfg)
    assert result == {1: "secret123", 2: "secret123"}
