from __future__ import annotations

import re
import unicodedata
from datetime import datetime

from app.services.parser import extract_text_from_pdf


NUMBER_RE = re.compile(r"-?[0-9,]+\.[0-9]{2}")
DATE_RE = re.compile(r"\b(20\d{2})/(\d{2})/(\d{2})\b")


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    output = []

    for char in normalized:
        try:
            output.append(str(unicodedata.digit(char)))
            continue
        except Exception:
            pass

        if char in {"\u066c", "٬"}:
            output.append(",")
        elif char in {"\u2212", "−"}:
            output.append("-")
        else:
            output.append(char)

    return "".join(output)


def _to_float(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return round(float(value.replace(",", "")), 2)
    except Exception:
        return None


def _line_numbers(line: str) -> list[float]:
    return [
        value
        for value in (_to_float(match) for match in NUMBER_RE.findall(line))
        if value is not None
    ]


def _row_marker(row_number: int) -> re.Pattern:
    return re.compile(rf"(?<!\d)\.{row_number}(?!\d)|(?<!\d){row_number}\.(?!\d)")


def _find_row_numbers(lines: list[str], row_number: int) -> list[float]:
    marker = _row_marker(row_number)
    for index, line in enumerate(lines):
        if not marker.search(line):
            continue

        values = _line_numbers(line)
        if values:
            return values

        for next_line in lines[index + 1:index + 4]:
            values = _line_numbers(next_line)
            if values:
                return values

    return []


def _parse_period(lines: list[str]) -> dict:
    for line in lines:
        matches = DATE_RE.findall(line)
        if len(matches) < 2:
            continue

        dates = [f"{year}-{month}-{day}" for year, month, day in matches[:2]]
        end_date = datetime.strptime(dates[0], "%Y-%m-%d").date()
        start_date = datetime.strptime(dates[1], "%Y-%m-%d").date()
        quarter = ((start_date.month - 1) // 3) + 1

        return {
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "quarter": f"Q{quarter} {start_date.year}",
            "year": start_date.year,
        }

    return {}


def looks_like_zatca_report(file_path: str) -> bool:
    pages = extract_text_from_pdf(file_path)
    text = _normalize_text("\n".join(page.get("text", "") for page in pages))
    return (
        "ZATCA" in text.upper()
        or "القيمة المضافة" in text
        or "ضريبة" in text and "إقرار" in text
        or bool(_find_row_numbers([line.strip() for line in text.splitlines()], 13))
    )


def analyze_zatca_report(file_path: str, filename: str | None = None) -> dict | None:
    pages = extract_text_from_pdf(file_path)
    lines = [
        _normalize_text(line).strip()
        for page in pages
        for line in page.get("text", "").splitlines()
        if _normalize_text(line).strip()
    ]

    if not lines:
        return None

    sales_row = _find_row_numbers(lines, 6)
    purchases_row = _find_row_numbers(lines, 12)
    net_tax_row = _find_row_numbers(lines, 13)

    if len(sales_row) < 3 or len(purchases_row) < 3 or not net_tax_row:
        return None

    period = _parse_period(lines)
    sales_tax = sales_row[0]
    purchases_tax = purchases_row[0]
    net_tax = net_tax_row[0]

    analytics = {
        "total_sales": sales_row[-1],
        "total_purchases": purchases_row[-1],
        "sales_tax": sales_tax,
        "purchase_tax": purchases_tax,
        "net_taxes": net_tax,
        "computed_net_taxes": round((sales_tax or 0) - (purchases_tax or 0), 2),
        "quarter": period.get("quarter"),
        "period_start": period.get("period_start"),
        "period_end": period.get("period_end"),
        "year": period.get("year"),
    }

    warnings = []
    if abs(analytics["computed_net_taxes"] - net_tax) > 0.05:
        warnings.append("Computed net tax differs from the value reported in the ZATCA return.")

    return {
        "filename": filename or file_path,
        "document_type": "zatca_vat_return",
        "bank_name": "ZATCA",
        "template_name": "zatca_vat_return_v1",
        "parser_used": "zatca_vat_return_v1",
        "is_scanned": False,
        "status": "parsed" if not warnings else "parsed_with_warnings",
        "parse_confidence": 0.95,
        "quality_metrics": {
            "period_coverage_pct": 100.0 if period else 0.0,
            "tax_rows_coverage_pct": 100.0,
        },
        "warnings": warnings,
        "review_required": bool(warnings),
        "review_questions": [],
        "transaction_count": 0,
        "analytics": analytics,
        "transactions": [],
    }
