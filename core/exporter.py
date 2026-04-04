# core/exporter.py

import os
from datetime import datetime
from xml.sax.saxutils import escape


class Exporter:

    def export_txt(self, wallet: str, result: dict,
                   portfolio: list, filepath: str):
        lines = [
            "=" * 60,
            "  AI DESTEKLİ SOLANA CÜZDAN ANALİZİ",
            "=" * 60,
            f"Cüzdan  : {wallet}",
            f"Tarih   : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            f"Risk Seviyesi  : {result.get('risk_level', '?')}",
            f"Yatırımcı Tipi : {result.get('investor_type', '?')}",
            "",
            "── ANALİZ " + "─" * 50,
            result.get("analysis", ""),
            "",
            "── TAVSİYELER " + "─" * 46,
        ]

        for i, rec in enumerate(result.get("recommendations", []), 1):
            lines += [
                f"\n{i}. {rec.get('action', '')}",
                f"   Neden : {rec.get('reason', '')}",
                f"   Risk  : {rec.get('risk', '')}",
            ]
            det = (rec.get("detail") or "").strip()
            if det:
                lines.append(f"   Detay : {det}")

        lines += ["", "── PORTFÖY " + "─" * 49]
        for token in portfolio:
            lines.append(f"  {token['name']:<30} {token['amount']:,.4f}")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def export_pdf(self, wallet: str, result: dict,
                   portfolio: list, filepath: str):
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            )
            from reportlab.lib.units import cm
        except ImportError:
            raise RuntimeError("reportlab yüklü değil: pip install reportlab")

        doc    = SimpleDocTemplate(filepath, pagesize=A4)
        styles = getSampleStyleSheet()
        story  = []

        # Özel stiller
        title_style = ParagraphStyle(
            "title", parent=styles["Title"],
            fontSize=18, textColor=colors.HexColor("#9945ff"),
        )
        head_style = ParagraphStyle(
            "head", parent=styles["Heading2"],
            fontSize=12, textColor=colors.HexColor("#14f195"),
        )
        body_style = styles["BodyText"]
        body_style.fontSize = 10

        # Başlık
        story.append(Paragraph("AI Destekli Solana Cüzdan Analizi", title_style))
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph(f"<b>Cüzdan:</b> {wallet}", body_style))
        story.append(Paragraph(
            f"<b>Tarih:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            body_style
        ))
        story.append(Spacer(1, 0.5 * cm))

        # Risk & Tip
        story.append(Paragraph("Risk Profili", head_style))
        story.append(Paragraph(
            f"<b>Risk Seviyesi:</b> {result.get('risk_level', '?')}", body_style
        ))
        story.append(Paragraph(
            f"<b>Yatırımcı Tipi:</b> {result.get('investor_type', '?')}", body_style
        ))
        story.append(Spacer(1, 0.4 * cm))

        # Analiz
        story.append(Paragraph("Analiz", head_style))
        _an = escape(result.get("analysis", "")).replace("\n", "<br/>")
        story.append(Paragraph(_an, body_style))
        story.append(Spacer(1, 0.4 * cm))

        # Tavsiyeler
        story.append(Paragraph("Yatırım Tavsiyeleri", head_style))
        for i, rec in enumerate(result.get("recommendations", []), 1):
            story.append(Paragraph(
                f"<b>{i}. {escape(str(rec.get('action', '')))}</b>", body_style
            ))
            _r = escape(str(rec.get("reason", ""))).replace("\n", "<br/>")
            story.append(Paragraph(f"Neden: {_r}", body_style))
            story.append(Paragraph(
                f"Risk: {escape(str(rec.get('risk', '')))}", body_style
            ))
            det = (rec.get("detail") or "").strip()
            if det:
                _d = escape(det).replace("\n", "<br/>")
                story.append(Paragraph(f"Detay: {_d}", body_style))
            story.append(Spacer(1, 0.2 * cm))

        # Portföy tablosu
        if portfolio:
            story.append(Spacer(1, 0.4 * cm))
            story.append(Paragraph("Token Portföyü", head_style))
            table_data = [["Token", "Miktar"]]
            for t in portfolio:
                table_data.append([t["name"], f"{t['amount']:,.4f}"])

            table = Table(table_data, colWidths=[12 * cm, 5 * cm])
            table.setStyle(TableStyle([
                ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#9945ff")),
                ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
                ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [colors.HexColor("#1a1a2e"), colors.HexColor("#12121f")]),
                ("TEXTCOLOR",   (0, 1), (-1, -1), colors.HexColor("#e0e0ff")),
                ("GRID",        (0, 0), (-1, -1), 0.5, colors.HexColor("#2a2a45")),
                ("ALIGN",       (1, 0), (1, -1), "RIGHT"),
            ]))
            story.append(table)

        doc.build(story)