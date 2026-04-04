# core/compare_summary.py
# İki cüzdanın kayıtlı analiz + portföy verisinden kısa, yönlü karşılaştırma metni.


def _short_addr(wallet: str) -> str:
    w = (wallet or "").strip()
    if len(w) <= 12:
        return w or "?"
    return f"{w[:6]}…{w[-4:]}"


def _risk_rank(level: str) -> int:
    """Yüksek = daha riskli AI etiketi."""
    m = (level or "").upper().strip()
    order = {
        "DÜŞÜK": 1,
        "ORTA": 2,
        "YÜKSEK": 3,
        "KRİTİK": 4,
        "BİLİNMİYOR": 2,
    }
    return order.get(m, 2)


def _risk_label(rank: int) -> str:
    for k, v in (
        ("DÜŞÜK", 1), ("ORTA", 2), ("YÜKSEK", 3), ("KRİTİK", 4)
    ):
        if v == rank:
            return k
    return "?"


def _portfolio_metrics(portfolio: list[dict]) -> dict:
    tokens = [t for t in portfolio if float(t.get("amount") or 0) > 0]
    n = len(tokens)
    total_usd = sum(float(t.get("usd_value") or 0) for t in tokens)

    if total_usd > 0:
        shares = [float(t.get("usd_value") or 0) / total_usd for t in tokens]
    else:
        total_amt = sum(float(t.get("amount") or 0) for t in tokens)
        if total_amt > 0:
            shares = [float(t.get("amount") or 0) / total_amt for t in tokens]
        else:
            shares = []

    hhi = sum(s * s for s in shares) if shares else 0.0
    return {"n": n, "total_usd": total_usd, "hhi": hhi}


