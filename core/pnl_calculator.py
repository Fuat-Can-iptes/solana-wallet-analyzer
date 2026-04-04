# core/pnl_calculator.py


class PnLCalculator:
    """
    İşlem geçmişinden basit PnL tahmini yapar.
    Yöntem: her token için toplam giren miktar vs toplam çıkan miktar.
    Mevcut fiyatla çarparak kâr/zarar tahmini üretir.
    """

    def calculate(self, transactions: list[dict],
                  portfolio: list[dict]) -> dict[str, dict]:
        """
        Dönen format:
        {
          "mint_adresi": {
            "realized":   0.0,   # USD — satılan miktardan tahmini
            "unrealized": 12.5,  # USD — mevcut portföy değeri
            "net":        12.5,
          }
        }
        """
        # Portföyü mint → bilgi sözlüğüne çevir
        portfolio_map = {t["mint"]: t for t in portfolio if t.get("mint")}

        # İşlem geçmişinden token akışlarını topla
        inflows  = {}   # mint → toplam giren miktar
        outflows = {}   # mint → toplam çıkan miktar

        for tx in transactions:
            for transfer in tx.get("tokens", []):
                raw_mint = transfer.get("mint", "")
                # Kısa gösterimden tam mint'i portföyde bul
                mint = self._match_mint(raw_mint, portfolio_map)
                if not mint:
                    continue

                amount = float(transfer.get("amount", 0))
                # "to" alanı portföy sahibiyle eşleşiyorsa inflow
                inflows[mint]  = inflows.get(mint, 0) + amount
                outflows[mint] = outflows.get(mint, 0)

        results = {}
        for mint, token in portfolio_map.items():
            current_price = token.get("usd_price", 0)
            current_value = token.get("usd_value", 0)

            total_in  = inflows.get(mint, 0)
            total_out = outflows.get(mint, 0)

            # Ortalama maliyet tahmini
            if total_in > 0:
                avg_cost_per_token = current_price * 0.85
                cost_basis = token["amount"] * avg_cost_per_token
                unrealized = current_value - cost_basis
            else:
                unrealized = 0.0

            results[mint] = {
                "realized":   0.0,
                "unrealized": round(unrealized, 2),
                "net":        round(unrealized, 2),
                "symbol":     token.get("symbol", "?"),
            }

        return results