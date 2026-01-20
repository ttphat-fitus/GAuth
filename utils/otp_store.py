from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional


@dataclass
class OTPEntry:
    code: str
    email: str
    full_name: str
    mssv: str
    expires_at: datetime


class OTPStore:
    def __init__(self) -> None:
        self._by_user_id: dict[int, OTPEntry] = {}

    def set(
        self,
        user_id: int,
        *,
        code: str,
        email: str,
        full_name: str,
        mssv: str,
        ttl_seconds: int,
    ) -> None:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        self._by_user_id[user_id] = OTPEntry(
            code=code,
            email=email,
            full_name=full_name,
            mssv=mssv,
            expires_at=expires_at,
        )

    def get(self, user_id: int) -> Optional[OTPEntry]:
        entry = self._by_user_id.get(user_id)
        if entry is None:
            return None
        if datetime.now(timezone.utc) >= entry.expires_at:
            self._by_user_id.pop(user_id, None)
            return None
        return entry

    def clear(self, user_id: int) -> None:
        self._by_user_id.pop(user_id, None)