def build_wallet_comparison_report(
    wallet_a: str,
    result_a: dict,
    portfolio_a: list,
    wallet_b: str,
    result_b: dict,
    portfolio_b: list,
) -> str:
    """
    Türkçe düz metin: hangi cüzdan hangi boyutta relativ olarak daha iyi/kötü / belirsiz.
    """
    la = _short_addr(wallet_a)
    lb = _short_addr(wallet_b)
    ra = _risk_rank(result_a.get("risk_level"))
    rb = _risk_rank(result_b.get("risk_level"))
    ma = _portfolio_metrics(portfolio_a or [])
    mb = _portfolio_metrics(portfolio_b or [])

    lines: list[str] = [
        "KİM NEREDE ÖNE ÇIKIYOR?",
        "─" * 44,
        "",
    ]

    # --- Risk (düşük = muhafazakar açıdan “daha sakin”) ---
    if ra < rb:
        lines.append(
            f"• Risk (AI): {la} daha düşük risk bandında ({_risk_label(ra)}), "
            f"{lb} daha yüksek ({_risk_label(rb)}). "
            f"Volatiliteden kaçınmak isteyen açıdan {la} relativ olarak daha sakin görünüyor."
        )
        lines.append(
            f"  → Relativ daha agresif / yüksek risk etiketi: {lb}."
        )
    elif rb < ra:
        lines.append(
            f"• Risk (AI): {lb} daha düşük risk bandında ({_risk_label(rb)}), "
            f"{la} daha yüksek ({_risk_label(ra)}). "
            f"Volatiliteden kaçınmak isteyen açıdan {lb} relativ olarak daha sakin."
        )
        lines.append(
            f"  → Relativ daha agresif / yüksek risk etiketi: {la}."
        )
    else:
        lines.append(
            f"• Risk (AI): İkisi de aynı banda yakın ({_risk_label(ra)}). "
            "Bu eksende net bir üstünlük yok."
        )

    lines.append("")

    # --- Çeşitlilik ---
    if ma["n"] > mb["n"]:
        lines.append(
            f"• Çeşitlilik: {la} daha fazla farklı token gösteriyor "
            f"({ma['n']} çeşit vs {mb['n']}). "
            f"Tek tipe yığılma riskine karşı {lb} daha dar bir portföy."
        )
    elif mb["n"] > ma["n"]:
        lines.append(
            f"• Çeşitlilik: {lb} daha fazla farklı token "
            f"({mb['n']} vs {ma['n']}). "
            f"{la} relativ olarak daha konsantre bir liste."
        )
    else:
        lines.append(
            f"• Çeşitlilik: Token sayısı yaklaşık eşit ({ma['n']})."
        )

    lines.append("")

    # --- Yoğunlaşma (HHI: 1 = tek varlık, düşük = daha dağınık) ---
    diff_hhi = abs(ma["hhi"] - mb["hhi"])
    if ma["n"] <= 1 and mb["n"] <= 1:
        lines.append(
            "• Yoğunlaşma: Her iki tarafta da tek veya çok az token — "
            "dağılım karşılaştırması sınırlı."
        )
    elif diff_hhi >= 0.08:
        if ma["hhi"] > mb["hhi"]:
            lines.append(
                f"• Yoğunlaşma: {la} varlıkların büyük kısmını daha az sayıda "
                f"tokende topluyor (daha yığılmacı). {lb} relativ olarak daha dağınık."
            )
        else:
            lines.append(
                f"• Yoğunlaşma: {lb} daha yığılmacı; {la} relativ olarak dağılımı daha geniş."
            )
    else:
        lines.append(
            "• Yoğunlaşma: İki portföyde varlık dağılımı birbirine yakın yoğunlukta."
        )

    lines.append("")

    # --- USD toplam ---
    if ma["total_usd"] > 0 and mb["total_usd"] > 0:
        if ma["total_usd"] > mb["total_usd"] * 1.15:
            lines.append(
                f"• Tahmini toplam değer (USD): {la} daha yüksek "
                f"(~${ma['total_usd']:,.0f} vs ~${mb['total_usd']:,.0f}). "
                f"Yüksek değer otomatik olarak “daha iyi” değildir; sadece büyüklük farkı."
            )
        elif mb["total_usd"] > ma["total_usd"] * 1.15:
            lines.append(
                f"• Tahmini toplam değer (USD): {lb} daha yüksek "
                f"(~${mb['total_usd']:,.0f} vs ~${ma['total_usd']:,.0f})."
            )
        else:
            lines.append(
                "• Tahmini toplam değer (USD): İki taraf yaklaşık aynı büyüklükte."
            )
    elif ma["total_usd"] > 0 >= mb["total_usd"]:
        lines.append(
            f"• USD değer: Anlamlı toplam yalnızca {la} için; "
            f"{lb} tarafında fiyat verisi yok veya sıfır (ör. devnet)."
        )
    elif mb["total_usd"] > 0 >= ma["total_usd"]:
        lines.append(
            f"• USD değer: Anlamlı toplam yalnızca {lb} için; "
            f"{la} tarafında fiyat verisi yok veya sıfır."
        )
    else:
        lines.append(
            "• USD değer: Her iki tarafta da spot USD toplamı yok veya anlamsız; "
            "grafik ve miktar sütununa bakın (devnet’te sık görülür)."
        )

    lines.extend([
        "",
        "─" * 44,
        "ÖZET",
        "─" * 44,
    ])

    # Kısa özet cümlesi
    bits = []
    if ra != rb:
        safer = la if ra < rb else lb
        bits.append(f"Daha düşük AI risk etiketi: {safer}.")
    if ma["n"] != mb["n"]:
        wider = la if ma["n"] > mb["n"] else lb
        bits.append(f"Daha çok token çeşidi: {wider}.")
    if ma["total_usd"] > 0 and mb["total_usd"] > 0:
        if ma["total_usd"] > mb["total_usd"] * 1.15:
            bits.append(f"Daha yüksek tahmini USD toplamı: {la}.")
        elif mb["total_usd"] > ma["total_usd"] * 1.15:
            bits.append(f"Daha yüksek tahmini USD toplamı: {lb}.")

    if bits:
        lines.append(" ".join(bits))
    else:
        lines.append(
            "Bu metriklerle iki cüzdan birbirine oldukça yakın; "
            "detay için aşağıdaki AI analiz metinlerine bakın."
        )

    lines.extend([
        "",
        "Not: Bu metin kayıtlı analiz verisine dayalı otomatik bir özetdir; "
        "yatırım tavsiyesi değildir.",
    ])

    return "\n".join(lines)
