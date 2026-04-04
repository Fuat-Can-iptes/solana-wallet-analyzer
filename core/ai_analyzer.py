# core/ai_analyzer.py

import json
import requests
from config.settings import GROQ_API_KEY, SYSTEM_PROMPT


class AIAnalyzer:

    def __init__(self):
        self.api_key  = GROQ_API_KEY
        self.endpoint = "https://api.groq.com/openai/v1/chat/completions"

    def _build_prompt(self, wallet: str, transactions: list[dict],
                      portfolio: list[dict], total_usd: float) -> str:

        tx_text = json.dumps(transactions, ensure_ascii=False, indent=2)

        # Portföy özetini hazırla — sadece değeri olan tokenlar
        portfolio_lines = []
        for t in portfolio:
            usd = t.get("usd_value", 0)
            if usd > 0:
                portfolio_lines.append(
                    f"  - {t['name']}: {t['amount']:,.2f} adet "
                    f"(~${usd:,.2f})"
                )
        portfolio_text = "\n".join(portfolio_lines) if portfolio_lines \
            else "  Fiyatı bilinen token bulunamadı."

        return (
            f"Analiz edilecek cüzdan: {wallet}\n\n"
            f"PORTFÖY (Toplam tahmini değer: ~${total_usd:,.2f} USD):\n"
            f"{portfolio_text}\n\n"
            f"Son {len(transactions)} işlem:\n{tx_text}\n\n"
            f"Yanıtını SADECE şu JSON formatında ver:\n"
            f'{{"risk_level":"...","investor_type":"...","analysis":"...",'
            f'"recommendations":[{{"action":"...","reason":"...","risk":"..."}},'
            f'{{"action":"...","reason":"...","risk":"..."}},'
            f'{{"action":"...","reason":"...","risk":"..."}}]}}'
        )

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

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json",
        }

        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",
                 "content": self._build_prompt(
                     wallet_address, transactions, portfolio, total_usd
                 )},
            ],
            "temperature":     0.85,
            "max_tokens":      1024,
            "response_format": {"type": "json_object"},
        }

        try:
            r = requests.post(
                self.endpoint, headers=headers,
                json=payload, timeout=30
            )
            if not r.ok:
                print(f"[DEBUG] {r.status_code}: {r.text}")
                r.raise_for_status()

            text = r.json()["choices"][0]["message"]["content"].strip()
            return json.loads(text)

        except json.JSONDecodeError as e:
            raise RuntimeError(f"JSON parse hatası: {e}")
        except (requests.exceptions.RequestException, KeyError) as e:
            raise RuntimeError(f"AI Analiz hatası: {e}")