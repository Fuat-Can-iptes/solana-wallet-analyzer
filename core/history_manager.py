# core/history_manager.py

import json
import os
from datetime import datetime

HISTORY_FILE = "history.json"


class HistoryManager:
    """Analiz geçmişini history.json dosyasında saklar ve okur."""

    def __init__(self):
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def _load(self) -> dict:
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _save(self, data: dict):
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def save_analysis(self, wallet: str, result: dict,
                  portfolio: list, pnl: dict = None):
        data = self._load()
        data[wallet] = {
            "wallet":     wallet,
            "result":     result,
            "portfolio":  portfolio,
            "pnl":        pnl or {},
            "timestamp":  datetime.now().strftime("%Y-%m-%d %H:%M"),
            "last_signature": None,
            "watched":      False,
        }
        self._save(data)

    def get_analysis(self, wallet: str) -> dict | None:
        """Kayıtlı analizi döner, yoksa None."""
        data = self._load()
        return data.get(wallet)

    def get_all_wallets(self) -> list[dict]:
        """Tüm kayıtlı cüzdanları zaman sırasına göre döner."""
        data = self._load()
        wallets = list(data.values())
        wallets.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return wallets

    def update_last_signature(self, wallet: str, signature: str):
        data = self._load()
        if wallet in data:
            data[wallet]["last_signature"] = signature
            self._save(data)

    def get_last_signature(self, wallet: str) -> str | None:
        data = self._load()
        return data.get(wallet, {}).get("last_signature")

    def is_watched(self, wallet: str) -> bool:
        data = self._load()
        return data.get(wallet, {}).get("watched", False)

    def set_watched(self, wallet: str, state: bool):
        data = self._load()
        if wallet in data:
            data[wallet]["watched"] = state
            self._save(data)