# core/blinks_builder.py

from config.settings import IS_DEVNET


class BlinksBuilder:
    """
    Analiz sonucuna göre tıklanabilir Solana aksiyonları üretir.
    Gerçek bir Blink sunucusu kurmak yerine, aksiyon URL'lerini
    Solana Actions formatında hazırlar.
    """

    JUPITER_SWAP = "https://jup.ag/swap"
    MARINADE_STAKE = "https://marinade.finance/app/stake"
    DEVNET_FAUCET = "https://faucet.solana.com/"

    def build_actions(
        self,
        risk_level: str,
        recommendations: list[dict],
        wallet: str | None = None,
    ) -> list[dict]:
        """
        Risk seviyesine göre aksiyonlar üretir.
        Dönen format: [{"label": "...", "url": "...", "type": "..."}, ...]
        """
        if IS_DEVNET:
            actions = [
                {
                    "label": "🚰 Devnet Faucet",
                    "description": "Test SOL al (Solana resmi musluk)",
                    "url": self.DEVNET_FAUCET,
                    "type": "faucet",
                },
            ]
            if wallet:
                actions.append({
                    "label": "🔍 Explorer (Devnet)",
                    "description": "Cüzdanı Solana Explorer'da aç",
                    "url": (
                        f"https://explorer.solana.com/address/{wallet}"
                        f"?cluster=devnet"
                    ),
                    "type": "explorer",
                })
            actions.append({
                "label": "📚 Devnet cluster bilgisi",
                "description": "Resmi Solana dokümantasyonu",
                "url": "https://docs.solana.com/clusters/devnet",
                "type": "help",
            })
            return actions

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
        if IS_DEVNET:
            if action_type == "faucet":
                return self.DEVNET_FAUCET
            return (
                f"https://explorer.solana.com/address/{wallet}"
                f"?cluster=devnet"
            )
        if action_type == "stake":
            return (
                f"solana-action:https://marinade.finance/api/stake"
                f"?wallet={wallet}"
            )
        if action_type == "swap":
            return (
                "solana-action:https://jup.ag/api/swap?"
                "inputMint=So11111111111111111111111111111111111111112&"
                "outputMint=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
            )
        return ""
