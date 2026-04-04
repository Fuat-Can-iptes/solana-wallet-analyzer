# core/watcher.py

from PyQt6.QtCore import QTimer, QObject, pyqtSignal
from core.solana_fetcher import SolanaDataFetcher
from core.history_manager import HistoryManager

try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False

POLL_INTERVAL_MS = 60_000  # 60 saniye


class WalletWatcher(QObject):
    """
    Takip edilen cüzdanları QTimer ile her 60 saniyede bir kontrol eder.
    Yeni işlem geldiğinde new_transaction sinyali yayar.
    """

    new_transaction = pyqtSignal(str)  # cüzdan adresi

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fetcher  = SolanaDataFetcher()
        self.history  = HistoryManager()
        self.watched  = set()

        self.timer = QTimer(self)
        self.timer.setInterval(POLL_INTERVAL_MS)
        self.timer.timeout.connect(self._poll)

    def watch(self, wallet: str):
        self.watched.add(wallet)
        self.history.set_watched(wallet, True)
        if not self.timer.isActive():
            self.timer.start()

    def unwatch(self, wallet: str):
        self.watched.discard(wallet)
        self.history.set_watched(wallet, False)
        if not self.watched:
            self.timer.stop()

    def is_watching(self, wallet: str) -> bool:
        return wallet in self.watched

    def _poll(self):
        for wallet in list(self.watched):
            try:
                latest = self.fetcher.get_latest_signature(wallet)
                saved  = self.history.get_last_signature(wallet)

                if latest and latest != saved:
                    self.history.update_last_signature(wallet, latest)
                    self._notify(wallet)
                    self.new_transaction.emit(wallet)

            except Exception:
                pass

    def _notify(self, wallet: str):
        short = wallet[:8] + "..."
        if PLYER_AVAILABLE:
            try:
                notification.notify(
                    title="Solana Cüzdan Hareketi",
                    message=f"{short} adresinde yeni işlem tespit edildi!",
                    app_name="Solana Analyzer",
                    timeout=5,
                )
            except Exception:
                pass