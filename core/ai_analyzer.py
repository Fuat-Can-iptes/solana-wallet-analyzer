# core/ai_analyzer.py

import json
import random
import time

import requests

from config.settings import (
    AI_USE_OPENAI_FALLBACK,
    GROQ_API_KEY,
    GROQ_MAX_RETRIES,
    GROQ_MODEL,
    GROQ_RETRY_BASE_SEC,
    IS_DEVNET,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    SYSTEM_PROMPT,
)


class AIAnalyzer:

    def __init__(self):
        self.groq_key = GROQ_API_KEY
        self.groq_url = "https://api.groq.com/openai/v1/chat/completions"

    def _build_prompt(self, wallet: str, transactions: list[dict],
                      portfolio: list[dict], total_usd: float) -> str:

        tx_text = json.dumps(transactions, ensure_ascii=False, indent=2)

        portfolio_lines = []
        for t in portfolio:
            usd = float(t.get("usd_value", 0) or 0)
            amt = float(t.get("amount", 0) or 0)
            nm = t.get("name") or t.get("mint", "?")[:16]
            if usd > 0:
                portfolio_lines.append(
                    f"  - {nm}: {amt:,.2f} adet (~${usd:,.2f})"
                )
            elif IS_DEVNET and amt > 0:
                portfolio_lines.append(
                    f"  - {nm}: {amt:,.2f} adet (Devnet — spot USD yok)"
                )
        if portfolio_lines:
            portfolio_text = "\n".join(portfolio_lines)
        elif IS_DEVNET:
            portfolio_text = (
                "  Devnet: bakiye/token yok veya listelenemedi "
                "(test ağı, gerçek para değildir)."
            )
        else:
            portfolio_text = "  Fiyatı bilinen token bulunamadı."

        cluster = "Solana Devnet (test ağı)" if IS_DEVNET else "Solana Mainnet"
        return (
            f"Analiz edilecek cüzdan: {wallet}\n"
            f"Ağ bağlamı: {cluster}\n\n"
            f"PORTFÖY (Toplam tahmini değer: ~${total_usd:,.2f} USD):\n"
            f"{portfolio_text}\n\n"
            f"Son {len(transactions)} işlem:\n{tx_text}\n\n"
            "Çıktı: risk_level, investor_type, analysis (8–12+ cümle), "
            "recommendations dizisinde tam 5 nesne; her birinde action, reason "
            "(≥3 cümle), risk, detail (≥2 cümle). Sadece JSON.\n"
        )

    @staticmethod
    def _should_try_openai_fallback(err: BaseException) -> bool:
        if not AI_USE_OPENAI_FALLBACK or not OPENAI_API_KEY:
            return False
        if isinstance(err, requests.HTTPError) and err.response is not None:
            return err.response.status_code in (429, 503)
        if isinstance(err, RuntimeError):
            m = str(err).lower()
            return any(
                k in m
                for k in ("429", "503", "kotası", "yoğun", "tamamlanamadı")
            )
        return False

    def _openai_complete(self, system_content: str, user_content: str) -> dict:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type":  "application/json",
        }
        payload = {
            "model":       OPENAI_MODEL,
            "messages":    [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.72,
            "max_tokens":  4096,
            "response_format": {"type": "json_object"},
        }
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=120,
        )
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"].strip()
        return json.loads(text)

    def analyze(self, wallet_address: str, transactions: list[dict],
                portfolio: list[dict] = None,
                total_usd: float = 0.0) -> dict:

        if portfolio is None:
            portfolio = []

        if not transactions:
            return {
                "risk_level":    "BİLİNMİYOR",
                "investor_type": "Hayalet",
                "analysis":      "Bu cüzdan sessizliğin kendisi. Veri yok.",
                "recommendations": [],
            }

        system_content = SYSTEM_PROMPT
        if IS_DEVNET:
            system_content += (
                "\n\nBağlam: Veriler Solana Devnet test ağındandır; gerçek para "
                "değildir. Tokenlerin çoğunun spot USD fiyatı yoktur. Analizi test "
                "ağı / geliştirme perspektifiyle yap."
            )

        user_content = self._build_prompt(
            wallet_address, transactions, portfolio, total_usd
        )

        groq_payload = {
            "model":       GROQ_MODEL,
            "messages":    [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.72,
            "max_tokens":  3072,
            "response_format": {"type": "json_object"},
        }
        groq_headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type":  "application/json",
        }

        if not self.groq_key:
            if OPENAI_API_KEY and AI_USE_OPENAI_FALLBACK:
                print("[AI] GROQ_API_KEY yok — OpenAI kullanılıyor.")
                try:
                    return self._openai_complete(system_content, user_content)
                except Exception as e:
                    raise RuntimeError(f"OpenAI analiz hatası: {e}") from e
            raise RuntimeError(
                "GROQ_API_KEY tanımlı değil (.env). OpenAI yedeği için "
                "OPENAI_API_KEY ekleyin veya Groq anahtarını girin."
            )

        try:
            r = self._post_groq_with_retry(groq_headers, groq_payload)
            text = r.json()["choices"][0]["message"]["content"].strip()
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"JSON parse hatası: {e}") from e
        except (RuntimeError, requests.HTTPError) as e:
            if self._should_try_openai_fallback(e):
                print("[AI] Groq kotası veya geçici hata — OpenAI yedeğe geçiliyor…")
                try:
                    return self._openai_complete(system_content, user_content)
                except Exception as oe:
                    raise RuntimeError(
                        f"Groq: {e} | OpenAI yedek de başarısız: {oe}"
                    ) from oe
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"AI Analiz hatası: {e}") from e
        except (requests.exceptions.RequestException, KeyError) as e:
            if self._should_try_openai_fallback(e):
                try:
                    return self._openai_complete(system_content, user_content)
                except Exception as oe:
                    raise RuntimeError(
                        f"Ağ hatası: {e} | OpenAI: {oe}"
                    ) from oe
            raise RuntimeError(f"AI Analiz hatası: {e}") from e

    def _wait_after_rate_limit(self, response: requests.Response, attempt: int) -> float:
        ra = response.headers.get("Retry-After")
        if ra:
            try:
                return min(float(ra), 120.0)
            except ValueError:
                pass
        base = GROQ_RETRY_BASE_SEC * (2**attempt)
        return min(base + random.uniform(0, 1.5), 90.0)

    def _post_groq_with_retry(
        self, headers: dict, payload: dict
    ) -> requests.Response:
        for attempt in range(GROQ_MAX_RETRIES):
            r = requests.post(
                self.groq_url,
                headers=headers,
                json=payload,
                timeout=90,
            )
            if r.status_code == 200:
                return r

            if r.status_code in (429, 503) and attempt < GROQ_MAX_RETRIES - 1:
                wait = self._wait_after_rate_limit(r, attempt)
                print(
                    f"[Groq] {r.status_code} — {wait:.1f}s bekleniyor "
                    f"({attempt + 1}/{GROQ_MAX_RETRIES})"
                )
                time.sleep(wait)
                continue

            if r.status_code == 429:
                raise RuntimeError(
                    "Groq API kotası aşıldı (429 Too Many Requests). "
                    "console.groq.com üzerinden limit kontrol edin veya "
                    "OPENAI_API_KEY ile otomatik yedek kullanın."
                )
            if r.status_code == 503:
                raise RuntimeError(
                    "Groq geçici olarak yoğun (503). Bir süre sonra tekrar deneyin."
                )

            if not r.ok:
                print(f"[DEBUG] {r.status_code}: {r.text[:500]}")
                r.raise_for_status()

        raise RuntimeError("Groq isteği tamamlanamadı.")
