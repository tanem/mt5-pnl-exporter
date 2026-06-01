"""Tests for secrets.py — redaction filter."""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from mt5_pnl_exporter.secrets import (
    _RedactFilter,
    get_encryption_passphrase,
    get_investor_password,
    set_encryption_passphrase,
    set_investor_password,
)


def _make_logger(name: str = "test") -> tuple[logging.Logger, list[logging.LogRecord]]:
    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)
    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _Capture()
    log.addHandler(handler)
    return log, records


def test_redact_filter_replaces_secret(caplog):
    filt = _RedactFilter()
    filt.register("s3cr3t")

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="password is s3cr3t",
        args=(),
        exc_info=None,
    )
    filt.filter(record)
    assert record.getMessage() == "password is ***"


def test_redact_filter_does_not_corrupt_percent_formatting():
    """After a secret is registered, log.info("count=%d", n) must not raise."""
    filt = _RedactFilter()
    filt.register("s3cr3t")

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="count=%d",
        args=(42,),
        exc_info=None,
    )
    # Must not raise TypeError
    filt.filter(record)
    assert record.getMessage() == "count=42"


def test_redact_filter_no_secrets_leaves_args_intact():
    """With no registered secrets, args are not touched."""
    filt = _RedactFilter()

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="count=%d",
        args=(7,),
        exc_info=None,
    )
    filt.filter(record)
    assert record.getMessage() == "count=7"


def test_get_investor_password_delegates_to_keyring():
    with patch("mt5_pnl_exporter.secrets.keyring.get_password", return_value="pw123") as mock_get:
        result = get_investor_password(12345)
    mock_get.assert_called_once_with("mt5-pnl-exporter", "12345")
    assert result == "pw123"


def test_set_investor_password_delegates_to_keyring():
    with patch("mt5_pnl_exporter.secrets.keyring.set_password") as mock_set:
        set_investor_password(12345, "pw123")
    mock_set.assert_called_once_with("mt5-pnl-exporter", "12345", "pw123")


def test_redact_filter_empty_secret_not_registered():
    """register('') should not add an empty pattern that matches everything."""
    filt = _RedactFilter()
    filt.register("")

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="hello world",
        args=(),
        exc_info=None,
    )
    filt.filter(record)
    assert record.getMessage() == "hello world"


def test_get_encryption_passphrase_delegates_to_keyring():
    with patch("mt5_pnl_exporter.secrets.keyring.get_password", return_value="hunter2") as mock_get:
        result = get_encryption_passphrase()
    mock_get.assert_called_once_with("mt5-pnl-exporter", "encryption-passphrase")
    assert result == "hunter2"


def test_get_encryption_passphrase_returns_none_when_unset():
    with patch("mt5_pnl_exporter.secrets.keyring.get_password", return_value=None):
        assert get_encryption_passphrase() is None


def test_set_encryption_passphrase_delegates_to_keyring():
    with patch("mt5_pnl_exporter.secrets.keyring.set_password") as mock_set:
        set_encryption_passphrase("hunter2")
    mock_set.assert_called_once_with("mt5-pnl-exporter", "encryption-passphrase", "hunter2")


def test_set_investor_password_rejects_empty():
    """Empty password is rejected at the library boundary, before keyring is touched."""
    with (
        patch("mt5_pnl_exporter.secrets.keyring.set_password") as mock_set,
        pytest.raises(ValueError, match="password cannot be empty"),
    ):
        set_investor_password(12345, "")
    mock_set.assert_not_called()


def test_set_encryption_passphrase_rejects_empty():
    """Empty passphrase is rejected at the library boundary, before keyring is touched."""
    with (
        patch("mt5_pnl_exporter.secrets.keyring.set_password") as mock_set,
        pytest.raises(ValueError, match="passphrase cannot be empty"),
    ):
        set_encryption_passphrase("")
    mock_set.assert_not_called()


def test_scrub_returns_input_unchanged_with_no_secrets():
    """No registered secrets → scrub is a no-op."""
    filt = _RedactFilter()
    assert filt.scrub("hello world") == "hello world"


def test_scrub_replaces_single_registered_secret():
    filt = _RedactFilter()
    filt.register("pw123")
    assert filt.scrub("hello pw123 world") == "hello *** world"


def test_scrub_handles_multiple_registered_secrets():
    filt = _RedactFilter()
    filt.register("pw123")
    filt.register("alpha")
    assert filt.scrub("alpha and pw123") == "*** and ***"
