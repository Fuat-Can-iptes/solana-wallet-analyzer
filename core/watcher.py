# core/watcher.py

from PyQt6.QtCore import QTimer, QObject, pyqtSignal
from PyQt6.QtWidgets import QStyle, QSystemTrayIcon

from config.settings import WATCH_POLL_INTERVAL_MS
from core.history_manager import HistoryManager
from core.solana_fetcher import SolanaDataFetcher

try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False


class WalletWatcher(QObject):
    """
    Takip edilen cüzdanları periyodik olarak kontrol eder.
    Yeni işlem geldiğinde new_transaction sinyali ve masaüstü bildirimi.
    """

    new_transaction = pyqtSignal(str)  # cüzdan adresi

    def __init__(self, parent=None, tray_icon: QSystemTrayIcon | None = None):
        super().__init__(parent)
        self.fetcher = SolanaDataFetcher()
        self.history = HistoryManager()
        self.watched = set()
        self._tray = tray_icon

        self.timer = QTimer(self)
        self.timer.setInterval(WATCH_POLL_INTERVAL_MS)
        self.timer.timeout.connect(self._poll)

    def set_tray_icon(self, tray: QSystemTrayIcon | None):
        self._tray = tray

    def watch(self, wallet: str):
        self.watched.add(wallet)
        self.history.set_watched(wallet, True)
        if self.history.get_last_signature(wallet) is None:
            self._baseline_signature(wallet)
        if not self.timer.isActive():
            self.timer.start()

    def unwatch(self, wallet: str):
        self.watched.discard(wallet)
        self.history.set_watched(wallet, False)
        if not self.watched:
            self.timer.stop()

    def is_watching(self, wallet: str) -> bool:
        return wallet in self.watched

    def _baseline_signature(self, wallet: str):
        """İlk takipte mevcut son imzayı kaydet; yanlış 'yeni işlem' bildirimini önler."""
        try:
            latest = self.fetcher.get_latest_signature(wallet)
            if latest:
                self.history.update_last_signature(wallet, latest)
        except Exception:
            pass

    def _poll(self):
        for wallet in list(self.watched):
            try:
                latest = self.fetcher.get_latest_signature(wallet)
                saved = self.history.get_last_signature(wallet)

                if latest and latest != saved:
                    self.history.update_last_signature(wallet, latest)
                    self._notify(wallet)
                    self.new_transaction.emit(wallet)

            except Exception:
                pass

    def _notify(self, wallet: str):
        short = wallet[:8] + "..."
        title = "Solana Cüzdan Hareketi"
        message = f"{short} adresinde yeni işlem tespit edildi!"

        if PLYER_AVAILABLE:
            try:
                notification.notify(
                    title=title,
                    message=message,
                    app_name="Solana Analyzer",
                    timeout=5,
                )
            except Exception:
                pass

        if (
            self._tray
            and self._tray.isVisible()
            and QSystemTrayIcon.supportsMessages()
        ):
            self._tray.showMessage(
                title,
                message,
                QSystemTrayIcon.MessageIcon.Information,
                5000,
            )


def tray_icon_for_app(parent) -> QSystemTrayIcon | None:
    """Windows dahil masaüstü bildirimi için tepsi simgesi (görünür olmalı)."""
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return None
    tray = QSystemTrayIcon(parent)
    style = parent.style()
    if style is not None:
        tray.setIcon(
            style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
        )
    tray.setToolTip("Solana Cüzdan Analizcisi")
    tray.show()
    return tray
