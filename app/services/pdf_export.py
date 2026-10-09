from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


FONT_NAME = "Helvetica"
BOLD_FONT_NAME = "Helvetica-Bold"

INK = colors.HexColor("#17201a")
MUTED = colors.HexColor("#637069")
LINE = colors.HexColor("#d8e0d9")
SURFACE = colors.HexColor("#f7faf7")
PAPER = colors.HexColor("#ffffff")
PAPER_SOFT = colors.HexColor("#f1f6f3")
ACCENT = colors.HexColor("#0f766e")
ACCENT_STRONG = colors.HexColor("#115e59")
GREEN = colors.HexColor("#15803d")
ROSE = colors.HexColor("#b42318")
GOLD = colors.HexColor("#b7791f")
WARNING_BG = colors.HexColor("#fff8e6")
WARNING_LINE = colors.HexColor("#f2d18b")


def _register_fonts() -> None:
    global FONT_NAME, BOLD_FONT_NAME

    font_path = Path("C:/Windows/Fonts/arial.ttf")
    bold_path = Path("C:/Windows/Fonts/arialbd.ttf")
    if font_path.exists():
        pdfmetrics.registerFont(TTFont("AppArial", str(font_path)))
        FONT_NAME = "AppArial"
    if bold_path.exists():
        pdfmetrics.registerFont(TTFont("AppArialBold", str(bold_path)))
        BOLD_FONT_NAME = "AppArialBold"


def _text(value) -> str:
    if value is None:
        return "-"
    return str(value)


def _money(value) -> str:
    try:
        return f"{float(value):,.2f}"
    except Exception:
        return "-"


def _percent(value) -> str:
    try:
        return f"{float(value) * 100:.0f}%"
    except Exception:
        return "-"


def _paragraph(value, style):
    return Paragraph(_text(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), style)


def _status_color(status: str | None):
    normalized = (status or "").lower()
    if "review" in normalized or "warning" in normalized:
        return GOLD, WARNING_BG
    if "fail" in normalized or "error" in normalized:
        return ROSE, colors.HexColor("#fff1f1")
    return ACCENT_STRONG, PAPER_SOFT


