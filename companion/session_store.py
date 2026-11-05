"""Optional Windows Credential Manager refresh-token storage using keyring.

No password or refresh token goes into config.json, .env, logs, or ChatGPT.
The keyring library picks the OS credential backend. We only enable persistence
on Windows to avoid insecure fallback implementations on other platforms.
"""
from __future__ import annotations
import sys

SERVICE = "ApexIQCompanion.Cloud"
ACCOUNT = "A.R.I.S Cloud user refresh session"


class CloudSessionStore:
    @staticmethod
    def available() -> bool:
        if sys.platform != "win32":
            return False
        try:
            import keyring
            return True
        except ImportError:
            return False

    def read(self) -> str | None:
        if not self.available():
            return None
        try:
            import keyring
            return keyring.get_password(SERVICE, ACCOUNT)
        except Exception:
            return None

    def save(self, refresh_token: str) -> bool:
        if not self.available() or not refresh_token:
            return False
        try:
            import keyring
            keyring.set_password(SERVICE, ACCOUNT, refresh_token)
            return True
        except Exception:
            return False

    def forget(self) -> None:
        if not self.available():
            return
        try:
            import keyring
            keyring.delete_password(SERVICE, ACCOUNT)
        except Exception:
            return
