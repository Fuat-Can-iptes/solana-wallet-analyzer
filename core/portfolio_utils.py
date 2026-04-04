# core/portfolio_utils.py

from config.settings import IS_DEVNET


def token_label(t: dict) -> str:
    sym = (t.get("symbol") or "").strip()
    if sym and sym not in ("?", ""):
        return sym[:14]
    name = (t.get("name") or "").strip()
    if name:
        return name[:14] if len(name) > 14 else name
    mint = t.get("mint") or ""
    if len(mint) > 12:
        return f"{mint[:6]}…{mint[-4:]}"
    return mint or "?"


def portfolio_summary_line(portfolio: list[dict]) -> str:
    total_usd = sum(float(t.get("usd_value") or 0) for t in portfolio)
    with_amt = [t for t in portfolio if float(t.get("amount") or 0) > 0]
    n = len(with_amt)
    if total_usd > 0:
        return f"Toplam tahmini değer: ${total_usd:,.2f}  ·  {n} token"
    if n == 0:
        return "Listelenebilir token yok (bakiye 0 veya veri alınamadı)."
    hint = " Devnet: spot USD yok; tablo ve grafik miktar bazlı." if IS_DEVNET else " USD fiyatı bulunamadı; grafik miktar paylarına göre."
    return f"{n} token · miktar dağılımı gösteriliyor.{hint}"


def safe_token_row(token: dict) -> tuple[str, str, float, float, float]:
    """Sembol, görünen ad, miktar, usd_price, usd_value."""
    name = token.get("name") or token.get("mint") or "?"
    sym = (token.get("symbol") or "").strip() or (name[:10] if name else "?")
    amt = float(token.get("amount") or 0)
    price = float(token.get("usd_price") or 0)
    usd = float(token.get("usd_value") or 0)
    return sym, name, amt, price, usd
