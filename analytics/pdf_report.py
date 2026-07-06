"""
CommunityIQ AI — PDF Report Generator

Generates professional downloadable PDF reports for the Decision Intelligence platform.
Uses reportlab for PDF creation.
"""
import io
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ── Try to import reportlab ──────────────────────────────────────────────────
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, KeepTogether
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logger.warning("[PDF] reportlab not installed — PDF generation disabled")


def generate_pdf_report(
    analytics: dict,
    recommendations: Optional[list] = None,
    executive_summary: Optional[str] = None,
    date_range: str = "Last 30 Days"
) -> bytes:
    """
    Generate a complete Decision Intelligence PDF report.
    
    Args:
        analytics: dict from analytics pipeline (compute_analytics)
        recommendations: list of action recommendation strings
        executive_summary: Gemini-generated executive summary text
        date_range: human-readable date range label
    
    Returns:
        PDF bytes ready for download
    """
    if not REPORTLAB_AVAILABLE:
        # Return a minimal text-based "PDF" placeholder
        return _fallback_text_report(analytics, recommendations, executive_summary)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="CommunityIQ AI — Decision Intelligence Report"
    )

    styles = getSampleStyleSheet()

    # ── Custom Styles ─────────────────────────────────────────────────────────
    title_style = ParagraphStyle(
        "CIQTitle",
        parent=styles["Title"],
        fontSize=22,
        textColor=colors.HexColor("#1e40af"),
        spaceAfter=6,
        alignment=TA_CENTER,
    )
    subtitle_style = ParagraphStyle(
        "CIQSubtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#6b7280"),
        alignment=TA_CENTER,
        spaceAfter=20,
    )
    section_style = ParagraphStyle(
        "CIQSection",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#1e40af"),
        borderPad=4,
        spaceBefore=16,
        spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "CIQBody",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#374151"),
        spaceAfter=6,
        leading=16,
    )
    highlight_style = ParagraphStyle(
        "CIQHighlight",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#dc2626"),
        spaceAfter=4,
        fontName="Helvetica-Bold",
    )

    story = []

    # ── Cover Header ──────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("🏛️ CommunityIQ AI", title_style))
    story.append(Paragraph("Decision Intelligence Report", subtitle_style))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%B %d, %Y %H:%M')} | Period: {date_range}",
        ParagraphStyle("meta", parent=styles["Normal"], fontSize=9,
                       textColor=colors.HexColor("#9ca3af"), alignment=TA_CENTER)
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1e40af"), spaceAfter=16))

    # ── Key Stats Summary ─────────────────────────────────────────────────────
    story.append(Paragraph("📊 Key Performance Indicators", section_style))

    total      = analytics.get("total_complaints", 0)
    resolved   = analytics.get("resolved", 0)
    open_c     = analytics.get("open", 0)
    critical   = analytics.get("open_critical", 0)
    res_rate   = analytics.get("resolution_rate", 0)
    avg_sev    = analytics.get("avg_severity_score", 0)

    kpi_data = [
        ["Metric", "Value", "Status"],
        ["Total Complaints", str(total), "—"],
        ["Resolved", str(resolved), "✅" if res_rate >= 70 else "⚠️"],
        ["Open", str(open_c), "🔴" if open_c > 10 else "🟡"],
        ["Open Critical/High", str(critical), "🚨" if critical > 0 else "✅"],
        ["Resolution Rate", f"{res_rate}%", "✅" if res_rate >= 70 else "⚠️"],
        ["Avg Severity Score", f"{avg_sev}/100", "🔴" if avg_sev > 70 else "🟡"],
    ]

    kpi_table = Table(kpi_data, colWidths=[8 * cm, 4 * cm, 4 * cm])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0),  colors.HexColor("#1e40af")),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, 0),  11),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f8fafc"), colors.white]),
        ("FONTSIZE",     (0, 1), (-1, -1), 10),
        ("GRID",         (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("ALIGN",        (1, 0), (-1, -1), "CENTER"),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 0.4 * cm))

    # ── Executive Summary ────────────────────────────────────────────────────
    if executive_summary:
        story.append(Paragraph("🧠 AI Executive Summary", section_style))
        story.append(Paragraph(executive_summary, body_style))
        story.append(Spacer(1, 0.3 * cm))

    # ── Category Distribution ─────────────────────────────────────────────────
    cat_dist = analytics.get("category_distribution", {})
    if cat_dist:
        story.append(Paragraph("📂 Issue Category Distribution", section_style))
        cat_data = [["Category", "Count", "% Share"]]
        cat_total = sum(cat_dist.values()) or 1
        sorted_cats = sorted(cat_dist.items(), key=lambda x: x[1], reverse=True)
        for cat, cnt in sorted_cats[:10]:
            pct = round(cnt / cat_total * 100, 1)
            cat_data.append([cat.replace("_", " ").title(), str(cnt), f"{pct}%"])

        cat_table = Table(cat_data, colWidths=[8 * cm, 4 * cm, 4 * cm])
        cat_table.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0),  colors.HexColor("#0369a1")),
            ("TEXTCOLOR",    (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1),
             [colors.HexColor("#f0f9ff"), colors.white]),
            ("FONTSIZE",     (0, 0), (-1, -1), 10),
            ("GRID",         (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("ALIGN",        (1, 0), (-1, -1), "CENTER"),
            ("TOPPADDING",   (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 7),
        ]))
        story.append(cat_table)
        story.append(Spacer(1, 0.3 * cm))

    # ── Top Affected Locations ────────────────────────────────────────────────
    top_locs = analytics.get("top_locations", [])
    if top_locs:
        story.append(Paragraph("📍 Top Affected Locations", section_style))
        loc_data = [["#", "Location", "Complaints"]]
        for i, loc in enumerate(top_locs[:8], 1):
            loc_data.append([
                str(i),
                str(loc.get("location", "Unknown"))[:50],
                str(loc.get("count", 0))
            ])
        loc_table = Table(loc_data, colWidths=[1.5 * cm, 10 * cm, 4.5 * cm])
        loc_table.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0),  colors.HexColor("#7c3aed")),
            ("TEXTCOLOR",    (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1),
             [colors.HexColor("#faf5ff"), colors.white]),
            ("FONTSIZE",     (0, 0), (-1, -1), 10),
            ("GRID",         (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("ALIGN",        (0, 0), (0, -1), "CENTER"),
            ("ALIGN",        (2, 0), (2, -1), "CENTER"),
            ("TOPPADDING",   (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 7),
        ]))
        story.append(loc_table)
        story.append(Spacer(1, 0.3 * cm))

    # ── Recommended Actions ──────────────────────────────────────────────────
    if recommendations:
        story.append(Paragraph("⚡ Recommended Actions", section_style))
        for i, rec in enumerate(recommendations[:8], 1):
            story.append(Paragraph(f"{i}. {rec}", body_style))
        story.append(Spacer(1, 0.3 * cm))

    # ── Risk by Category ─────────────────────────────────────────────────────
    risk_by_cat = analytics.get("risk_by_category", {})
    if risk_by_cat:
        story.append(Paragraph("⚠️ Risk Scores by Category", section_style))
        risk_data = [["Category", "Risk Score", "Level"]]
        for cat, score in sorted(risk_by_cat.items(), key=lambda x: x[1], reverse=True):
            level = "🔴 Critical" if score >= 75 else "🟠 High" if score >= 50 else "🟡 Moderate" if score >= 25 else "🟢 Low"
            risk_data.append([cat.replace("_", " ").title(), str(score), level])
        risk_table = Table(risk_data, colWidths=[7 * cm, 4 * cm, 5 * cm])
        risk_table.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0),  colors.HexColor("#dc2626")),
            ("TEXTCOLOR",    (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1),
             [colors.HexColor("#fff1f2"), colors.white]),
            ("FONTSIZE",     (0, 0), (-1, -1), 10),
            ("GRID",         (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("ALIGN",        (1, 0), (-1, -1), "CENTER"),
            ("TOPPADDING",   (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 7),
        ]))
        story.append(risk_table)

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.8 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb")))
    story.append(Paragraph(
        "Generated by CommunityIQ AI — AI-Powered Decision Intelligence Platform | "
        "Hack2Skill Gen AI Academy APAC Edition",
        ParagraphStyle("footer", parent=styles["Normal"], fontSize=8,
                       textColor=colors.HexColor("#9ca3af"), alignment=TA_CENTER)
    ))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    logger.info("[PDF] Generated PDF report: %d bytes", len(pdf_bytes))
    return pdf_bytes


def _fallback_text_report(analytics: dict, recommendations, executive_summary) -> bytes:
    """Plain text fallback when reportlab is not installed."""
    lines = [
        "CommunityIQ AI — Decision Intelligence Report",
        "=" * 60,
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "KEY METRICS",
        f"Total Complaints:  {analytics.get('total_complaints', 0)}",
        f"Resolved:          {analytics.get('resolved', 0)}",
        f"Resolution Rate:   {analytics.get('resolution_rate', 0)}%",
        f"Open Critical:     {analytics.get('open_critical', 0)}",
        "",
    ]
    if executive_summary:
        lines += ["EXECUTIVE SUMMARY", executive_summary, ""]
    if recommendations:
        lines += ["RECOMMENDED ACTIONS"] + [f"  {i+1}. {r}" for i, r in enumerate(recommendations)] + [""]
    lines += ["---", "Powered by Google Gemini AI | CommunityIQ AI"]
    return "\n".join(lines).encode("utf-8")
