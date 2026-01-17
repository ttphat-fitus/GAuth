from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path


class VerificationLog:
    def __init__(self, log_dir: str = "logs") -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.success_file = self.log_dir / "verification_success.jsonl"
        self.failed_file = self.log_dir / "verification_failed.jsonl"

    def log_success(
        self,
        discord_id: int,
        discord_username: str,
        full_name: str,
        mssv: str,
        email: str,
    ) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "discord_id": discord_id,
            "discord_username": discord_username,
            "full_name": full_name,
            "mssv": mssv,
            "email": email,
            "status": "success",
        }
        with open(self.success_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def log_failed_attempts(
        self,
        discord_id: int,
        discord_username: str,
        full_name: str,
        mssv: str,
        email: str,
        reason: str,
    ) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "discord_id": discord_id,
            "discord_username": discord_username,
            "full_name": full_name,
            "mssv": mssv,
            "email": email,
            "reason": reason,
        }
        with open(self.failed_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        print(f"[GAuth] Logged failed: {discord_username} ({mssv}) - {reason}")

    def count_success(self) -> int:
        if not self.success_file.exists():
            return 0
        with open(self.success_file, "r", encoding="utf-8") as f:
            return len(f.readlines())

    def count_failed(self) -> int:
        if not self.failed_file.exists():
            return 0
        with open(self.failed_file, "r", encoding="utf-8") as f:
            return len(f.readlines())

    def get_failed_entries(self, limit: int = 20) -> list[dict]:
        if not self.failed_file.exists():
            return []
        entries = []
        with open(self.failed_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines[-limit:]:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return entries
