# main.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLineEdit, QLabel, QTextEdit, QTableWidget,
    QTableWidgetItem, QListWidget, QListWidgetItem, QFileDialog,
    QMessageBox, QSplitter, QFrame, QHeaderView
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor

from core.worker import AnalysisWorker
from core.history_manager import HistoryManager
from core.watcher import WalletWatcher
from core.exporter import Exporter

QSS_FILE = "assets/styles/dark_theme.qss"


class MainApp(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Destekli Solana Cüzdan Analizcisi")
        self.resize(1200, 750)

        self.history   = HistoryManager()
        self.watcher   = WalletWatcher(self)
        self.exporter  = Exporter()
        self.worker    = None
        self.current_wallet   = None
        self.current_result   = None
        self.current_portfolio = []

        self._apply_styles()
        self._build_ui()
        self._connect_signals()
        self._load_sidebar()

    # ------------------------------------------------------------------ #
    #  UI Kurulumu                                                         #
    # ------------------------------------------------------------------ #
    def _apply_styles(self):
        try:
            with open(QSS_FILE, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            pass

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter)

        # ── Sol Panel (Sidebar) ────────────────────────────────────────
        sidebar = QFrame()
        sidebar.setFixedWidth(260)
        sidebar.setObjectName("sidebar")
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(12, 12, 12, 12)
        sb_layout.setSpacing(8)

        sb_title = QLabel("📋 GEÇMİŞ")
        sb_title.setObjectName("sectionHeader")
        sb_layout.addWidget(sb_title)

        self.wallet_input = QLineEdit()
        self.wallet_input.setPlaceholderText("Cüzdan adresi girin...")
        sb_layout.addWidget(self.wallet_input)

        self.analyze_button = QPushButton("ANALİZ ET")
        sb_layout.addWidget(self.analyze_button)

        self.sidebar_list = QListWidget()
        self.sidebar_list.setObjectName("sidebarList")
        sb_layout.addWidget(self.sidebar_list)

        splitter.addWidget(sidebar)

        # ── Sağ Panel (Ana İçerik) ────────────────────────────────────
        right = QFrame()
        right.setObjectName("rightPanel")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(20, 16, 20, 16)
        right_layout.setSpacing(10)

        # Üst bar
        top_bar = QHBoxLayout()

        self.wallet_title = QLabel("Bir cüzdan seçin veya analiz edin")
        self.wallet_title.setObjectName("walletTitle")
        top_bar.addWidget(self.wallet_title)

        top_bar.addStretch()

        self.watch_button = QPushButton("👁 Takip Et")
        self.watch_button.setObjectName("secondaryBtn")
        self.watch_button.setEnabled(False)
        top_bar.addWidget(self.watch_button)

        self.refresh_button = QPushButton("🔄 Yenile")
        self.refresh_button.setObjectName("secondaryBtn")
        self.refresh_button.setEnabled(False)
        top_bar.addWidget(self.refresh_button)

        self.export_txt_button = QPushButton("⬇ TXT")
        self.export_txt_button.setObjectName("secondaryBtn")
        self.export_txt_button.setEnabled(False)
        top_bar.addWidget(self.export_txt_button)

        self.export_pdf_button = QPushButton("⬇ PDF")
        self.export_pdf_button.setObjectName("secondaryBtn")
        self.export_pdf_button.setEnabled(False)
        top_bar.addWidget(self.export_pdf_button)

        right_layout.addLayout(top_bar)

        # Risk / Yatırımcı satırı
        info_bar = QHBoxLayout()

        risk_box = QVBoxLayout()
        risk_lbl = QLabel("RİSK SEVİYESİ")
        risk_lbl.setObjectName("sectionHeader")
        self.risk_label = QLabel("—")
        self.risk_label.setObjectName("risk_label")
        risk_box.addWidget(risk_lbl)
        risk_box.addWidget(self.risk_label)
        info_bar.addLayout(risk_box)

        info_bar.addSpacing(40)

        inv_box = QVBoxLayout()
        inv_lbl = QLabel("YATIRIMC TİPİ")
        inv_lbl.setObjectName("sectionHeader")
        self.investor_label = QLabel("—")
        self.investor_label.setObjectName("investor_label")
        inv_box.addWidget(inv_lbl)
        inv_box.addWidget(self.investor_label)
        info_bar.addLayout(inv_box)

        info_bar.addStretch()
        right_layout.addLayout(info_bar)

        # Analiz metni
        analysis_lbl = QLabel("ANALİZ & TAVSİYELER")
        analysis_lbl.setObjectName("sectionHeader")
        right_layout.addWidget(analysis_lbl)

        self.analysis_text = QTextEdit()
        self.analysis_text.setReadOnly(True)
        self.analysis_text.setMinimumHeight(180)
        right_layout.addWidget(self.analysis_text)

        # Portföy tablosu
        portfolio_lbl = QLabel("TOKEN PORTFÖYÜ")
        portfolio_lbl.setObjectName("sectionHeader")
        right_layout.addWidget(portfolio_lbl)

        self.portfolio_table = QTableWidget(0, 2)
        self.portfolio_table.setHorizontalHeaderLabels(["Token", "Miktar"])
        self.portfolio_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.portfolio_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.portfolio_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.portfolio_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.portfolio_table.setMinimumHeight(160)
        right_layout.addWidget(self.portfolio_table)

        # Durum çubuğu
        self.status_label = QLabel("")
        self.status_label.setObjectName("status_label")
        right_layout.addWidget(self.status_label)

        splitter.addWidget(right)
        splitter.setSizes([260, 940])

    def _connect_signals(self):
        self.analyze_button.clicked.connect(self._on_analyze_clicked)
        self.wallet_input.returnPressed.connect(self._on_analyze_clicked)
        self.sidebar_list.itemClicked.connect(self._on_sidebar_clicked)
        self.refresh_button.clicked.connect(self._on_refresh_clicked)
        self.watch_button.clicked.connect(self._on_watch_clicked)
        self.export_txt_button.clicked.connect(self._on_export_txt)
        self.export_pdf_button.clicked.connect(self._on_export_pdf)
        self.watcher.new_transaction.connect(self._on_new_transaction)

    # ------------------------------------------------------------------ #
    #  Sidebar                                                             #
    # ------------------------------------------------------------------ #
    def _load_sidebar(self):
        self.sidebar_list.clear()
        for entry in self.history.get_all_wallets():
            wallet = entry["wallet"]
            ts     = entry.get("timestamp", "")
            risk   = entry.get("result", {}).get("risk_level", "?")
            item   = QListWidgetItem(f"{wallet[:12]}...\n{ts}  [{risk}]")
            item.setData(Qt.ItemDataRole.UserRole, wallet)
            item.setSizeHint(QSize(0, 52))
            self.sidebar_list.addItem(item)

    def _on_sidebar_clicked(self, item: QListWidgetItem):
        wallet = item.data(Qt.ItemDataRole.UserRole)
        entry  = self.history.get_analysis(wallet)
        if entry:
            self.current_wallet    = wallet
            self.current_result    = entry["result"]
            self.current_portfolio = entry.get("portfolio", [])
            self._render_result(
                wallet,
                self.current_result,
                self.current_portfolio,
            )
            self._set_status("📂 Önbellekten yüklendi — güncellemek için Yenile'ye bas.")

    # ------------------------------------------------------------------ #
    #  Analiz Başlat                                                       #
    # ------------------------------------------------------------------ #
    def _on_analyze_clicked(self):
        wallet = self.wallet_input.text().strip()
        if not wallet:
            self._set_status("⚠️ Lütfen bir cüzdan adresi girin.")
            return
        if len(wallet) < 32:
            self._set_status("⚠️ Geçersiz Solana adresi.")
            return
        self.current_wallet = wallet
        self._start_worker(wallet)

    def _on_refresh_clicked(self):
        if self.current_wallet:
            self._start_worker(self.current_wallet)

    def _start_worker(self, wallet: str):
        self._set_ui_loading(True)
        self.worker = AnalysisWorker(wallet_address=wallet)
        self.worker.finished.connect(self._on_analysis_complete)
        self.worker.error.connect(self._on_analysis_error)
        self.worker.progress.connect(self._set_status)
        self.worker.start()

    # ------------------------------------------------------------------ #
    #  Analiz Tamamlandı                                                   #
    # ------------------------------------------------------------------ #
    def _on_analysis_complete(self, result: dict, portfolio: list):
        self._set_ui_loading(False)
        self.current_result    = result
        self.current_portfolio = portfolio

        self.history.save_analysis(self.current_wallet, result, portfolio)

        sig = None
        try:
            from core.solana_fetcher import SolanaDataFetcher
            sig = SolanaDataFetcher().get_latest_signature(self.current_wallet)
        except Exception:
            pass
        if sig:
            self.history.update_last_signature(self.current_wallet, sig)

        self._render_result(self.current_wallet, result, portfolio)
        self._load_sidebar()

    def _render_result(self, wallet: str, result: dict, portfolio: list):
        self.wallet_title.setText(f"🔍 {wallet[:20]}...")
        self.refresh_button.setEnabled(True)
        self.watch_button.setEnabled(True)
        self.export_txt_button.setEnabled(True)
        self.export_pdf_button.setEnabled(True)

        # Watch butonu güncelle
        if self.watcher.is_watching(wallet):
            self.watch_button.setText("👁 Takibi Bırak")
        else:
            self.watch_button.setText("👁 Takip Et")

        # Risk etiketi
        risk = result.get("risk_level", "?")
        self.risk_label.setText(risk)
        risk_colors = {
            "DÜŞÜK":  "color: #14f195;",
            "ORTA":   "color: #ffcc00;",
            "YÜKSEK": "color: #ff6600;",
            "KRİTİK": "color: #ff3355;",
        }
        self.risk_label.setStyleSheet(
            risk_colors.get(risk.upper(), "color: #ffffff;")
        )
        self.investor_label.setText(result.get("investor_type", "?"))

        # Analiz metni
        full_text  = f"📊 ANALİZ\n{result.get('analysis', '')}\n\n"
        full_text += "💡 TAVSİYELER\n" + "─" * 40 + "\n"
        for i, rec in enumerate(result.get("recommendations", []), 1):
            full_text += (
                f"\n{i}. {rec.get('action', '')}\n"
                f"   Neden : {rec.get('reason', '')}\n"
                f"   Risk  : {rec.get('risk', '')}\n"
            )
        self.analysis_text.setPlainText(full_text)

        # Portföy tablosu
        self.portfolio_table.setRowCount(0)
        for token in portfolio:
            row = self.portfolio_table.rowCount()
            self.portfolio_table.insertRow(row)
            self.portfolio_table.setItem(row, 0, QTableWidgetItem(token["name"]))
            amt_item = QTableWidgetItem(f"{token['amount']:,.4f}")
            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight |
                                      Qt.AlignmentFlag.AlignVCenter)
            self.portfolio_table.setItem(row, 1, amt_item)

    # ------------------------------------------------------------------ #
    #  Takip                                                               #
    # ------------------------------------------------------------------ #
    def _on_watch_clicked(self):
        if not self.current_wallet:
            return
        if self.watcher.is_watching(self.current_wallet):
            self.watcher.unwatch(self.current_wallet)
            self.watch_button.setText("👁 Takip Et")
            self._set_status("Takip durduruldu.")
        else:
            self.watcher.watch(self.current_wallet)
            self.watch_button.setText("👁 Takibi Bırak")
            self._set_status("✅ Takip başladı — 60 saniyede bir kontrol edilecek.")

    def _on_new_transaction(self, wallet: str):
        self._set_status(f"🔔 {wallet[:12]}... adresinde yeni işlem!")

    # ------------------------------------------------------------------ #
    #  Dışa Aktar                                                          #
    # ------------------------------------------------------------------ #
    def _on_export_txt(self):
        if not self.current_result:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "TXT olarak kaydet", f"{self.current_wallet[:8]}_analiz.txt",
            "Text Files (*.txt)"
        )
        if path:
            self.exporter.export_txt(
                self.current_wallet, self.current_result,
                self.current_portfolio, path
            )
            self._set_status(f"✅ TXT kaydedildi: {path}")

    def _on_export_pdf(self):
        if not self.current_result:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "PDF olarak kaydet", f"{self.current_wallet[:8]}_analiz.pdf",
            "PDF Files (*.pdf)"
        )
        if path:
            try:
                self.exporter.export_pdf(
                    self.current_wallet, self.current_result,
                    self.current_portfolio, path
                )
                self._set_status(f"✅ PDF kaydedildi: {path}")
            except RuntimeError as e:
                QMessageBox.critical(self, "Hata", str(e))

    # ------------------------------------------------------------------ #
    #  Hata                                                                #
    # ------------------------------------------------------------------ #
    def _on_analysis_error(self, error_msg: str):
        self._set_ui_loading(False)
        self._set_status(f"❌ {error_msg}")
        QMessageBox.critical(self, "Hata", error_msg)

    # ------------------------------------------------------------------ #
    #  Yardımcılar                                                         #
    # ------------------------------------------------------------------ #
    def _set_ui_loading(self, loading: bool):
        self.analyze_button.setEnabled(not loading)
        self.wallet_input.setEnabled(not loading)
        self.refresh_button.setEnabled(not loading)
        if loading:
            self.analyze_button.setText("Analiz Ediliyor...")
            self.risk_label.setText("—")
            self.investor_label.setText("—")
            self.analysis_text.clear()
            self.portfolio_table.setRowCount(0)
        else:
            self.analyze_button.setText("ANALİZ ET")

    def _set_status(self, message: str):
        self.status_label.setText(message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())