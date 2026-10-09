from __future__ import annotations

from dataclasses import dataclass, field

from app.services.parser import extract_text_from_pdf


@dataclass
class StatementDetection:
    bank_name: str | None
    template_name: str
    parser_name: str
    is_scanned: bool
    confidence: float
    warnings: list[str] = field(default_factory=list)


def _combined_text(pages: list[dict]) -> str:
    return "\n".join(page.get("text", "") for page in pages)


def detect_statement(file_path: str) -> tuple[StatementDetection, list[dict]]:
    pages = extract_text_from_pdf(file_path)
    text = _combined_text(pages)
    upper = text.upper()
    warnings: list[str] = []

    text_chars = len("".join(text.split()))
    is_scanned = text_chars < 300

    if is_scanned:
        warnings.append(
            "The PDF appears to have little extractable text. OCR support is needed for reliable scanned-statement parsing."
        )
        return StatementDetection(
            bank_name=None,
            template_name="scanned_or_image_pdf",
            parser_name="generic_text_v1",
            is_scanned=True,
            confidence=0.2,
            warnings=warnings,
        ), pages

    sabb_signals = [
        "SABB",
        "SAUDI AWWAL BANK",
        "ACCOUNT STATEMENT FOR THE PERIOD",
        "TRANSACTION DATE VALUE DATE",
        "S.NO REMARKS TRANSACTION AMOUNT",
        "BALANCE SAR",
    ]
    sabb_hits = sum(1 for signal in sabb_signals if signal in upper)

    if sabb_hits >= 3:
        return StatementDetection(
            bank_name="SABB",
            template_name="sabb_v1",
            parser_name="sabb_v1",
            is_scanned=False,
            confidence=min(0.95, 0.55 + (sabb_hits * 0.08)),
            warnings=warnings,
        ), pages

    snb_signals = [
        "SAUDI NATIONAL BANK",
        "BALANCE CREDIT/DEBIT TRANSACTION DESCRIPTION",
        "SPANMRC",
        "SFEEMRC",
        "ACCOUNT STATEMENT",
    ]
    snb_hits = sum(1 for signal in snb_signals if signal in upper)

    if snb_hits >= 2:
        return StatementDetection(
            bank_name="Saudi National Bank",
            template_name="snb_business_v1",
            parser_name="snb_business_v1",
            is_scanned=False,
            confidence=min(0.92, 0.55 + (snb_hits * 0.08)),
            warnings=warnings,
        ), pages

    alawwal_statement_signals = [
        "SAUDI AWWAL BANK",
        "DATE TRANSACTION TYPE NARRATIVES DEBIT CREDIT BALANCE",
        "TRANSACTION DETAILS",
        "STATEMENT REFERENCE NUMBER",
    ]
    alawwal_statement_hits = sum(1 for signal in alawwal_statement_signals if signal in upper)

    if alawwal_statement_hits >= 2:
        return StatementDetection(
            bank_name="Alawwal Bank",
            template_name="alawwal_statement_v1",
            parser_name="alawwal_statement_v1",
            is_scanned=False,
            confidence=min(0.94, 0.58 + (alawwal_statement_hits * 0.08)),
            warnings=warnings,
        ), pages

    bsf_signals = [
        "TRANSACTIONS LIST",
        "FRANSICORP",
        "BANK SAUDI FRANSI",
        "BSF",
        "TRANSACTION VALUE DATE",
    ]
    bsf_hits = sum(1 for signal in bsf_signals if signal in upper)

    if bsf_hits >= 3:
        return StatementDetection(
            bank_name="Banque Saudi Fransi",
            template_name="bsf_transaction_history_v1",
            parser_name="bsf_transaction_history_v1",
            is_scanned=False,
            confidence=min(0.94, 0.58 + (bsf_hits * 0.07)),
            warnings=warnings,
        ), pages

    alawwal_signals = [
        "SABBSARI",
        "CURRENT ACCOUNT",
        "POS 04/",
        "ﻝﻭ ﻷﺍ",
    ]
    alawwal_hits = sum(1 for signal in alawwal_signals if signal in upper)

    if alawwal_hits >= 2:
        return StatementDetection(
            bank_name="Alawwal Bank",
            template_name="alawwal_icorp_v1",
            parser_name="alawwal_icorp_v1",
            is_scanned=False,
            confidence=min(0.92, 0.55 + (alawwal_hits * 0.08)),
            warnings=warnings,
        ), pages

    generic_signals = [
        "TRANSACTION",
        "DATE",
        "BALANCE",
        "DEBIT",
        "CREDIT",
        "DR",
        "CR",
        "AMOUNT",
    ]
    generic_hits = sum(1 for signal in generic_signals if signal in upper)

    warnings.append(
        "No known bank template matched strongly. Used generic text parsing; review results before relying on analytics."
    )

    return StatementDetection(
        bank_name=None,
        template_name="generic_text_v1",
        parser_name="generic_text_v1",
        is_scanned=False,
        confidence=min(0.65, 0.25 + (generic_hits * 0.05)),
        warnings=warnings,
    ), pages
