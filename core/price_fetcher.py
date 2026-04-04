# core/price_fetcher.py

import requests

DEXSCREENER_API = "https://api.dexscreener.com/tokens/v1/solana"


class PriceFetcher:

    def get_prices_for_mints(self, mint_addresses: list[str]) -> dict[str, dict]:
        """
        Dönen format:
        { "mint": { "price": 1.23, "symbol": "SOL", "name": "Wrapped SOL" } }
        """
        if not mint_addresses:
            return {}

        results = {}
        chunk_size = 30

        for i in range(0, len(mint_addresses), chunk_size):
            chunk = mint_addresses[i:i + chunk_size]
            ids   = ",".join(chunk)
            try:
                r = requests.get(
                    f"{DEXSCREENER_API}/{ids}",
                    timeout=10,
                )
                r.raise_for_status()
                pairs = r.json()

                best = {}
                for pair in pairs:
                    base  = pair.get("baseToken", {})
                    mint  = base.get("address", "")
                    price = float(pair.get("priceUsd") or 0)
                    liq   = float((pair.get("liquidity") or {}).get("usd") or 0)

                    if mint and price > 0:
                        if mint not in best or liq > best[mint]["liq"]:
                            best[mint] = {
                                "price":  price,
                                "symbol": base.get("symbol", mint[:6]),
                                "name":   base.get("name", ""),
                                "liq":    liq,
                            }

                for mint, data in best.items():
                    results[mint] = {
                        "price":  data["price"],
                        "symbol": data["symbol"],
                        "name":   data["name"],
                    }

            except Exception as e:
                print(f"[PriceFetcher] Hata: {e}")

        print(f"[PriceFetcher] {len(results)}/{len(mint_addresses)} token fiyatlandı")
        return results

    def enrich_portfolio(self, portfolio: list[dict]) -> list[dict]:
        mints   = [t.get("mint", "") for t in portfolio if t.get("mint")]
        data    = self.get_prices_for_mints(mints)

        enriched = []
        for token in portfolio:
            mint     = token.get("mint", "")
            info     = data.get(mint, {})
            price    = info.get("price", 0.0)
            symbol   = info.get("symbol", token["name"])
            name     = info.get("name", "")
            usd_val  = token["amount"] * price

            enriched.append({
                **token,
                "symbol":    symbol,
                "full_name": name,
                "usd_price": price,
                "usd_value": usd_val,
            })

        enriched.sort(key=lambda x: x["usd_value"], reverse=True)
        return enriched