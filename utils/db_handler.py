from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass(frozen=True)
class MemberRecord:
    full_name: str
    mssv: str
    email: str
    dob: str


class DBHandler:
    def __init__(self, csv_path: str) -> None:
        self.csv_path = csv_path
        self._df: Optional[pd.DataFrame] = None

    def load(self) -> None:
        if not os.path.exists(self.csv_path):
            raise FileNotFoundError(f"CSV not found: {self.csv_path}")

        # Data has no header; some fields may be quoted and contain commas.
        df = pd.read_csv(
            self.csv_path,
            header=None,
            dtype=str,
            keep_default_na=False,
            encoding="utf-8",
        )

        # Ensure at least 5 columns exist (we need 0,1,3,4)
        needed_cols = 5
        if df.shape[1] < needed_cols:
            for col in range(df.shape[1], needed_cols):
                df[col] = ""

        # Normalize
        df[0] = df[0].astype(str).str.strip()
        df[1] = df[1].astype(str).str.strip()
        df[3] = df[3].astype(str).str.strip().str.lower()
        df[4] = df[4].astype(str).str.strip()

        self._df = df

    def _ensure_loaded(self) -> pd.DataFrame:
        if self._df is None:
            self.load()
        assert self._df is not None
        return self._df

    def find_by_identifier(self, identifier: str) -> Optional[MemberRecord]:
        identifier = (identifier or "").strip()
        if not identifier:
            return None

        df = self._ensure_loaded()

        identifier_lower = identifier.lower()

        # MSSV match (exact)
        mssv_match = df[df[1] == identifier]
        if not mssv_match.empty:
            row = mssv_match.iloc[0]
            return MemberRecord(
                full_name=str(row[0]).strip(),
                mssv=str(row[1]).strip(),
                email=str(row[3]).strip().lower(),
                dob=str(row[4]).strip(),
            )

        # Email match (case-insensitive exact)
        email_match = df[df[3] == identifier_lower]
        if not email_match.empty:
            row = email_match.iloc[0]
            return MemberRecord(
                full_name=str(row[0]).strip(),
                mssv=str(row[1]).strip(),
                email=str(row[3]).strip().lower(),
                dob=str(row[4]).strip(),
            )

        return None
