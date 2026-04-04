# core/chart_widget.py

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from core.portfolio_utils import token_label


class PortfolioPieChart(FigureCanvasQTAgg):

    COLORS = [
        "#9945ff", "#14f195", "#ffcc00", "#ff6600",
        "#00c2ff", "#ff3355", "#a855f7", "#22d3ee",
        "#f59e0b", "#10b981",
    ]

    def __init__(self, parent=None):
        # Geniş figür: sağda lejant için alan
        self.fig = Figure(figsize=(4.2, 3.4), facecolor="#12121f")
        super().__init__(self.fig)
        self.setParent(parent)
        self.ax = self.fig.add_subplot(111)
        self._draw_empty()

    def _draw_empty(self, message: str = "Analiz bekleniyor"):
        self.ax.clear()
        self.ax.set_facecolor("#12121f")
        self.fig.patch.set_facecolor("#12121f")
        self.ax.text(
            0.5, 0.5, message,
            ha="center", va="center",
            color="#8888aa", fontsize=10,
            transform=self.ax.transAxes,
        )
        self.ax.axis("off")
        self.fig.subplots_adjust(left=0.02, right=0.98, top=0.94, bottom=0.06)
        self.draw()

    def update_chart(self, portfolio: list[dict]):
        self.ax.clear()
        self.ax.set_facecolor("#12121f")
        self.fig.patch.set_facecolor("#12121f")

        if not portfolio:
            self._draw_empty("Portföy boş")
            return

        total_usd = sum(float(t.get("usd_value") or 0) for t in portfolio)

        if total_usd > 0:
            data = [
                t for t in portfolio
                if float(t.get("usd_value") or 0) > 0
            ]
            value_fn = lambda t: float(t.get("usd_value") or 0)
            unit = "USD"
        else:
            data = [
                t for t in portfolio
                if float(t.get("amount") or 0) > 0
            ]
            value_fn = lambda t: float(t.get("amount") or 0)
            unit = "miktar"

        if not data:
            self._draw_empty("Gösterilecek bakiye yok")
            return

        data = sorted(data, key=value_fn, reverse=True)
        total_val = sum(value_fn(t) for t in data)
        if total_val <= 0:
            self._draw_empty("Toplam değer sıfır")
            return

        if len(data) > 8:
            top = data[:7]
            other_val = sum(value_fn(t) for t in data[7:])
            labels = [token_label(t) for t in top] + ["Diğer"]
            sizes = [value_fn(t) for t in top] + [other_val]
        else:
            labels = [token_label(t) for t in data]
            sizes = [value_fn(t) for t in data]

        colors = self.COLORS[: len(sizes)]
        explode = [0.02] * len(sizes)

        wedges, texts, autotexts = self.ax.pie(
            sizes,
            labels=None,
            explode=explode,
            colors=colors,
            autopct=lambda p: f"{p:.0f}%" if p >= 5 else "",
            startangle=90,
            wedgeprops={"linewidth": 0.6, "edgecolor": "#12121f"},
            pctdistance=0.72,
            textprops={"color": "#ffffff", "fontsize": 8},
        )

        for at in autotexts:
            at.set_color("#ffffff")
            at.set_fontsize(8)

        self.ax.set_title(
            f"Dağılım ({unit})",
            color="#c8c8ee", fontsize=10, pad=6,
        )

        self.ax.legend(
            wedges,
            labels,
            loc="center left",
            bbox_to_anchor=(1.02, 0.5),
            fontsize=7,
            frameon=True,
            facecolor="#1a1a2e",
            edgecolor="#2a2a45",
            labelcolor="#c8c8ee",
        )

        self.ax.axis("equal")
        self.fig.subplots_adjust(left=0.02, right=0.68, top=0.88, bottom=0.06)
        self.draw()
