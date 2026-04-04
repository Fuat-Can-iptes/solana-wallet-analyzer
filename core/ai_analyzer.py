import json
import requests
from config.settings import GROQ_API_KEY, SYSTEM_PROMPT


class AIAnalyzer:
    def __init__(self):
        self.api_key = GROQ_API_KEY
        self.endpoint = "https://api.groq.com/openai/v1/chat/completions"

    def _build_prompt(self, wallet: str, transactions: list[dict]) -> str:
        tx_text = json.dumps(transactions, ensure_ascii=False, indent=2)
        return (
            f"Analiz edilecek cüzdan: {wallet}\n\n"
            f"Son {len(transactions)} işlem:\n{tx_text}\n\n"
            f"Yanıtını SADECE şu JSON formatında ver, başka hiçbir şey yazma:\n"
            f'{{"risk_level": "...", "investor_type": "...", "analysis": "..."}}'
        )

    def analyze(self, wallet_address: str, transactions: list[dict]) -> dict:
        if not transactions:
            return {
                "risk_level": "BİLİNMİYOR",
                "investor_type": "Hayalet",
                "analysis": "Bu cüzdan sessizliğin kendisi. Veri yok.",
            }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": self._build_prompt(wallet_address, transactions)},
            ],
            "temperature": 0.85,
            "max_tokens": 1024,
            "response_format": {"type": "json_object"},
        }

        try:
            response = requests.post(
                self.endpoint, headers=headers, json=payload, timeout=30
            )

            if not response.ok:
                print(f"[DEBUG] Status: {response.status_code}")
                print(f"[DEBUG] Yanıt: {response.text}")
                response.raise_for_status()

            text = response.json()["choices"][0]["message"]["content"].strip()
            return json.loads(text)

        except json.JSONDecodeError as e:
            raise RuntimeError(f"JSON parse hatası: {e}")
        except (requests.exceptions.RequestException, KeyError) as e:
            raise RuntimeError(f"AI Analiz hatası: {e}")