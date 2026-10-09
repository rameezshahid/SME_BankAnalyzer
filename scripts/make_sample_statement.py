"""Generate a synthetic bank statement PDF for trying out the analyzer.

All names, numbers and accounts are made up. The layout mimics the SABB
text-PDF format so the template detector and `sabb_v1` parser pick it up.

Usage:
    python scripts/make_sample_statement.py            # -> samples/sample_statement.pdf
    python scripts/make_sample_statement.py out.pdf
"""
from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


OPENING_BALANCE = 100_000.00

# (date, headline, DR/CR, amount, detail lines)
TRANSACTIONS = [
    ("01/04/2025", "TRANSFER", "CR", 48_500.00, ["DEMO CUSTOMER LLC", "INVOICE 1042"]),
    ("03/04/2025", "OUTGOING TRANSFER- SARIE", "DR", 12_750.00, ["SAMPLE SUPPLIES TRADING CO", "BUYING GOODS"]),
    ("03/04/2025", "CHARGES AND FEES", "DR", 5.75, ["SARIE TRANSFER FEE"]),
    ("10/04/2025", "CASH DEPOSIT", "CR", 20_000.00, []),
    ("25/04/2025", "PAYROLL", "DR", 38_000.00, ["APRIL SALARIES"]),
    ("02/05/2025", "TRANSFER", "CR", 61_200.00, ["EXAMPLE HOLDINGS CO"]),
    ("08/05/2025", "OUTGOING TRANSFER- SARIE", "DR", 22_400.00, ["PLACEHOLDER LOGISTICS LLC"]),
    ("15/05/2025", "CASH WITHDRAWAL", "DR", 5_000.00, []),
    ("25/05/2025", "PAYROLL", "DR", 38_000.00, ["MAY SALARIES"]),
    ("03/06/2025", "TRANSFER", "CR", 54_300.00, ["DEMO CUSTOMER LLC", "INVOICE 1077"]),
    ("12/06/2025", "OUTGOING TRANSFER- SARIE", "DR", 18_900.00, ["SAMPLE SUPPLIES TRADING CO"]),
    ("15/06/2025", "CASH DEPOSIT", "CR", 15_000.00, []),
    ("25/06/2025", "PAYROLL", "DR", 38_000.00, ["JUNE SALARIES"]),
]


def build_lines() -> list[str]:
    lines = [
        "SYNTHETIC SAMPLE STATEMENT - SABB LAYOUT - NOT REAL DATA",
        "Account Statement for the period 01/04/2025 to 30/06/2025",
        "Account Name: DEMO TRADING EST      Account Number: 000000000001",
        f"Opening Balance SAR {OPENING_BALANCE:,.2f}",
        "",
        "Transaction Date Value Date",
        "S.No Remarks Transaction Amount",
    ]

    balance = OPENING_BALANCE
    for sno, (date, headline, drcr, amount, details) in enumerate(TRANSACTIONS, start=1):
        balance += amount if drcr == "CR" else -amount
        lines.append(f"{sno} {date} {date} {headline} {drcr} {amount:,.2f}")
        lines.append(f"Balance SAR {balance:,.2f}")
        lines.extend(details)

    lines += [
        "",
        f"Closing Balance SAR {balance:,.2f}",
        "This is a computer generated statement",
    ]
    return lines


def write_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(path), pagesize=A4)
    _, height = A4
    top, bottom, step = height - 50, 50, 14
    y = top

    pdf.setFont("Helvetica", 9)
    for line in build_lines():
        if y < bottom:
            pdf.showPage()
            pdf.setFont("Helvetica", 9)
            y = top
        pdf.drawString(50, y, line)
        y -= step

    pdf.save()


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("samples") / "sample_statement.pdf"
    write_pdf(out)
    print(f"Wrote {out}")
