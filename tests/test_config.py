"""Tests for config.py — flat shape (no poll: wrapper), validators, keyring."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from mt5_pnl_exporter.config import (
    AccountConfig,
    Config,
    check_file_perms,
    load_config,
    resolve_passwords,
)


def _write_cfg(path: Path, body: str) -> None:
    path.write_text(body)


# ─── flat shape ──────────────────────────────────────────────────────────────


def test_terminal_path_is_top_level(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    _write_cfg(
        cfg_path,
        "snapshot_path: /tmp/s.json\n"
        "terminal_path: 'C:\\mt5\\terminal64.exe'\n"
        "accounts:\n"
        "  - label: Test\n"
        "    login: 1\n"
        "    server: TestBroker\n",
    )
    cfg = load_config(cfg_path)
    assert cfg.terminal_path == "C:\\mt5\\terminal64.exe"
    assert cfg.snapshot_path == "/tmp/s.json"


def test_terminal_path_defaults_to_empty(tmp_path):
    """Omitting terminal_path is allowed; defaults to empty string."""
    cfg_path = tmp_path / "config.yaml"
    _write_cfg(
        cfg_path,
        "snapshot_path: /tmp/s.json\n"
        "accounts:\n"
        "  - label: Test\n"
        "    login: 1\n"
        "    server: TestBroker\n",
    )
    cfg = load_config(cfg_path)
    assert cfg.terminal_path == ""


# ─── validators ──────────────────────────────────────────────────────────────


def test_accounts_not_empty(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    _write_cfg(cfg_path, "snapshot_path: /tmp/s.json\naccounts: []\n")
    with pytest.raises(ValueError, match="accounts"):
        load_config(cfg_path)


def test_labels_unique(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    _write_cfg(
        cfg_path,
        "snapshot_path: /tmp/s.json\n"
        "accounts:\n"
        "  - label: Same\n"
        "    login: 1\n"
        "    server: A\n"
        "  - label: Same\n"
        "    login: 2\n"
        "    server: B\n",
    )
    with pytest.raises(ValueError, match="unique"):
        load_config(cfg_path)


def test_load_config_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match=r"config\.example\.yaml"):
        load_config(tmp_path / "nope.yaml")


# ─── perms ───────────────────────────────────────────────────────────────────


@pytest.mark.skipif(os.name == "nt", reason="POSIX perms only")
def test_check_file_perms_warns_on_world_readable(tmp_path, capsys):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("x: 1\n")
    os.chmod(cfg_path, 0o644)
    check_file_perms(cfg_path)
    captured = capsys.readouterr()
    assert "chmod 600" in captured.err


@pytest.mark.skipif(os.name == "nt", reason="POSIX perms only")
def test_check_file_perms_silent_on_600(tmp_path, capsys):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("x: 1\n")
    os.chmod(cfg_path, 0o600)
    check_file_perms(cfg_path)
    captured = capsys.readouterr()
    assert captured.err == ""


# ─── resolve_passwords ───────────────────────────────────────────────────────


def test_resolve_passwords_pulls_from_keyring():
    cfg = Config(
        snapshot_path="/tmp/s.json",
        terminal_path="",
        accounts=[
            AccountConfig(label="A", login=1, server="X"),
            AccountConfig(label="B", login=2, server="Y"),
        ],
    )
    with patch("mt5_pnl_exporter.config.get_investor_password") as gp:
        gp.side_effect = lambda login: f"pw-{login}"
        result = resolve_passwords(cfg)
    assert result == {1: "pw-1", 2: "pw-2"}


def test_resolve_passwords_raises_when_missing():
    cfg = Config(
        snapshot_path="/tmp/s.json",
        terminal_path="",
        accounts=[AccountConfig(label="A", login=1, server="X")],
    )
    with (
        patch("mt5_pnl_exporter.config.get_investor_password", return_value=None),
        pytest.raises(RuntimeError, match="set-password"),
    ):
        resolve_passwords(cfg)
