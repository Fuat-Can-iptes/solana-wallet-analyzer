# main.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLineEdit, QLabel, QTextEdit, QTableWidget,
    QTableWidgetItem, QListWidget, QListWidgetItem, QFileDialog,
    QMessageBox, QSplitter, QFrame, QHeaderView, QDialog,
    QDialogButtonBox, QGridLayout,
)
from PyQt6.QtCore import Qt, QSize, QUrl
from PyQt6.QtGui import QColor, QDesktopServices

from core.worker import AnalysisWorker
from core.history_manager import HistoryManager
from core.watcher import WalletWatcher
from core.exporter import Exporter
from core.blinks_builder import BlinksBuilder
from core.chart_widget import PortfolioPieChart

QSS_FILE = "assets/styles/dark_theme.qss"


class CompareDialog(QDialog):
    """İki cüzdanı yan yana karşılaştırma penceresi."""

    def __init__(self, wallet_a: str, result_a: dict, portfolio_a: list,
                 wallet_b: str, result_b: dict, portfolio_b: list,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cüzdan Karşılaştırma")
        self.resize(900, 600)
        self._build(wallet_a, result_a, portfolio_a,
                    wallet_b, result_b, portfolio_b)

    def _build(self, wa, ra, pa, wb, rb, pb):
        layout = QHBoxLayout(self)

        for wallet, result, portfolio in [(wa, ra, pa), (wb, rb, pb)]:
            frame = QFrame()
            frame.setObjectName("rightPanel")
            vl = QVBoxLayout(frame)

            title = QLabel(f"🔍 {wallet[:20]}...")
            title.setObjectName("walletTitle")
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
            vl.addWidget(inv_lbl)

            analysis = QTextEdit()
            analysis.setReadOnly(True)
            analysis.setPlainText(result.get("analysis", ""))
            vl.addWidget(analysis)

            # Pasta grafik
            chart = PortfolioPieChart()
            chart.update_chart(portfolio)
            chart.setMinimumHeight(200)
            vl.addWidget(chart)

            # Toplam değer
            total = sum(t.get("usd_value", 0) for t in portfolio)
            total_lbl = QLabel(f"Portföy: ${total:,.2f}")
            total_lbl.setObjectName("sectionHeader")
            vl.addWidget(total_lbl)

            layout.addWidget(frame)


class MainApp(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Destekli Solana Cüzdan Analizcisi")
        self.resize(1300, 800)

        self.history            = HistoryManager()
        self.watcher            = WalletWatcher(self)
        self.exporter           = Exporter()
        self.blinks             = BlinksBuilder()
        self.worker             = None
        self.compare_worker     = None
        self.current_wallet     = None
        self.current_result     = None
        self.current_portfolio  = []
        self.current_pnl        = {}

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

        btn_row = QHBoxLayout()
        self.analyze_button = QPushButton("ANALİZ ET")
        btn_row.addWidget(self.analyze_button)
        sb_layout.addLayout(btn_row)

        self.compare_button = QPushButton("🔀 Karşılaştır")
        self.compare_button.setObjectName("secondaryBtn")
        self.compare_button.setEnabled(False)
        self.compare_button.setToolTip(
            "Aktif cüzdanı seçili geçmiş cüzdanla karşılaştır"
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
        self.pie_chart.setMinimumHeight(220)
        self.pie_chart.setMaximumWidth(300)
        pie_col.addWidget(self.pie_chart)
        pie_col.addStretch()
        mid_row.addLayout(pie_col, stretch=1)

        right_layout.addLayout(mid_row)

        # Portföy tablosu — 5 sütun: Sembol, İsim, Miktar, Fiyat, USD, PnL
        right_layout.addWidget(self._section_label("TOKEN PORTFÖYÜ"))

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
        self.portfolio_table.setMinimumHeight(180)
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
        splitter.setSizes([260, 1040])

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("sectionHeader")
        return lbl

    def _connect_signals(self):
        self.analyze_button.clicked.connect(self._on_analyze_clicked)
        self.wallet_input.returnPressed.connect(self._on_analyze_clicked)
        self.sidebar_list.itemClicked.connect(self._on_sidebar_clicked)
        self.refresh_button.clicked.connect(self._on_refresh_clicked)
        self.watch_button.clicked.connect(self._on_watch_clicked)
        self.export_txt_button.clicked.connect(self._on_export_txt)
        self.export_pdf_button.clicked.connect(self._on_export_pdf)
        self.compare_button.clicked.connect(self._on_compare_clicked)
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
        self.analysis_text.setPlainText(full_text)

        # Pasta grafik
        self.pie_chart.update_chart(portfolio)

        # Portföy tablosu
        self.portfolio_table.setRowCount(0)
        total_usd = 0.0

        for token in portfolio:
            row  = self.portfolio_table.rowCount()
            self.portfolio_table.insertRow(row)
            mint = token.get("mint", "")

            sym  = token.get("symbol", token["name"][:8])
            name = token.get("full_name", token["name"])

            self.portfolio_table.setItem(row, 0, QTableWidgetItem(sym))
            self.portfolio_table.setItem(row, 1, QTableWidgetItem(name[:24]))

            amt = QTableWidgetItem(f"{token['amount']:,.4f}")
            amt.setTextAlignment(Qt.AlignmentFlag.AlignRight |
                                  Qt.AlignmentFlag.AlignVCenter)
            self.portfolio_table.setItem(row, 2, amt)

            price_val = token.get("usd_price", 0.0)
            price_item = QTableWidgetItem(
                f"${price_val:,.6f}" if price_val < 0.01
                else f"${price_val:,.4f}"
            )
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight |
                                         Qt.AlignmentFlag.AlignVCenter)
            self.portfolio_table.setItem(row, 3, price_item)

            usd_val = token.get("usd_value", 0.0)
            total_usd += usd_val
            usd_item = QTableWidgetItem(
                f"${usd_val:,.2f}" if usd_val > 0 else "—"
            )
            usd_item.setTextAlignment(Qt.AlignmentFlag.AlignRight |
                                       Qt.AlignmentFlag.AlignVCenter)
            if usd_val > 0:
                usd_item.setForeground(QColor("#14f195"))
            self.portfolio_table.setItem(row, 4, usd_item)

            # PnL sütunu
            pnl_data = pnl.get(mint, {})
            pnl_val  = pnl_data.get("unrealized", 0.0)
            pnl_text = f"${pnl_val:+,.2f}" if pnl_val != 0 else "—"
            pnl_item = QTableWidgetItem(pnl_text)
            pnl_item.setTextAlignment(Qt.AlignmentFlag.AlignRight |
                                       Qt.AlignmentFlag.AlignVCenter)
            if pnl_val > 0:
                pnl_item.setForeground(QColor("#14f195"))
            elif pnl_val < 0:
                pnl_item.setForeground(QColor("#ff3355"))
            self.portfolio_table.setItem(row, 5, pnl_item)

        # Toplam satırı
        if total_usd > 0:
            row = self.portfolio_table.rowCount()
            self.portfolio_table.insertRow(row)
            tl = QTableWidgetItem("TOPLAM")
            tl.setForeground(QColor("#9945ff"))
            self.portfolio_table.setItem(row, 0, tl)
            ti = QTableWidgetItem(f"${total_usd:,.2f}")
            ti.setTextAlignment(Qt.AlignmentFlag.AlignRight |
                                  Qt.AlignmentFlag.AlignVCenter)
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
    def _on_compare_clicked(self):
        selected = self.sidebar_list.currentItem()
        if not selected:
            self._set_status("⚠️ Karşılaştırmak için sol panelden bir cüzdan seç.")
            return
        if not self.current_wallet:
            self._set_status("⚠️ Önce bir cüzdan analiz et.")
            return

        compare_wallet = selected.data(Qt.ItemDataRole.UserRole)
        if compare_wallet == self.current_wallet:
            self._set_status("⚠️ Aynı cüzdanı karşılaştıramazsın.")
            return

        entry_b = self.history.get_analysis(compare_wallet)
        if not entry_b:
            self._set_status("⚠️ Karşılaştırılacak cüzdanın analizi bulunamadı.")
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
            self._set_status("Takip durduruldu.")
        else:
            self.watcher.watch(self.current_wallet)
            self.watch_button.setText("👁 Takibi Bırak")
            self._set_status("✅ Takip başladı — 60s'de bir kontrol edilecek.")

    def _on_new_transaction(self, wallet: str):
        self._set_status(f"🔔 {wallet[:12]}... adresinde yeni işlem!")

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