def _section_label(title: str, style, width: float):
    table = Table([[_paragraph(title, style)]], colWidths=[width])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PAPER),
        ("LINEBELOW", (0, 0), (-1, -1), 1, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _metric_cards(cards: list[tuple[str, str, str | None]], width: float, styles: dict, columns: int = 4):
    col_width = width / columns
    rows = []
    for start in range(0, len(cards), columns):
        row = []
        for label, value, tone in cards[start:start + columns]:
            value_style = styles["metric_value"]
            if tone == "good":
                value_style = styles["metric_value_good"]
            elif tone == "bad":
                value_style = styles["metric_value_bad"]
            elif tone == "accent":
                value_style = styles["metric_value_accent"]
            row.append([
                _paragraph(label, styles["metric_label"]),
                Spacer(1, 0.05 * cm),
                _paragraph(value, value_style),
            ])
        while len(row) < columns:
            row.append("")
        rows.append(row)

    table = Table(rows, colWidths=[col_width] * columns, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PAPER),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def _info_table(rows, width: float, normal_style, label_style):
    data = [[_paragraph(label, label_style), _paragraph(value, normal_style)] for label, value in rows]
    table = Table(data, colWidths=[width * 0.32, width * 0.68], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("BACKGROUND", (0, 0), (-1, -1), PAPER),
        ("BACKGROUND", (0, 0), (0, -1), PAPER_SOFT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _analytics_rows(title: str, rows: list[dict], width: float, styles: dict):
    story = [_section_label(title, styles["heading"], width)]
    if not rows:
        empty = Table([[_paragraph("None found", styles["muted"])]], colWidths=[width])
        empty.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, LINE),
            ("BACKGROUND", (0, 0), (-1, -1), PAPER_SOFT),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(empty)
        return story

    data = [[_paragraph("Counterparty", styles["table_head"]), _paragraph("Amount", styles["table_head_right"])]]
    for row in rows[:15]:
        data.append([
            _paragraph(row.get("counterparty_name") or "Unknown", styles["normal"]),
            _paragraph(_money(row.get("amount")), styles["amount_right"]),
        ])

    table = Table(data, colWidths=[width * 0.7, width * 0.3], hAlign="LEFT", repeatRows=1)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAPER, SURFACE]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    return story


def _month_key_from_value(value) -> str | None:
    if not value:
        return None
    text = str(value)
    if len(text) >= 7 and text[4] == "-":
        return text[:7]
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%Y-%m")
    except Exception:
        return None


def _monthwise_from_transactions(transactions: list[dict], direction: str) -> dict[str, float]:
    totals: dict[str, float] = {}
    for txn in transactions:
        txn_direction = txn.get("direction")
        amount = txn.get("amount")
        if txn_direction is None:
            try:
                txn_direction = "debit" if float(amount) < 0 else "credit"
            except Exception:
                txn_direction = None
        if txn_direction != direction:
            continue

        month = _month_key_from_value(txn.get("txn_date"))
        if not month:
            continue

        try:
            totals[month] = totals.get(month, 0.0) + abs(float(amount))
        except Exception:
            continue

    return {month: round(amount, 2) for month, amount in sorted(totals.items())}


def _has_month_values(months: dict | None) -> bool:
    if not months:
        return False
    for value in months.values():
        try:
            if abs(float(value)) > 0:
                return True
        except Exception:
            continue
    return False


def _monthwise_table(
    credits: dict,
    debits: dict,
    transactions: list[dict],
    width: float,
    styles: dict,
):
    credits = credits if _has_month_values(credits) else _monthwise_from_transactions(transactions, "credit")
    debits = debits if _has_month_values(debits) else _monthwise_from_transactions(transactions, "debit")
    months = sorted(set(credits.keys()) | set(debits.keys()))

    story = [_section_label("Monthwise Credits And Debits", styles["heading"], width)]
    if not months:
        empty = Table([[_paragraph("None found", styles["muted"])]], colWidths=[width])
        empty.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, LINE),
            ("BACKGROUND", (0, 0), (-1, -1), PAPER_SOFT),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(empty)
        return story

    data = [[
        _paragraph("Month", styles["table_head"]),
        _paragraph("Credits", styles["table_head_right"]),
        _paragraph("Debits", styles["table_head_right"]),
        _paragraph("Net", styles["table_head_right"]),
    ]]
    for month in months:
        credit = float(credits.get(month) or 0)
        debit = float(debits.get(month) or 0)
        data.append([
            _paragraph(month, styles["normal"]),
            _paragraph(_money(credit), styles["amount_right_good"]),
            _paragraph(_money(debit), styles["amount_right_bad"]),
            _paragraph(_money(credit - debit), styles["amount_right"]),
        ])

    table = Table(
        data,
        colWidths=[width * 0.25, width * 0.25, width * 0.25, width * 0.25],
        hAlign="LEFT",
        repeatRows=1,
    )
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAPER, SURFACE]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    return story


def _draw_page_frame(canvas, doc, report: dict) -> None:
    canvas.saveState()
    page_width, page_height = landscape(A4)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    filename = _text(report.get("filename") or report.get("report_id"))

    canvas.setFillColor(SURFACE)
    canvas.rect(0, 0, page_width, page_height, stroke=0, fill=1)
    canvas.setFillColor(ACCENT)
    canvas.rect(0, page_height - 0.22 * cm, page_width, 0.22 * cm, stroke=0, fill=1)

    canvas.setFillColor(INK)
    canvas.setFont(BOLD_FONT_NAME, 9)
    canvas.drawString(doc.leftMargin, page_height - 0.85 * cm, "SME Statement Analyzer")
    canvas.setFillColor(MUTED)
    canvas.setFont(FONT_NAME, 7)
    canvas.drawRightString(page_width - doc.rightMargin, page_height - 0.85 * cm, filename[:95])

    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, 1.05 * cm, page_width - doc.rightMargin, 1.05 * cm)
    canvas.setFillColor(MUTED)
    canvas.setFont(FONT_NAME, 7)
    canvas.drawString(doc.leftMargin, 0.62 * cm, f"Generated {generated}")
    canvas.drawRightString(page_width - doc.rightMargin, 0.62 * cm, f"Page {doc.page}")
    canvas.restoreState()


