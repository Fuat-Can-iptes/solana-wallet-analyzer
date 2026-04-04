# core/chart_widget.py

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import matplotlib.pyplot as plt


class PortfolioPieChart(FigureCanvasQTAgg):

    COLORS = [
        "#9945ff", "#14f195", "#ffcc00", "#ff6600",
        "#00c2ff", "#ff3355", "#a855f7", "#22d3ee",
        "#f59e0b", "#10b981",
    ]

    def __init__(self, parent=None):
        self.fig = Figure(figsize=(4, 3), facecolor="#12121f")
        super().__init__(self.fig)
        self.setParent(parent)
        self.ax = self.fig.add_subplot(111)
        self._draw_empty()

    def _draw_empty(self):
        self.ax.clear()
        self.ax.set_facecolor("#12121f")
        self.ax.text(
            0.5, 0.5, "Analiz bekleniyor",
            ha="center", va="center",
            color="#555577", fontsize=10,
            transform=self.ax.transAxes,
        )
        self.ax.axis("off")
        self.draw()

    def update_chart(self, portfolio: list[dict]):
        self.ax.clear()
        self.ax.set_facecolor("#12121f")
        self.fig.patch.set_facecolor("#12121f")

        # Sadece USD değeri olan tokenları al, max 8 slice
        data = [t for t in portfolio if t.get("usd_value", 0) > 0]
        if not data:
            self._draw_empty()
            return

        data = sorted(data, key=lambda x: x["usd_value"], reverse=True)

        # 8'den fazlaysa geri kalanları "Diğer" olarak grupla
        if len(data) > 8:
            top   = data[:7]
            other = sum(t["usd_value"] for t in data[7:])
            labels = [t.get("symbol", t["name"][:6]) for t in top] + ["Diğer"]
            sizes  = [t["usd_value"] for t in top] + [other]
        else:
            labels = [t.get("symbol", t["name"][:6]) for t in data]
            sizes  = [t["usd_value"] for t in data]

        colors = self.COLORS[:len(sizes)]

        wedges, texts, autotexts = self.ax.pie(
            sizes,
            labels=None,
            colors=colors,
            autopct=lambda p: f"{p:.1f}%" if p > 4 else "",
            startangle=90,
            wedgeprops={"linewidth": 0.5, "edgecolor": "#12121f"},
            pctdistance=0.75,
        )

        for at in autotexts:
            at.set_color("#ffffff")
            at.set_fontsize(8)

        # Legend
        self.ax.legend(
            wedges, labels,
            loc="lower center",
            bbox_to_anchor=(0.5, -0.15),
            ncol=4,
            fontsize=7,
            frameon=False,
            labelcolor="#8888aa",
        )

        self.ax.axis("equal")
        self.fig.tight_layout(pad=0.5)
        self.draw()