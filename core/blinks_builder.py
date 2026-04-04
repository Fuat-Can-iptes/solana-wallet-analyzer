# core/blinks_builder.py

import base64
import json
import requests
from config.settings import HELIUS_RPC_URL


class BlinksBuilder:
    """
    Analiz sonucuna göre tıklanabilir Solana aksiyonları üretir.
    Gerçek bir Blink sunucusu kurmak yerine, aksiyon URL'lerini
    Solana Actions formatında hazırlar.
    """

    JUPITER_SWAP = "https://jup.ag/swap"
    MARINADE_STAKE = "https://marinade.finance/app/stake"

    def build_actions(self, risk_level: str,
                      recommendations: list[dict]) -> list[dict]:
        """
        Risk seviyesine göre aksiyonlar üretir.
        Dönen format: [{"label": "...", "url": "...", "type": "..."}, ...]
        """
        actions = []
        risk = risk_level.upper()

        if risk in ("YÜKSEK", "KRİTİK"):
            actions.append({
                "label":       "🛡 USDC'ye Swap Et",
                "description": "Riski azaltmak için stablecoin'e geç",
                "url":         f"{self.JUPITER_SWAP}/SOL-USDC",
                "type":        "swap",
            })

        if risk in ("DÜŞÜK", "ORTA"):
            actions.append({
                "label":       "🥩 SOL Stake Et",
                "description": "Düşük riskli cüzdan için stake getirisi",
                "url":         self.MARINADE_STAKE,
                "type":        "stake",
            })

        actions.append({
            "label":       "🔄 Jupiter'da İşlem Yap",
            "description": "Solana'nın en büyük DEX aggregator'ı",
            "url":         f"{self.JUPITER_SWAP}",
            "type":        "swap",
        })

        return actions

    def get_onchain_action_url(self, wallet: str, action_type: str) -> str:
        """
        Solana Actions standardına uygun URL üretir.
        Bu URL bir Blink olarak paylaşılabilir.
        """
        if action_type == "stake":
            return f"solana-action:https://marinade.finance/api/stake?wallet={wallet}"
        elif action_type == "swap":
            return f"solana-action:https://jup.ag/api/swap?inputMint=So11111111111111111111111111111111111111112&outputMint=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        return ""