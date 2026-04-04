# main.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLineEdit, QLabel, QTextEdit, QTableWidget,
    QTableWidgetItem, QListWidget, QListWidgetItem, QFileDialog,
    QMessageBox, QSplitter, QFrame, QHeaderView, QDialog,
    QDialogButtonBox, QGridLayout, QInputDialog, QSizePolicy,
)
from PyQt6.QtCore import Qt, QSize, QUrl, QObject, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices

from config.settings import SOLANA_CLUSTER_LABEL
from core.worker import AnalysisWorker
from core.history_manager import HistoryManager
from core.watcher import WalletWatcher, tray_icon_for_app
from core.exporter import Exporter
from core.blinks_builder import BlinksBuilder
from core.chart_widget import PortfolioPieChart
from core.compare_summary import build_wallet_comparison_report
from core.portfolio_utils import portfolio_summary_line, safe_token_row
from core.wallet_book import WalletBook, is_valid_solana_address
from core.wallet_connect_server import (
    start_wallet_connect_server,
    stop_wallet_connect_server,
)

QSS_FILE = "assets/styles/dark_theme.qss"


class PhantomBridge(QObject):
    """HTTP thread → GUI thread (Phantom public key)."""

    received = pyqtSignal(str)


class CompareDialog(QDialog):
    """İki cüzdanı yan yana karşılaştırma penceresi."""

    def __init__(self, wallet_a: str, result_a: dict, portfolio_a: list,
                 wallet_b: str, result_b: dict, portfolio_b: list,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cüzdan Karşılaştırma")
        self.resize(1150, 820)
        self._build(wallet_a, result_a, portfolio_a,
                    wallet_b, result_b, portfolio_b)

    def _column(self, wallet: str, result: dict, portfolio: list) -> QFrame:
        frame = QFrame()
        frame.setObjectName("rightPanel")
        vl = QVBoxLayout(frame)
        vl.setSpacing(8)

        title = QLabel(f"🔍 {wallet}")
        title.setObjectName("walletTitle")
        title.setWordWrap(True)
        vl.addWidget(title)

        risk = result.get("risk_level", "?")
        risk_lbl = QLabel(f"Risk: {risk}")
        risk_lbl.setObjectName("risk_label")
        risk_colors = {
            "DÜŞÜK": "color:#14f195;",
            "ORTA": "color:#ffcc00;",
            "YÜKSEK": "color:#ff6600;",
            "KRİTİK": "color:#ff3355;",
        }
        risk_lbl.setStyleSheet(
            risk_colors.get(risk.upper(), "color:#fff;")
        )
        vl.addWidget(risk_lbl)

        inv_lbl = QLabel(result.get("investor_type", "?"))
        inv_lbl.setObjectName("investor_label")
        inv_lbl.setWordWrap(True)
        vl.addWidget(inv_lbl)

        sum_lbl = QLabel(portfolio_summary_line(portfolio))
        sum_lbl.setObjectName("status_label")
        sum_lbl.setWordWrap(True)
        vl.addWidget(sum_lbl)

        chart = PortfolioPieChart()
        chart.setMinimumHeight(260)
        chart.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        chart.update_chart(portfolio)
        vl.addWidget(chart)

        rec_hdr = QLabel("Öne çıkan tavsiyeler")
        rec_hdr.setObjectName("sectionHeader")
        vl.addWidget(rec_hdr)
        rec_lines = []
        for i, rec in enumerate(result.get("recommendations", [])[:3], 1):
            rec_lines.append(
                f"{i}. {rec.get('action', '')} "
                f"({rec.get('risk', '')})"
            )
        rec_body = "\n".join(rec_lines) if rec_lines else "—"
        rec_lbl = QLabel(rec_body)
        rec_lbl.setWordWrap(True)
        rec_lbl.setObjectName("status_label")
        vl.addWidget(rec_lbl)

        ana_hdr = QLabel("Analiz özeti")
        ana_hdr.setObjectName("sectionHeader")
        vl.addWidget(ana_hdr)

        analysis = QTextEdit()
        analysis.setReadOnly(True)
        analysis.setPlainText(result.get("analysis", "") or "—")
        analysis.setMinimumHeight(180)
        vl.addWidget(analysis, stretch=1)

        return frame

    def _build(self, wa, ra, pa, wb, rb, pb):
        root = QVBoxLayout(self)

        verdict_hdr = QLabel("⚖ İKİ CÜZDAN: KİM NEREDE DAHA İYİ / DAHA ZAYIF?")
        verdict_hdr.setObjectName("sectionHeader")
        root.addWidget(verdict_hdr)

        verdict_box = QTextEdit()
        verdict_box.setReadOnly(True)
        verdict_box.setPlainText(
            build_wallet_comparison_report(wa, ra, pa, wb, rb, pb)
        )
        verdict_box.setMinimumHeight(200)
        verdict_box.setMaximumHeight(280)
        verdict_box.setObjectName("compareVerdict")
        root.addWidget(verdict_box)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(self._column(wa, ra, pa))
        split.addWidget(self._column(wb, rb, pb))
        split.setSizes([560, 560])
        root.addWidget(split)

        bbox = QDialogButtonBox()
        close_btn = bbox.addButton(
            "Kapat", QDialogButtonBox.ButtonRole.AcceptRole
        )
        close_btn.clicked.connect(self.accept)
        root.addWidget(bbox)


class MainApp(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle(
            f"AI Destekli Solana Cüzdan Analizcisi — {SOLANA_CLUSTER_LABEL}"
        )
        self.resize(1300, 800)

        self.history            = HistoryManager()
        self.wallet_book        = WalletBook()
        self.exporter           = Exporter()
        self.blinks             = BlinksBuilder()
        self._phantom_bridge    = PhantomBridge(self)
        self._wallet_connect_server = None
        self.worker             = None
        self.compare_worker     = None
        self.current_wallet     = None
        self.current_result     = None
        self.current_portfolio  = []
        self.current_pnl        = {}
        self._tray_icon         = None
        self.watcher            = None

        self._apply_styles()
        self._build_ui()
        self._tray_icon = tray_icon_for_app(self)
        self.watcher = WalletWatcher(self, tray_icon=self._tray_icon)
        self._connect_signals()
        self._load_wallet_book_list()
        self._load_sidebar()
        self._restore_watched_wallets()

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
        sidebar.setFixedWidth(300)
        sidebar.setObjectName("sidebar")
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(12, 12, 12, 12)
        sb_layout.setSpacing(8)

        book_title = QLabel("👛 KAYITLI CÜZDANLAR")
        book_title.setObjectName("sectionHeader")
        sb_layout.addWidget(book_title)

        self.wallet_book_list = QListWidget()
        self.wallet_book_list.setObjectName("sidebarList")
        self.wallet_book_list.setMaximumHeight(130)
        self.wallet_book_list.setToolTip(
            "Tek tık: adrese yükle · Çift tık: doğrudan analiz"
        )
        sb_layout.addWidget(self.wallet_book_list)

        book_btns_a = QHBoxLayout()
        self.phantom_connect_btn = QPushButton("🔗 Phantom")
        self.phantom_connect_btn.setObjectName("secondaryBtn")
        self.phantom_connect_btn.setToolTip(
            "Chrome/Brave’de açılır; Phantom ile onay (yalnızca public key)"
        )
        self.clipboard_wallet_btn = QPushButton("📋 Panodan")
        self.clipboard_wallet_btn.setObjectName("secondaryBtn")
        book_btns_a.addWidget(self.phantom_connect_btn)
        book_btns_a.addWidget(self.clipboard_wallet_btn)
        sb_layout.addLayout(book_btns_a)

        book_btns_b = QHBoxLayout()
        self.add_wallet_btn = QPushButton("➕ Adres ekle")
        self.add_wallet_btn.setObjectName("secondaryBtn")
        self.remove_wallet_btn = QPushButton("🗑 Kaldır")
        self.remove_wallet_btn.setObjectName("secondaryBtn")
        book_btns_b.addWidget(self.add_wallet_btn)
        book_btns_b.addWidget(self.remove_wallet_btn)
        sb_layout.addLayout(book_btns_b)

        sb_hint = QLabel("veya herhangi bir adres yazın ↓")
        sb_hint.setObjectName("status_label")
        sb_layout.addWidget(sb_hint)

        sb_title = QLabel("📋 ANALİZ GEÇMİŞİ")
        sb_title.setObjectName("sectionHeader")
        sb_layout.addWidget(sb_title)

        self.wallet_input = QLineEdit()
        self.wallet_input.setPlaceholderText("Cüzdan adresi (manuel veya yukarıdan)...")
        sb_layout.addWidget(self.wallet_input)

        btn_row = QHBoxLayout()
        self.analyze_button = QPushButton("ANALİZ ET")
        btn_row.addWidget(self.analyze_button)
        sb_layout.addLayout(btn_row)

        self.compare_button = QPushButton("🔀 Karşılaştır")
        self.compare_button.setObjectName("secondaryBtn")
        self.compare_button.setEnabled(False)
        self.compare_button.setToolTip(
            "Aktif cüzdanı başka bir analiz ile karşılaştır. "
            "Geçmişte satır seçili değilse liste açılır."
        )
        sb_layout.addWidget(self.compare_button)

        self.sidebar_list = QListWidget()
        self.sidebar_list.setObjectName("sidebarList")
        sb_layout.addWidget(self.sidebar_list)

        splitter.addWidget(sidebar)

        # ── Sağ Panel ─────────────────────────────────────────────────
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

        for attr, label in [
            ("watch_button",      "👁 Takip Et"),
            ("refresh_button",    "🔄 Yenile"),
            ("export_txt_button", "⬇ TXT"),
            ("export_pdf_button", "⬇ PDF"),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("secondaryBtn")
            btn.setEnabled(False)
            setattr(self, attr, btn)
            top_bar.addWidget(btn)

        right_layout.addLayout(top_bar)

        # Risk / Yatırımcı + Pasta grafik yan yana
        mid_row = QHBoxLayout()

        # Sol: Risk + Yatırımcı + Analiz
        left_col = QVBoxLayout()

        info_bar = QHBoxLayout()
        risk_box = QVBoxLayout()
        risk_box.addWidget(self._section_label("RİSK SEVİYESİ"))
        self.risk_label = QLabel("—")
        self.risk_label.setObjectName("risk_label")
        risk_box.addWidget(self.risk_label)
        info_bar.addLayout(risk_box)
        info_bar.addSpacing(30)

        inv_box = QVBoxLayout()
        inv_box.addWidget(self._section_label("YATIRIMC TİPİ"))
        self.investor_label = QLabel("—")
        self.investor_label.setObjectName("investor_label")
        self.investor_label.setWordWrap(True)
        inv_box.addWidget(self.investor_label)
        info_bar.addLayout(inv_box)

        info_bar.addStretch()
        left_col.addLayout(info_bar)

        left_col.addWidget(self._section_label("ANALİZ & TAVSİYELER"))
        self.analysis_text = QTextEdit()
        self.analysis_text.setReadOnly(True)
        self.analysis_text.setMinimumHeight(200)
        left_col.addWidget(self.analysis_text)

        mid_row.addLayout(left_col, stretch=3)

        # Sağ: Pasta grafik
        pie_col = QVBoxLayout()
        pie_col.addWidget(self._section_label("PORTFÖY DAĞILIMI"))
        self.pie_chart = PortfolioPieChart()
        self.pie_chart.setMinimumSize(300, 240)
        self.pie_chart.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.MinimumExpanding,
        )
        pie_col.addWidget(self.pie_chart)
        pie_col.addStretch()
        mid_row.addLayout(pie_col, stretch=1)

        right_layout.addLayout(mid_row)

        # Portföy tablosu — 5 sütun: Sembol, İsim, Miktar, Fiyat, USD, PnL
        right_layout.addWidget(self._section_label("TOKEN PORTFÖYÜ"))
        self.portfolio_hint = QLabel("")
        self.portfolio_hint.setObjectName("status_label")
        self.portfolio_hint.setWordWrap(True)
        right_layout.addWidget(self.portfolio_hint)

        self.portfolio_table = QTableWidget(0, 6)
        self.portfolio_table.setHorizontalHeaderLabels(
            ["Sembol", "Token", "Miktar", "Fiyat", "USD Değeri", "Tahmini PnL"]
        )
        for i, mode in enumerate([
            QHeaderView.ResizeMode.ResizeToContents,
            QHeaderView.ResizeMode.Stretch,
            QHeaderView.ResizeMode.ResizeToContents,
            QHeaderView.ResizeMode.ResizeToContents,
            QHeaderView.ResizeMode.ResizeToContents,
            QHeaderView.ResizeMode.ResizeToContents,
        ]):
            self.portfolio_table.horizontalHeader().setSectionResizeMode(i, mode)

        self.portfolio_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.portfolio_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.portfolio_table.setMinimumHeight(200)
        self.portfolio_table.setAlternatingRowColors(True)
        self.portfolio_table.verticalHeader().setVisible(False)
        self.portfolio_table.setShowGrid(True)
        right_layout.addWidget(self.portfolio_table)

        # Blinks
        right_layout.addWidget(self._section_label("⚡ ÖNERİLEN AKSİYONLAR"))
        self.actions_frame  = QFrame()
        self.actions_layout = QHBoxLayout(self.actions_frame)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(8)
        right_layout.addWidget(self.actions_frame)

        # Durum
        self.status_label = QLabel("")
        self.status_label.setObjectName("status_label")
        right_layout.addWidget(self.status_label)

        splitter.addWidget(right)
        splitter.setSizes([300, 1000])

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("sectionHeader")
        return lbl

    def _connect_signals(self):
        self.analyze_button.clicked.connect(self._on_analyze_clicked)
        self.wallet_input.returnPressed.connect(self._on_analyze_clicked)
        self.sidebar_list.itemClicked.connect(self._on_sidebar_clicked)
        self.wallet_book_list.itemClicked.connect(self._on_wallet_book_clicked)
        self.wallet_book_list.itemDoubleClicked.connect(
            self._on_wallet_book_double_clicked
        )
        self.phantom_connect_btn.clicked.connect(self._on_phantom_connect_clicked)
        self.clipboard_wallet_btn.clicked.connect(self._on_clipboard_wallet_clicked)
        self.add_wallet_btn.clicked.connect(self._on_add_wallet_book_clicked)
        self.remove_wallet_btn.clicked.connect(self._on_remove_wallet_book_clicked)
        self.refresh_button.clicked.connect(self._on_refresh_clicked)
        self.watch_button.clicked.connect(self._on_watch_clicked)
        self.export_txt_button.clicked.connect(self._on_export_txt)
        self.export_pdf_button.clicked.connect(self._on_export_pdf)
        self.compare_button.clicked.connect(self._on_compare_clicked)
        self.watcher.new_transaction.connect(self._on_new_transaction)
        self._phantom_bridge.received.connect(self._on_phantom_address_received)

    # ------------------------------------------------------------------ #
    #  Sidebar                                                             #
    # ------------------------------------------------------------------ #
    def _load_sidebar(self):
        self.sidebar_list.clear()
        for entry in self.history.get_all_wallets():
            wallet = entry["wallet"]
            ts     = entry.get("timestamp", "")
            risk   = entry.get("result", {}).get("risk_level", "?")
            eye    = "👁 " if entry.get("watched") else ""
            item   = QListWidgetItem(f"{eye}{wallet[:12]}...\n{ts}  [{risk}]")
            item.setData(Qt.ItemDataRole.UserRole, wallet)
            item.setSizeHint(QSize(0, 52))
            self.sidebar_list.addItem(item)

    def _restore_watched_wallets(self):
        """Uygulama yeniden açılınca history.json'daki takipleri sürdür."""
        if not self.watcher:
            return
        for entry in self.history.get_all_wallets():
            if entry.get("watched") and entry.get("wallet"):
                self.watcher.watch(entry["wallet"])

    def _load_wallet_book_list(self):
        self.wallet_book_list.clear()
        for w in self.wallet_book.list_all():
            addr = w.get("address", "")
            lab  = w.get("label", "")
            item = QListWidgetItem(f"{lab}\n{addr[:10]}...{addr[-6:]}")
            item.setData(Qt.ItemDataRole.UserRole, addr)
            item.setSizeHint(QSize(0, 44))
            self.wallet_book_list.addItem(item)

    def _on_wallet_book_clicked(self, item: QListWidgetItem):
        addr = item.data(Qt.ItemDataRole.UserRole)
        if addr:
            self.wallet_input.setText(addr)
            self._set_status("Adres yüklendi — ANALİZ ET ile devam et.")

    def _on_wallet_book_double_clicked(self, item: QListWidgetItem):
        addr = item.data(Qt.ItemDataRole.UserRole)
        if not addr or not is_valid_solana_address(addr):
            return
        self.wallet_input.setText(addr)
        self.current_wallet = addr
        self._start_worker(addr)

    def _stop_wallet_connect_server(self):
        if self._wallet_connect_server is not None:
            stop_wallet_connect_server(self._wallet_connect_server)
            self._wallet_connect_server = None

    def _on_phantom_connect_clicked(self):
        self._stop_wallet_connect_server()

        def on_pk(pk: str) -> bool:
            if not is_valid_solana_address(pk):
                return False
            self._phantom_bridge.received.emit(pk)
            return True

        try:
            self._wallet_connect_server, port = start_wallet_connect_server(
                SOLANA_CLUSTER_LABEL, on_pk
            )
        except OSError as e:
            self._set_status(f"❌ Yerel bağlantı sunucusu açılamadı: {e}")
            return

        QDesktopServices.openUrl(QUrl(f"http://127.0.0.1:{port}/"))
        self._set_status(
            "Tarayıcıda Phantom ile onay ver; adres uygulamaya düşecek. "
            "Aynı ağı (Devnet/Mainnet) seçtiğinden emin ol."
        )

    def _on_phantom_address_received(self, pk: str):
        self._stop_wallet_connect_server()
        if not is_valid_solana_address(pk):
            self._set_status("❌ Geçersiz adres (Phantom yanıtı).")
            return
        self.wallet_book.add(pk, label="Phantom", source="phantom")
        self.wallet_input.setText(pk)
        self._load_wallet_book_list()
        self._set_status(
            "✅ Phantom adresi kaydedildi — ANALİZ ET veya çift tıkla analiz."
        )

    def _on_clipboard_wallet_clicked(self):
        clip = QApplication.clipboard().text().strip()
        if not is_valid_solana_address(clip):
            self._set_status("⚠️ Pano geçerli bir Solana adresi içermiyor.")
            return
        self.wallet_book.add(clip, label="Pano", source="clipboard")
        self.wallet_input.setText(clip)
        self._load_wallet_book_list()
        self._set_status("✅ Panodaki adres deftere eklendi.")

    def _on_add_wallet_book_clicked(self):
        addr, ok = QInputDialog.getText(
            self, "Cüzdan ekle", "Solana adresi (public key):"
        )
        if not ok or not addr.strip():
            return
        addr = addr.strip()
        if not is_valid_solana_address(addr):
            QMessageBox.warning(self, "Adres", "Geçersiz Solana adresi.")
            return
        lab, ok2 = QInputDialog.getText(
            self, "Etiket", "Liste için kısa isim (isteğe bağlı):",
            text="Hesabım",
        )
        label = lab.strip() if ok2 else "Hesabım"
        self.wallet_book.add(addr, label=label or "Hesabım", source="manual")
        self.wallet_input.setText(addr)
        self._load_wallet_book_list()
        self._set_status("✅ Cüzdan kayıtlı listeye eklendi.")

    def _on_remove_wallet_book_clicked(self):
        item = self.wallet_book_list.currentItem()
        if not item:
            self._set_status("⚠️ Kaldırmak için listeden bir satır seç.")
            return
        addr = item.data(Qt.ItemDataRole.UserRole)
        if addr and self.wallet_book.remove(addr):
            self._load_wallet_book_list()
            self._set_status("Kayıtlı listeden kaldırıldı.")

    def closeEvent(self, event):
        self._stop_wallet_connect_server()
        super().closeEvent(event)

    def _on_sidebar_clicked(self, item: QListWidgetItem):
        wallet = item.data(Qt.ItemDataRole.UserRole)
        entry  = self.history.get_analysis(wallet)
        if entry:
            self.current_wallet    = wallet
            self.current_result    = entry["result"]
            self.current_portfolio = entry.get("portfolio", [])
            self.current_pnl       = entry.get("pnl", {})
            self._render_result(
                wallet, self.current_result,
                self.current_portfolio, self.current_pnl
            )
            self.compare_button.setEnabled(True)
            self._set_status("📂 Önbellekten yüklendi — güncellemek için Yenile'ye bas.")

    # ------------------------------------------------------------------ #
    #  Analiz                                                              #
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

    def _on_analysis_complete(self, result: dict, portfolio: list, pnl: dict):
        self._set_ui_loading(False)
        self.current_result    = result
        self.current_portfolio = portfolio
        self.current_pnl       = pnl

        self.history.save_analysis(
            self.current_wallet, result, portfolio, pnl
        )

        try:
            from core.solana_fetcher import SolanaDataFetcher
            sig = SolanaDataFetcher().get_latest_signature(self.current_wallet)
            if sig:
                self.history.update_last_signature(self.current_wallet, sig)
        except Exception:
            pass

        self._render_result(
            self.current_wallet, result, portfolio, pnl
        )
        self.compare_button.setEnabled(True)
        self._load_sidebar()

    # ------------------------------------------------------------------ #
    #  Render                                                              #
    # ------------------------------------------------------------------ #
    def _render_result(self, wallet: str, result: dict,
                       portfolio: list, pnl: dict):
        self.wallet_title.setText(f"🔍 {wallet[:24]}...")
        for btn in [self.refresh_button, self.watch_button,
                    self.export_txt_button, self.export_pdf_button]:
            btn.setEnabled(True)

        if self.watcher.is_watching(wallet):
            self.watch_button.setText("👁 Takibi Bırak")
        else:
            self.watch_button.setText("👁 Takip Et")

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

        full_text  = f"📊 ANALİZ\n{result.get('analysis', '')}\n\n"
        full_text += "💡 TAVSİYELER\n" + "─" * 40 + "\n"
        for i, rec in enumerate(result.get("recommendations", []), 1):
            full_text += (
                f"\n{i}. {rec.get('action', '')}\n"
                f"   Neden : {rec.get('reason', '')}\n"
                f"   Risk  : {rec.get('risk', '')}\n"
            )
            det = (rec.get("detail") or "").strip()
            if det:
                full_text += f"   Detay : {det}\n"
        self.analysis_text.setPlainText(full_text)

        self.portfolio_hint.setText(portfolio_summary_line(portfolio))

        # Pasta grafik (USD yoksa miktar payları)
        self.pie_chart.update_chart(portfolio)

        # Portföy tablosu
        self.portfolio_table.clearSpans()
        self.portfolio_table.setRowCount(0)
        total_usd = 0.0

        if not portfolio:
            self.portfolio_table.insertRow(0)
            empty_msg = QTableWidgetItem(
                "Token bakiyesi yok veya henüz listelenmedi (ağ / RPC kontrol et)."
            )
            empty_msg.setForeground(QColor("#8888aa"))
            self.portfolio_table.setItem(0, 0, empty_msg)
            self.portfolio_table.setSpan(0, 0, 1, 6)
        else:
            for token in portfolio:
                row = self.portfolio_table.rowCount()
                self.portfolio_table.insertRow(row)
                mint = token.get("mint") or ""

                sym, name, amt, price_val, usd_val = safe_token_row(token)
                disp_name = (token.get("full_name") or "").strip() or name

                self.portfolio_table.setItem(row, 0, QTableWidgetItem(sym))
                self.portfolio_table.setItem(
                    row, 1, QTableWidgetItem(disp_name[:28])
                )

                amt_it = QTableWidgetItem(f"{amt:,.4f}")
                amt_it.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self.portfolio_table.setItem(row, 2, amt_it)

                if price_val > 0:
                    price_txt = (
                        f"${price_val:,.6f}" if price_val < 0.01
                        else f"${price_val:,.4f}"
                    )
                else:
                    price_txt = "—"
                price_item = QTableWidgetItem(price_txt)
                price_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self.portfolio_table.setItem(row, 3, price_item)

                total_usd += usd_val
                usd_item = QTableWidgetItem(
                    f"${usd_val:,.2f}" if usd_val > 0 else "—"
                )
                usd_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                if usd_val > 0:
                    usd_item.setForeground(QColor("#14f195"))
                self.portfolio_table.setItem(row, 4, usd_item)

                pnl_data = pnl.get(mint, {})
                pnl_val = float(pnl_data.get("unrealized", 0) or 0)
                if usd_val <= 0:
                    pnl_text = "—"
                else:
                    pnl_text = (
                        f"${pnl_val:+,.2f}" if pnl_val != 0 else "—"
                    )
                pnl_item = QTableWidgetItem(pnl_text)
                pnl_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                if pnl_val > 0:
                    pnl_item.setForeground(QColor("#14f195"))
                elif pnl_val < 0:
                    pnl_item.setForeground(QColor("#ff3355"))
                self.portfolio_table.setItem(row, 5, pnl_item)

            if total_usd > 0:
                row = self.portfolio_table.rowCount()
                self.portfolio_table.insertRow(row)
                tl = QTableWidgetItem("TOPLAM")
                tl.setForeground(QColor("#9945ff"))
                self.portfolio_table.setItem(row, 0, tl)
                ti = QTableWidgetItem(f"${total_usd:,.2f}")
                ti.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                ti.setForeground(QColor("#9945ff"))
                self.portfolio_table.setItem(row, 4, ti)

        # Blinks
        while self.actions_layout.count():
            child = self.actions_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        actions = self.blinks.build_actions(
            result.get("risk_level", ""),
            result.get("recommendations", []),
            wallet=self.current_wallet,
        )
        for action in actions:
            btn = QPushButton(action["label"])
            btn.setObjectName("secondaryBtn")
            btn.setToolTip(action["description"])
            url = action["url"]
            btn.clicked.connect(lambda _, u=url: self._open_action(u))
            self.actions_layout.addWidget(btn)
        self.actions_layout.addStretch()

    # ------------------------------------------------------------------ #
    #  Karşılaştırma                                                       #
    # ------------------------------------------------------------------ #
    def _pick_compare_wallet(self) -> str | None:
        """Geçmiş listesi seçimi veya diyalog ile ikinci cüzdan adresi."""
        cur = self.current_wallet
        if not cur:
            return None

        others: list[tuple[str, str]] = []
        for entry in self.history.get_all_wallets():
            w = entry.get("wallet")
            if not w or w == cur:
                continue
            risk = entry.get("result", {}).get("risk_level", "?")
            ts = entry.get("timestamp", "")
            others.append((w, f"{w[:8]}…{w[-4:]}  ·  {ts}  [{risk}]"))

        if not others:
            return None

        sel = self.sidebar_list.currentItem()
        if sel:
            cand = sel.data(Qt.ItemDataRole.UserRole)
            if cand and cand != cur and self.history.get_analysis(cand):
                return cand

        labels = [x[1] for x in others]
        keys = [x[0] for x in others]
        choice, ok = QInputDialog.getItem(
            self,
            "Karşılaştır",
            "İkinci cüzdanı seç (analiz geçmişinden):",
            labels,
            0,
            False,
        )
        if not ok:
            return None
        try:
            idx = labels.index(choice)
        except ValueError:
            return None
        return keys[idx]

    def _on_compare_clicked(self):
        if not self.current_wallet or not self.current_result:
            self._set_status("⚠️ Önce bu cüzdan için analiz tamamlanmalı.")
            return

        compare_wallet = self._pick_compare_wallet()
        if compare_wallet is None:
            self._set_status(
                "⚠️ Karşılaştırma için geçmişte başka bir analiz gerekli. "
                "İkinci cüzdanı analiz et veya listeden seç."
            )
            return

        if compare_wallet == self.current_wallet:
            self._set_status("⚠️ Aynı cüzdanı karşılaştıramazsın.")
            return

        entry_b = self.history.get_analysis(compare_wallet)
        if not entry_b:
            self._set_status("⚠️ Seçilen cüzdanın kayıtlı analizi yok.")
            return

        dlg = CompareDialog(
            self.current_wallet,
            self.current_result,
            self.current_portfolio,
            compare_wallet,
            entry_b["result"],
            entry_b.get("portfolio", []),
            parent=self,
        )
        dlg.exec()

    # ------------------------------------------------------------------ #
    #  Diğer slotlar                                                       #
    # ------------------------------------------------------------------ #
    def _open_action(self, url: str):
        QDesktopServices.openUrl(QUrl(url))
        self._set_status(f"🌐 Tarayıcıda açıldı: {url[:60]}...")

    def _on_watch_clicked(self):
        if not self.current_wallet:
            return
        if self.watcher.is_watching(self.current_wallet):
            self.watcher.unwatch(self.current_wallet)
            self.watch_button.setText("👁 Takip Et")
            self._load_sidebar()
            self._set_status("Takip durduruldu.")
        else:
            self.watcher.watch(self.current_wallet)
            self.watch_button.setText("👁 Takibi Bırak")
            self._load_sidebar()
            interval_sec = max(1, self.watcher.timer.interval() // 1000)
            self._set_status(
                f"✅ Takip başladı — her {interval_sec}s'de kontrol; "
                "yeni işlemde bildirim."
            )

    def _on_new_transaction(self, wallet: str):
        self._load_sidebar()
        self._set_status(
            f"🔔 {wallet[:12]}... yeni işlem — bildirim gönderildi. "
            "Güncel analiz için Yenile'ye bas."
        )

    def _on_export_txt(self):
        if not self.current_result:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "TXT olarak kaydet",
            f"{self.current_wallet[:8]}_analiz.txt",
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
            self, "PDF olarak kaydet",
            f"{self.current_wallet[:8]}_analiz.pdf",
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

    def _on_analysis_error(self, error_msg: str):
        self._set_ui_loading(False)
        self._set_status(f"❌ {error_msg}")
        QMessageBox.critical(self, "Hata", error_msg)

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
            self.pie_chart._draw_empty()
        else:
            self.analyze_button.setText("ANALİZ ET")

    def _set_status(self, message: str):
        self.status_label.setText(message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())