# core/price_fetcher.py

import requests

from config.settings import IS_DEVNET

DEXSCREENER_API = "https://api.dexscreener.com/tokens/v1/solana"
# Wrapped SOL mint (mainnet ve devnet aynı adres)
WSOL_MINT = "So11111111111111111111111111111111111111112"
COINGECKO_SOL = "https://api.coingecko.com/api/v3/simple/price"
HTTP_HEADERS = {"User-Agent": "SolanaWalletAnalyzer/1.0 (portfolio)"}


class PriceFetcher:

    def _fetch_sol_usd(self) -> float:
        """CoinGecko: spot SOL/USD (devnet WSOL için yaklaşık referans)."""
        try:
            r = requests.get(
                COINGECKO_SOL,
                params={"ids": "solana", "vs_currencies": "usd"},
                headers=HTTP_HEADERS,
                timeout=12,
            )
            r.raise_for_status()
            return float(r.json().get("solana", {}).get("usd") or 0)
        except Exception as e:
            print(f"[PriceFetcher] CoinGecko SOL: {e}")
            return 0.0

    def _dexscreener_batch(self, mint_addresses: list[str]) -> dict[str, dict]:
        results: dict[str, dict] = {}
        if not mint_addresses:
            return results

        # Kısa URL / timeout riski için küçük parçalar
        chunk_size = 10
        for i in range(0, len(mint_addresses), chunk_size):
            chunk = [m for m in mint_addresses[i : i + chunk_size] if m]
            if not chunk:
                continue
            ids = ",".join(chunk)
            try:
                r = requests.get(
                    f"{DEXSCREENER_API}/{ids}",
                    headers=HTTP_HEADERS,
                    timeout=15,
                )
                r.raise_for_status()
                pairs = r.json()
                if not isinstance(pairs, list):
                    pairs = []

                best: dict[str, dict] = {}
                for pair in pairs:
                    base = pair.get("baseToken") or {}
                    mint = base.get("address", "")
                    price = float(pair.get("priceUsd") or 0)
                    liq = float((pair.get("liquidity") or {}).get("usd") or 0)

                    if mint and price > 0:
                        if mint not in best or liq > best[mint]["liq"]:
                            best[mint] = {
                                "price": price,
                                "symbol": base.get("symbol", mint[:6]),
                                "name": base.get("name", ""),
                                "liq": liq,
                            }

                for mint, data in best.items():
                    results[mint] = {
                        "price": data["price"],
                        "symbol": data["symbol"],
                        "name": data["name"],
                    }
            except Exception as e:
                print(f"[PriceFetcher] DexScreener: {e}")

        return results

    def get_prices_for_mints(self, mint_addresses: list[str]) -> dict[str, dict]:
        """
        Dönen format:
        { "mint": { "price": 1.23, "symbol": "SOL", "name": "..." } }
        """
        mints = [m.strip() for m in mint_addresses if m and str(m).strip()]
        if not mints:
            return {}

        if IS_DEVNET:
            # Devnet mint'leri DEX’te yok; yalnızca WSOL için CoinGecko spot (referans).
            out: dict[str, dict] = {}
            sol_usd = self._fetch_sol_usd()
            if sol_usd > 0 and WSOL_MINT in mints:
                out[WSOL_MINT] = {
                    "price": sol_usd,
                    "symbol": "SOL",
                    "name": "SOL (~spot, CoinGecko)",
                }
            print(
                f"[PriceFetcher] Devnet: {len(out)}/{len(mints)} mint için "
                "referans fiyat (çoğunlukla yalnızca SOL)."
            )
            return out

        results = self._dexscreener_batch(mints)

        # WSOL / SOL DexScreener’da boş kaldıysa CoinGecko ile doldur
        need_sol = WSOL_MINT in mints and WSOL_MINT not in results
        if need_sol:
            sol_usd = self._fetch_sol_usd()
            if sol_usd > 0:
                results[WSOL_MINT] = {
                    "price": sol_usd,
                    "symbol": "SOL",
                    "name": "Wrapped SOL",
                }

        print(f"[PriceFetcher] {len(results)}/{len(mints)} token fiyatlandı")
        return results

    def enrich_portfolio(self, portfolio: list[dict]) -> list[dict]:
        mints = [t.get("mint", "") for t in portfolio if t.get("mint")]
        data = self.get_prices_for_mints(mints)

        enriched = []
        for token in portfolio:
            mint = token.get("mint", "")
            base_name = (token.get("name") or "").strip()
            if not base_name:
                base_name = (
                    f"{mint[:8]}…{mint[-4:]}" if mint and len(mint) > 12 else (mint or "?")
                )
            info = data.get(mint, {})
            price = float(info.get("price") or 0)
            symbol = info.get("symbol") or base_name[:10]
            name = (info.get("name") or "").strip()
            full_name = name or base_name
            amt = float(token.get("amount") or 0)
            usd_val = amt * price

            enriched.append({
                **token,
                "symbol":    symbol,
                "full_name": full_name,
                "usd_price": price,
                "usd_value": usd_val,
            })

        enriched.sort(key=lambda x: x["usd_value"], reverse=True)
        return enriched
