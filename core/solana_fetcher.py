# core/solana_fetcher.py

import requests
import datetime
from config.settings import HELIUS_API_KEY, HELIUS_RPC_URL, MAX_TRANSACTIONS


class SolanaDataFetcher:

    def __init__(self):
        self.enhanced_url = (
            f"https://api.helius.xyz/v0/addresses/"
            f"{{address}}/transactions?api-key={HELIUS_API_KEY}"
            f"&limit={MAX_TRANSACTIONS}"
        )

    # ------------------------------------------------------------------ #
    #  İşlem Geçmişi                                                       #
    # ------------------------------------------------------------------ #
    def fetch_transactions(self, wallet_address: str) -> list[dict]:
        url = self.enhanced_url.format(address=wallet_address)
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Helius API hatası: {e}")

    def parse_transactions(self, raw_txs: list[dict]) -> list[dict]:
        cleaned = []
        for tx in raw_txs:
            tx_type    = tx.get("type", "UNKNOWN")
            description = tx.get("description", "").strip()
            fee_sol    = tx.get("fee", 0) / 1_000_000_000
            ts         = tx.get("timestamp", 0)
            readable_ts = datetime.datetime.utcfromtimestamp(ts).strftime(
                "%Y-%m-%d %H:%M"
            ) if ts else "Bilinmiyor"
            cleaned.append({
                "type":        tx_type,
                "description": description or f"{tx_type} işlemi",
                "fee_sol":     round(fee_sol, 6),
                "timestamp":   readable_ts,
                "tokens":      self._extract_token_transfers(tx),
            })
        return cleaned

    def _extract_token_transfers(self, tx: dict) -> list[dict]:
        transfers = []
        for t in tx.get("tokenTransfers", []):
            transfers.append({
                "mint":   t.get("mint", "")[:8] + "...",
                "amount": t.get("tokenAmount", 0),
                "from":   t.get("fromUserAccount", "")[:8] + "...",
                "to":     t.get("toUserAccount", "")[:8] + "...",
            })
        return transfers

    def get_clean_transactions(self, wallet_address: str) -> list[dict]:
        raw = self.fetch_transactions(wallet_address)
        return self.parse_transactions(raw)

    def get_latest_signature(self, wallet_address: str) -> str | None:
        """Polling için en son işlemin imzasını döner."""
        url = self.enhanced_url.format(address=wallet_address) + "&limit=1"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            txs = response.json()
            if txs:
                return txs[0].get("signature")
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------ #
    #  Token Portföyü                                                      #
    # ------------------------------------------------------------------ #
    def get_token_balances(self, wallet_address: str) -> list[dict]:
        """
        Helius RPC üzerinden cüzdanın token bakiyelerini çeker.
        Dönen format: [{"name": "...", "amount": 0.0}, ...]
        """
        payload = {
            "jsonrpc": "2.0",
            "id":      1,
            "method":  "getTokenAccountsByOwner",
            "params":  [
                wallet_address,
                {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                {"encoding": "jsonParsed"},
            ],
        }
        try:
            response = requests.post(HELIUS_RPC_URL, json=payload, timeout=15)
            response.raise_for_status()
            accounts = response.json().get("result", {}).get("value", [])

            tokens = []
            for acc in accounts:
                info   = acc["account"]["data"]["parsed"]["info"]
                mint   = info.get("mint", "")
                amount = info.get("tokenAmount", {})
                ui_amt = float(amount.get("uiAmount") or 0)

                if ui_amt > 0:
                    tokens.append({
                        "name":   mint[:8] + "..." + mint[-4:],
                        "amount": ui_amt,
                        "mint":   mint,
                    })

            tokens.sort(key=lambda x: x["amount"], reverse=True)
            return tokens

        except Exception as e:
            raise ConnectionError(f"Token bakiyesi alınamadı: {e}")