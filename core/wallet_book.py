# core/wallet_book.py

import json
import os
import re
from datetime import datetime

WALLET_BOOK_FILE = "wallet_book.json"

# Base58 Solana adresi (yaklaşık uzunluk)
SOLANA_ADDRESS_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


def is_valid_solana_address(addr: str) -> bool:
    s = (addr or "").strip()
    return bool(SOLANA_ADDRESS_RE.match(s))


class WalletBook:
    """Kayıtlı cüzdan adresleri (hesaplarım + manuel eklenenler)."""

    def __init__(self):
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(WALLET_BOOK_FILE):
            with open(WALLET_BOOK_FILE, "w", encoding="utf-8") as f:
                json.dump({"wallets": []}, f, ensure_ascii=False, indent=2)

    def _load(self) -> dict:
        try:
            with open(WALLET_BOOK_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"wallets": []}

    def _save(self, data: dict):
        with open(WALLET_BOOK_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def list_all(self) -> list[dict]:
        data = self._load()
        wallets = data.get("wallets", [])
        return sorted(wallets, key=lambda x: (x.get("label") or "").lower())

    def add(self, address: str, label: str = "", source: str = "manual") -> bool:
        addr = address.strip()
        if not is_valid_solana_address(addr):
            return False
        data = self._load()
        wallets = data.get("wallets", [])
        for w in wallets:
            if w.get("address") == addr:
                if label and not w.get("label"):
                    w["label"] = label
                    self._save(data)
                return True
        wallets.append({
            "address": addr,
            "label":   (label or "Cüzdan").strip() or "Cüzdan",
            "source":  source,
            "added":   datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        data["wallets"] = wallets
        self._save(data)
        return True

    def remove(self, address: str) -> bool:
        addr = address.strip()
        data = self._load()
        wallets = [w for w in data.get("wallets", []) if w.get("address") != addr]
        if len(wallets) == len(data.get("wallets", [])):
            return False
        data["wallets"] = wallets
        self._save(data)
        return True
