# core/worker.py

from PyQt6.QtCore import QThread, pyqtSignal

from config.settings import IS_DEVNET, SOLANA_CLUSTER_LABEL
from core.solana_fetcher import SolanaDataFetcher
from core.ai_analyzer import AIAnalyzer
from core.price_fetcher import PriceFetcher
from core.pnl_calculator import PnLCalculator


class AnalysisWorker(QThread):

    finished = pyqtSignal(dict, list, dict)  # result, portfolio, pnl
    error    = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, wallet_address: str):
        super().__init__()
        self.wallet_address = wallet_address
        self.fetcher        = SolanaDataFetcher()
        self.analyzer       = AIAnalyzer()
        self.pricer         = PriceFetcher()
        self.pnl_calc       = PnLCalculator()

    def run(self):
        try:
            self.progress.emit(
                f"🔗 {SOLANA_CLUSTER_LABEL} ağına bağlanılıyor..."
            )
            transactions = self.fetcher.get_clean_transactions(self.wallet_address)

            self.progress.emit("💼 Token portföyü çekiliyor...")
            try:
                raw_portfolio = self.fetcher.get_token_balances(self.wallet_address)
            except Exception:
                raw_portfolio = []

            self.progress.emit(
                "💰 Devnet: USD fiyat atlanıyor..."
                if IS_DEVNET
                else "💰 Fiyat verileri alınıyor..."
            )
            try:
                portfolio = self.pricer.enrich_portfolio(raw_portfolio)
            except Exception:
                portfolio = raw_portfolio

            self.progress.emit("📊 PnL hesaplanıyor...")
            try:
                pnl = self.pnl_calc.calculate(transactions, portfolio)
            except Exception:
                pnl = {}

            total_usd = sum(t.get("usd_value", 0) for t in portfolio)

            self.progress.emit(f"🤖 {len(transactions)} işlem AI'ya gönderiliyor...")
            result = self.analyzer.analyze(
                self.wallet_address, transactions, portfolio, total_usd
            )

            self.progress.emit("✅ Analiz tamamlandı.")
            self.finished.emit(result, portfolio, pnl)

        except ConnectionError as e:
            self.error.emit(f"Bağlantı Hatası: {e}")
        except RuntimeError as e:
            self.error.emit(f"AI Hatası: {e}")
        except Exception as e:
            self.error.emit(f"Beklenmedik hata: {e}")