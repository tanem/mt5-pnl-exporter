"""Keyring-based secret access and log redaction."""

from __future__ import annotations

import logging
import re

import keyring

KEYRING_SERVICE = "mt5-pnl-exporter"


def get_investor_password(login: int) -> str | None:
    return keyring.get_password(KEYRING_SERVICE, str(login))


def set_investor_password(login: int, password: str) -> None:
    keyring.set_password(KEYRING_SERVICE, str(login), password)


ENCRYPTION_PASSPHRASE_ACCOUNT = "encryption-passphrase"


def get_encryption_passphrase() -> str | None:
    return keyring.get_password(KEYRING_SERVICE, ENCRYPTION_PASSPHRASE_ACCOUNT)


def set_encryption_passphrase(passphrase: str) -> None:
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


redact_filter = _RedactFilter()