def build_report_pdf(report: dict) -> bytes:
    _register_fonts()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=1.2 * cm,
        leftMargin=1.2 * cm,
        topMargin=1.55 * cm,
        bottomMargin=1.25 * cm,
        title=f"Statement Report - {report.get('filename') or report.get('report_id')}",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName=BOLD_FONT_NAME,
        fontSize=21,
        leading=25,
        textColor=INK,
        spaceAfter=4,
    )
    heading_style = ParagraphStyle(
        "ReportHeading",
        parent=styles["Heading2"],
        fontName=BOLD_FONT_NAME,
        fontSize=11,
        leading=14,
        textColor=INK,
        spaceBefore=4,
        spaceAfter=4,
    )
    normal_style = ParagraphStyle(
        "ReportNormal",
        parent=styles["BodyText"],
        fontName=FONT_NAME,
        fontSize=8,
        leading=10.5,
        textColor=INK,
    )
    muted_style = ParagraphStyle(
        "ReportMuted",
        parent=normal_style,
        textColor=MUTED,
    )
    eyebrow_style = ParagraphStyle(
        "ReportEyebrow",
        parent=normal_style,
        fontName=BOLD_FONT_NAME,
        fontSize=7,
        leading=9,
        textColor=ACCENT_STRONG,
    )
    label_style = ParagraphStyle(
        "ReportLabel",
        parent=normal_style,
        fontName=BOLD_FONT_NAME,
        textColor=MUTED,
    )
    metric_label_style = ParagraphStyle(
        "MetricLabel",
        parent=normal_style,
        fontSize=7,
        leading=9,
        textColor=MUTED,
    )
    metric_value_style = ParagraphStyle(
        "MetricValue",
        parent=normal_style,
        fontName=BOLD_FONT_NAME,
        fontSize=13,
        leading=15,
        textColor=INK,
    )
    metric_value_accent_style = ParagraphStyle(
        "MetricValueAccent",
        parent=metric_value_style,
        textColor=ACCENT_STRONG,
    )
    metric_value_good_style = ParagraphStyle(
        "MetricValueGood",
        parent=metric_value_style,
        textColor=GREEN,
    )
    metric_value_bad_style = ParagraphStyle(
        "MetricValueBad",
        parent=metric_value_style,
        textColor=ROSE,
    )
    table_head_style = ParagraphStyle(
        "TableHead",
        parent=normal_style,
        fontName=BOLD_FONT_NAME,
        fontSize=7.5,
        leading=9,
        textColor=colors.white,
    )
    table_head_right_style = ParagraphStyle(
        "TableHeadRight",
        parent=table_head_style,
        alignment=TA_RIGHT,
    )
    amount_right_style = ParagraphStyle(
        "AmountRight",
        parent=normal_style,
        alignment=TA_RIGHT,
        fontName=BOLD_FONT_NAME,
    )
    amount_right_good_style = ParagraphStyle(
        "AmountRightGood",
        parent=amount_right_style,
        textColor=GREEN,
    )
    amount_right_bad_style = ParagraphStyle(
        "AmountRightBad",
        parent=amount_right_style,
        textColor=ROSE,
    )
    small_style = ParagraphStyle(
        "Small",
        parent=normal_style,
        fontSize=6.8,
        leading=8.2,
    )
    styles_by_name = {
        "normal": normal_style,
        "muted": muted_style,
        "heading": heading_style,
        "metric_label": metric_label_style,
        "metric_value": metric_value_style,
        "metric_value_accent": metric_value_accent_style,
        "metric_value_good": metric_value_good_style,
        "metric_value_bad": metric_value_bad_style,
        "table_head": table_head_style,
        "table_head_right": table_head_right_style,
        "amount_right": amount_right_style,
        "amount_right_good": amount_right_good_style,
        "amount_right_bad": amount_right_bad_style,
        "small": small_style,
    }

    width = doc.width
    status = _text(report.get("status") or "Ready")
    status_ink, status_bg = _status_color(status)
    status_style = ParagraphStyle(
        "StatusBadge",
        parent=normal_style,
        fontName=BOLD_FONT_NAME,
        alignment=TA_RIGHT,
        textColor=status_ink,
    )

    analytics = report.get("analytics") or {}
    metrics = report.get("quality_metrics") or {}
    transactions = report.get("transactions") or []
    is_zatca_report = report.get("document_type") == "zatca_vat_return"
    analytics_credits = analytics.get("monthwise_credits")
    analytics_debits = analytics.get("monthwise_debits")
    monthwise_credits = analytics_credits if _has_month_values(analytics_credits) else _monthwise_from_transactions(transactions, "credit")
    monthwise_debits = analytics_debits if _has_month_values(analytics_debits) else _monthwise_from_transactions(transactions, "debit")

    header = Table(
        [
            [
                [
                    _paragraph("TAX REPORT" if is_zatca_report else "STATEMENT REPORT", eyebrow_style),
                    Spacer(1, 0.08 * cm),
                    Paragraph("ZATCA VAT Return Analysis" if is_zatca_report else "Bank Statement Analysis Report", title_style),
                    _paragraph(report.get("filename"), muted_style),
                ],
                _paragraph(status, status_style),
            ],
        ],
        colWidths=[width * 0.75, width * 0.25],
        hAlign="LEFT",
    )
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PAPER),
        ("BOX", (0, 0), (-1, -1), 0.7, LINE),
        ("LINEBEFORE", (0, 0), (0, -1), 4, ACCENT),
        ("BACKGROUND", (1, 0), (1, 0), status_bg),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 11),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
    ]))

    summary_cards = [
        ("Document", "ZATCA VAT return", "accent"),
        ("Quarter", _text(analytics.get("quarter") or "Unknown"), "accent"),
        ("Period start", _text(analytics.get("period_start") or "-"), None),
        ("Period end", _text(analytics.get("period_end") or "-"), None),
        ("Parse confidence", _percent(report.get("parse_confidence")), "good"),
        ("Parser", _text(report.get("parser_used") or "-"), None),
    ] if is_zatca_report else [
        ("Bank", _text(report.get("bank_name") or "Unknown"), "accent"),
        ("Parser", _text(report.get("parser_used") or "-"), None),
        ("Parse confidence", _percent(report.get("parse_confidence")), "good"),
        ("Transactions", _text(report.get("transaction_count")), "accent"),
        ("Classified rows", f"{metrics.get('classified_rows_pct', 0)}%", None),
        ("Counterparty coverage", f"{metrics.get('counterparty_coverage_pct', 0)}%", None),
        ("Date coverage", f"{metrics.get('date_coverage_pct', 0)}%", None),
        ("Balance coverage", f"{metrics.get('balance_coverage_pct', 0)}%", None),
    ]

    story = [
        header,
        Spacer(1, 0.32 * cm),
        _metric_cards(summary_cards, width, styles_by_name, columns=4),
        Spacer(1, 0.28 * cm),
        _section_label("Report Details", heading_style, width),
        _info_table([
            ("Report ID", _text(report.get("report_id"))),
            ("Template", _text(report.get("template_name") or "Unknown")),
            ("Status", _text(report.get("status"))),
            ("Review required", "Yes" if report.get("review_required") else "No"),
        ], width, normal_style, label_style),
        Spacer(1, 0.28 * cm),
    ]

    story.append(_section_label("Analytics", heading_style, width))
    if is_zatca_report:
        story.extend([
            _metric_cards([
                ("Total sales", _money(analytics.get("total_sales")), "good"),
                ("Total purchases", _money(analytics.get("total_purchases")), "bad"),
                ("Sales tax", _money(analytics.get("sales_tax")), "accent"),
                ("Purchase tax", _money(analytics.get("purchase_tax")), "accent"),
                ("Net taxes", _money(analytics.get("net_taxes")), "bad" if (analytics.get("net_taxes") or 0) < 0 else "good"),
            ], width, styles_by_name, columns=4),
            Spacer(1, 0.28 * cm),
        ])
    else:
        story.extend([
            _metric_cards([
                ("Cash deposits", _money(analytics.get("total_cash_deposits")), "good"),
                ("Cash withdrawals", _money(analytics.get("total_cash_withdrawals")), "bad"),
                ("Average credit balance", _money(analytics.get("average_credit_balance")), "accent"),
                ("Credit months", _text(len(monthwise_credits)), None),
                ("Debit months", _text(len(monthwise_debits)), None),
            ], width, styles_by_name, columns=4),
            Spacer(1, 0.28 * cm),
        ])
        story.extend(_monthwise_table(monthwise_credits, monthwise_debits, transactions, width, styles_by_name))
        story.append(Spacer(1, 0.25 * cm))
        story.extend(_analytics_rows("Major Transfers To", analytics.get("major_transfers_to") or [], width, styles_by_name))
        story.append(Spacer(1, 0.25 * cm))
        story.extend(_analytics_rows("Major Deposits By", analytics.get("major_deposits_by") or [], width, styles_by_name))

    warnings = report.get("warnings") or []
    if warnings:
        story.append(Spacer(1, 0.25 * cm))
        story.append(_section_label("Warnings", heading_style, width))
        warning_rows = [[_paragraph(warning, normal_style)] for warning in warnings]
        warning_table = Table(warning_rows, colWidths=[width], hAlign="LEFT")
        warning_table.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.7, WARNING_LINE),
            ("BACKGROUND", (0, 0), (-1, -1), WARNING_BG),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#6f4e00")),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(warning_table)

    if transactions:
        story.append(PageBreak())
        story.append(_section_label("Transactions", heading_style, width))
        data = [[
            _paragraph("Date", table_head_style),
            _paragraph("Description", table_head_style),
            _paragraph("Amount", table_head_right_style),
            _paragraph("Balance", table_head_right_style),
            _paragraph("Category", table_head_style),
            _paragraph("Counterparty", table_head_style),
        ]]

        for txn in transactions[:500]:
            amount = txn.get("amount")
            amount_style = amount_right_style
            if amount is not None:
                try:
                    amount_style = ParagraphStyle(
                        "DebitAmount" if float(amount) < 0 else "CreditAmount",
                        parent=amount_right_style,
                        textColor=ROSE if float(amount) < 0 else GREEN,
                    )
                except Exception:
                    amount_style = amount_right_style
            data.append([
                _paragraph((txn.get("txn_date") or "")[:10], small_style),
                _paragraph(txn.get("description_display") or txn.get("description_normalized") or txn.get("description_raw"), small_style),
                _paragraph(_money(txn.get("amount")), amount_style),
                _paragraph(_money(txn.get("balance")), small_style),
                _paragraph(txn.get("category") or "-", small_style),
                _paragraph(txn.get("counterparty_name") or "-", small_style),
            ])

        table = Table(
            data,
            colWidths=[2.1 * cm, 11.9 * cm, 2.5 * cm, 2.5 * cm, 3.1 * cm, 5.2 * cm],
            repeatRows=1,
            hAlign="LEFT",
        )
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.35, LINE),
            ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAPER, SURFACE]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(table)

        if len(transactions) > 500:
            story.append(Spacer(1, 0.2 * cm))
            story.append(Paragraph(f"Showing first 500 of {len(transactions)} transactions.", muted_style))

    doc.build(
        story,
        onFirstPage=lambda canvas, built_doc: _draw_page_frame(canvas, built_doc, report),
        onLaterPages=lambda canvas, built_doc: _draw_page_frame(canvas, built_doc, report),
    )
    return buffer.getvalue()
