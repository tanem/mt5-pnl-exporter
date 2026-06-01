"""Keyring-based secret access and log redaction."""

from __future__ import annotations

import logging
import re

import keyring

KEYRING_SERVICE = "mt5-pnl-exporter"


def get_investor_password(login: int) -> str | None:
    return keyring.get_password(KEYRING_SERVICE, str(login))


def set_investor_password(login: int, password: str) -> None:
    if not password:
        raise ValueError("password cannot be empty")
    keyring.set_password(KEYRING_SERVICE, str(login), password)


ENCRYPTION_PASSPHRASE_ACCOUNT = "encryption-passphrase"


def get_encryption_passphrase() -> str | None:
    return keyring.get_password(KEYRING_SERVICE, ENCRYPTION_PASSPHRASE_ACCOUNT)


def set_encryption_passphrase(passphrase: str) -> None:
    if not passphrase:
        raise ValueError("passphrase cannot be empty")
    keyring.set_password(KEYRING_SERVICE, ENCRYPTION_PASSPHRASE_ACCOUNT, passphrase)


class _RedactFilter(logging.Filter):
    """Strip values registered via register() from log records.

    Used for keychain-sourced passwords.
    """

    def __init__(self) -> None:
        super().__init__()
        self._secrets: list[str] = []

    def register(self, secret: str) -> None:
        if secret:
            self._secrets.append(re.escape(secret))

    def filter(self, record: logging.LogRecord) -> bool:
        if self._secrets:
            pattern = "|".join(self._secrets)
            # Format args into msg first so we don't corrupt unrelated log calls
            formatted = record.getMessage()
            record.msg = re.sub(pattern, "***", formatted)
            record.args = None
        return True

    def scrub(self, s: str) -> str:
        """Return `s` with each registered secret replaced by ***.

        Companion to `filter` for sites that bypass the `logging`
        machinery (e.g. `rich.Console`). Existing call sites do not
        interpolate registered secrets; this helper is for any future
        site that might.
        """
        if not self._secrets:
            return s
        pattern = "|".join(self._secrets)
        return re.sub(pattern, "***", s)


redact_filter = _RedactFilter()
