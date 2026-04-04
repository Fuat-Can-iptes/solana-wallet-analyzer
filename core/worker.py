# core/worker.py

from PyQt6.QtCore import QThread, pyqtSignal
from core.solana_fetcher import SolanaDataFetcher
from core.ai_analyzer import AIAnalyzer


class AnalysisWorker(QThread):

    finished  = pyqtSignal(dict, list)  # result, portfolio
    error     = pyqtSignal(str)
    progress  = pyqtSignal(str)

    def __init__(self, wallet_address: str):
        super().__init__()
        self.wallet_address = wallet_address
        self.fetcher        = SolanaDataFetcher()
        self.analyzer       = AIAnalyzer()

    def run(self):
        try:
            self.progress.emit("🔗 Solana ağına bağlanılıyor...")
            transactions = self.fetcher.get_clean_transactions(self.wallet_address)

            self.progress.emit("💼 Token portföyü çekiliyor...")
            try:
                portfolio = self.fetcher.get_token_balances(self.wallet_address)
            except Exception:
                portfolio = []

            self.progress.emit(f"🤖 {len(transactions)} işlem AI'ya gönderiliyor...")
            result = self.analyzer.analyze(self.wallet_address, transactions)

            self.progress.emit("✅ Analiz tamamlandı.")
            self.finished.emit(result, portfolio)

        except ConnectionError as e:
            self.error.emit(f"Bağlantı Hatası: {e}")
        except RuntimeError as e:
            self.error.emit(f"AI Hatası: {e}")
        except Exception as e:
            self.error.emit(f"Beklenmedik hata: {e}")