from __future__ import annotations

import json
import os
import re
from pathlib import Path

from app.services.llm_enrichment import classify_transaction, extract_counterparty
from app.services.text_normalization import matching_text, normalize_arabic_text


TRANSFER_KEYWORDS = [
    "TRANSFER",
    "OUTGOING TRANSFER",
    "SARIE",
    "AC TO AC TRANSFER",
    "TRF FROM",
    "IPS",
    "BEN",
    "REM",
    "INCOME",
    "حوالة",
    "تحويل",
    "صادرة",
    "واردة",
    "حوالة",
    "تحويل",
]

FEE_KEYWORDS = [
    "CHARGES AND FEES",
    "CHARGES",
    " FEE ",
    " VAT ",
    "ضريبة",
    "القيمة المضافة",
    "ﺔﺒﻳﺮﺿ",
    "ﺔﻓﺎﻀﻤﻟﺍ ﺔﻤﻴﻘﻟﺍ",
    "رسوم",
    "تعاب",
    "رسم",
    "عمولة",
    "عموله",
]

CASH_DEPOSIT_KEYWORDS = [
    "CASH DEPOSIT",
    "CASH TRANSFER",
    "ايداع نقدي",
    "إيداع نقدي",
    "ايداع",
]

CASH_WITHDRAWAL_KEYWORDS = [
    "CASH WITHDRAWAL",
    "سحب نقدي",
    "سحب",
]

SALARY_KEYWORDS = [
    "PAYROLL",
    "SALARY",
    "دفع رواتب",
    "رواتب",
    "راتب",
]

TAWARRUQ_KEYWORDS = [
    "TAWARRUQ FINANCE REPAY",
    "تمويل تورق",
    "تورق",
]

ATM_KEYWORDS = [
    "ATM",
    "صراف آلي",
    "صراف",
]

SKIP_PARTS = {
    "TRANSFER",
    "OUTGOING TRANSFER- SARIE",
    "OUTGOING TRANSFER",
    "AC TO AC TRANSFER",
    "CHARGES AND FEES",
    "CHARGES",
    "SAB ICORP",
    "HEAD OFFICE RIYADH",
    "HEAD OFFICE NEW YORK",
    "SYSTEM GENERATED",
    "VDU",
    "NMSC",
}

# The account holder's own name(s), so internal transfers are not reported as
# counterparties. Comma-separated, e.g. OWN_ACCOUNT_NAMES="MY COMPANY CO LTD".
OWN_ACCOUNT_NAMES = {
    " ".join(name.split()).upper()
    for name in os.getenv("OWN_ACCOUNT_NAMES", "").split(",")
    if name.strip()
}

# Banks truncate long beneficiary names (often to ~24 chars). Optional aliases
# map a truncated name to the full one: {"ACME TRADING INTERNAT": "ACME TRADING INTERNATIONAL"}.
COUNTERPARTY_ALIASES_PATH = Path("data") / "counterparty_aliases.json"


def _load_counterparty_aliases() -> dict[str, str]:
    if not COUNTERPARTY_ALIASES_PATH.exists():
        return {}
    try:
        raw = json.loads(COUNTERPARTY_ALIASES_PATH.read_text(encoding="utf-8"))
        return {" ".join(k.split()).upper(): v for k, v in raw.items()}
    except Exception:
        return {}


COUNTERPARTY_ALIASES = _load_counterparty_aliases()


def normalize_counterparty_name(name: str | None) -> str | None:
    if not name:
        return None

    cleaned = " ".join(name.strip().split()).upper()

    return COUNTERPARTY_ALIASES.get(cleaned, cleaned)


def is_probably_identifier(text: str) -> bool:
    t = text.strip()

    if not t:
        return True

    upper = t.upper()

    if upper.startswith(("LP ", "HIB-", "PAYREF:", "ORIG-REF:", "UTI :", "EX RATE", "TO ", "ATMTOT")):
        return True

    if upper == "NMSC":
        return True

    if "BALANCE SAR" in upper:
        return True

    normalized_upper = normalize_arabic_text(t).upper()
    if normalized_upper != upper and "BALANCE SAR" in normalized_upper:
        return True

    if re.search(r"\d{2}/\d{2}/\d{4}", upper):
        return True

    if t.replace(",", "").replace(".", "").isdigit():
        return True

    return False


def extract_counterparty_rule_based(description: str) -> str | None:
    if not description:
        return None

    search_description = matching_text(description)

    biller_match = re.search(r"/Biller:([^/|]+)", search_description, re.IGNORECASE)
    if biller_match:
        biller = biller_match.group(1).strip()
        if biller and not is_probably_identifier(biller):
            return normalize_counterparty_name(biller)

    if "DISCOUNTING PAYMENT" in search_description.upper():
        return "BANK SAUDI FRANSI"

    finance_bank_match = re.search(r"REPAYMENT\s*FROM\s+([A-Z ]+BANK)", search_description, re.IGNORECASE)
    if finance_bank_match:
        return normalize_counterparty_name(finance_bank_match.group(1))

    beneficiary_name = extract_arabic_beneficiary_name(search_description)
    if beneficiary_name:
        return normalize_counterparty_name(beneficiary_name)

    rem_match = re.search(r"/REM:([^|]+)", search_description, re.IGNORECASE)
    if rem_match:
        rem_text = rem_match.group(1).strip()
        rem_parts = [part.strip() for part in rem_text.split("/") if part.strip()]
        for part in reversed(rem_parts):
            upper = part.upper()
            if not is_probably_identifier(part) and "IBAN" not in upper and len(part) >= 4:
                return normalize_counterparty_name(part)

    ben_match = re.search(r"/BEN:([^|]+?)(?:/BEN ACC|/BEN ADDRESS|/BEN BANK|/DUE|/INVOICE|$)", search_description, re.IGNORECASE)
    if ben_match:
        ben_text = ben_match.group(1).strip()
        if ben_text and not is_probably_identifier(ben_text):
            return normalize_counterparty_name(ben_text)

    parts = [p.strip() for p in search_description.split("|") if p.strip()]
    normalized_parts = [" ".join(p.split()) for p in parts]

    candidates: list[str] = []

    for part in normalized_parts:
        upper = part.upper()

        if upper in SKIP_PARTS:
            continue

        if upper in OWN_ACCOUNT_NAMES:
            continue

        if any(x in upper for x in [
            "BALANCE SAR",
            "EX RATE",
            "SAB ICORP",
            "HEAD OFFICE",
            "PAYREF",
            "ORIG-REF",
            "UTI",
            "SYSTEM GENERATED",
        ]):
            continue

        if is_probably_identifier(part):
            continue

        if len(part) < 4:
            continue

        candidates.append(part)

    if not candidates:
        return None

    # Prefer business-looking names
    priority_terms = [
        "LTD", "LLC", "CO", "COMPANY", "INTERNATIONAL", "IRELAND",
        "SAUDI", "TRADING", "BANK", "ENTERPRISE", "SARL", "EQUIP"
    ]

    for candidate in candidates:
        upper = candidate.upper()
        if upper in OWN_ACCOUNT_NAMES:
            continue
        if any(term in upper for term in priority_terms):
            return normalize_counterparty_name(candidate)

    for candidate in candidates:
        upper = candidate.upper()
        if upper not in OWN_ACCOUNT_NAMES:
            return normalize_counterparty_name(candidate)

    return None


def extract_payment_purpose_rule_based(description: str) -> str | None:
    if not description:
        return None

    parts = [p.strip() for p in matching_text(description).split("|") if p.strip()]
    lowered_parts = [p.lower() for p in parts]

    for original, lowered in zip(parts, lowered_parts):
        if "business" in lowered:
            return original
        if "buying goods" in lowered:
            return original
        if "payment" in lowered:
            return original
        if "incentive" in lowered:
            return original
        if "invoice" in lowered:
            return original

    return None


def extract_arabic_beneficiary_name(description: str) -> str | None:
    parts = [p.strip() for p in description.split("|") if p.strip()]

    for index, part in enumerate(parts):
        if "عنوان المستفيد" not in part:
            continue

        candidate = part.split("عنوان المستفيد", 1)[1]
        candidate = re.split(r"\b\d[\d,.]*\b|الدفع|المبلغ|مبلغ", candidate, maxsplit=1)[0]
        candidate = " ".join(candidate.split())

        next_part = parts[index + 1].strip() if index + 1 < len(parts) else ""
        if next_part and re.fullmatch(r"[\u0600-\u06ff\s]+", next_part):
            if not any(token in next_part for token in ["رقم", "تاريخ", "ضريبة", "القيمة", "المرجع"]):
                candidate = f"{candidate} {next_part}".strip()

        if candidate and len(candidate) >= 4 and not is_probably_identifier(candidate):
            return candidate

    return None


def infer_category_rule_based(description: str, amount: float | None = None) -> tuple[str | None, str | None]:
    normalized_description = matching_text(description)
    text = normalized_description.upper()
    signed_amount = float(amount or 0)

    # Check for cash deposits first (both English and Arabic)
    if any(k.upper() in text for k in CASH_DEPOSIT_KEYWORDS):
        return "cash_deposit", "credit"

    # Check for cash withdrawals (both English and Arabic)
    if any(k.upper() in text for k in CASH_WITHDRAWAL_KEYWORDS):
        return "cash_withdrawal", "debit"

    # Check for ATM transactions
    if any(k.upper() in text for k in ATM_KEYWORDS):
        return ("cash_deposit", "credit") if signed_amount > 0 else ("cash_withdrawal", "debit")

    # Check for fees and VAT (including عموله)
    if any(k.upper() in text for k in FEE_KEYWORDS) or "CHARGES" in text:
        if "VAT" in text or "ضريبة" in normalized_description or "القيمة المضافة" in normalized_description:
            return "vat", "debit"
        return "fee", "debit"

    # Check for salary/payroll (including دفع رواتب)
    if any(k.upper() in text for k in SALARY_KEYWORDS):
        return ("salary_payment", "debit") if signed_amount < 0 else ("salary", "credit")

    # Check for Tawarruq financing (Islamic finance)
    if any(k.upper() in text for k in TAWARRUQ_KEYWORDS):
        return "loan_repayment", "debit"

    # Check for bill payments
    if "SADAD" in text or "BILLER:" in text:
        return "bill_payment", "debit"

    # Check for discounting payments
    if "DISCOUNTING PAYMENT" in text:
        return "invoice_discounting", "credit"

    # Check for POS settlement
    if "POS" in text and (
        "SETL" in text
        or "ALL POS" in text
        or "نقاط البيع" in normalized_description
        or "ﻊﻴﺒﻟﺍ ﻁﺎﻘﻧ" in normalized_description
        or signed_amount > 0
    ):
        return "pos_settlement", "debit" if signed_amount < 0 else "credit"

    # Check for transfers (must be after specific checks to avoid false positives)
    if (
        abs(signed_amount) > 10
        and (any(k.upper() in text for k in TRANSFER_KEYWORDS) or "BEN:" in text or "REM:" in text)
    ):
        return ("transfer_out", "debit") if signed_amount < 0 else ("transfer_in", "credit")

    # Handle INCOME keyword with larger amounts as transfer_in
    if "INCOME" in text and signed_amount > 0:
        return "transfer_in", "credit"

    # Generic transfer keywords for amounts > 10
    if abs(signed_amount) > 10 and (any(k in text for k in TRANSFER_KEYWORDS) or "BEN:" in text or "REM:" in text):
        return ("transfer_out", "debit") if signed_amount < 0 else ("transfer_in", "credit")

    return None, "debit" if signed_amount < 0 else "credit"


def default_counterparty_for_category(category: str | None, description: str | None = None) -> str | None:
    text = matching_text(description).upper()

    if category in {"fee", "vat"}:
        return "BANK CHARGES"

    if category == "bill_payment":
        biller_match = re.search(r"/Biller:([^/|]+)", matching_text(description), re.IGNORECASE)
        if biller_match:
            return normalize_counterparty_name(biller_match.group(1).strip())

    if category == "salary_payment":
        return "PAYROLL"

    if category == "pos_settlement":
        return "POS NETWORK"

    if category == "loan_repayment":
        bank_match = re.search(r"\b(?:FROM|TO)\s+([A-Z ]+BANK)\b", text, re.IGNORECASE)
        if bank_match:
            return normalize_counterparty_name(bank_match.group(1))
        if "ALINMA BANK" in text:
            return "ALINMA BANK"

    if "DEBIT COMPANY: BANK SAUDI FRANSI" in text:
        return "BANK SAUDI FRANSI"

    return None


def should_llm_enrich(description: str, category=None, counterparty_name=None) -> bool:
    text = matching_text(description).upper()

    if any(k in text for k in FEE_KEYWORDS):
        return False

    if category in {"fee", "vat", "pos_settlement", "bill_payment", "salary_payment", "invoice_discounting"}:
        return False

    if category not in {None, "", "unknown", "transfer_in", "transfer_out", "internal_transfer"}:
        return False

    if category in {None, "", "unknown"}:
        return True

    if counterparty_name:
        return False

    return any(k in text for k in TRANSFER_KEYWORDS) or "BEN:" in text or "REM:" in text


def enrich_transaction(txn, use_llm: bool = True):
    text = matching_text(txn.description_raw).upper()
    category_hint, direction_hint = infer_category_rule_based(txn.description_raw, getattr(txn, "amount", None))

    if any(k.upper() in text for k in FEE_KEYWORDS) and category_hint in {"fee", "vat"}:
        if not txn.category:
            txn.category = category_hint or "fee"
        if not txn.direction:
            txn.direction = "debit"
        if not getattr(txn, "counterparty_name", None):
            txn.counterparty_name = default_counterparty_for_category(txn.category, txn.description_raw)
        txn.is_cash_deposit = False
        txn.is_cash_withdrawal = False
        return txn

    if not getattr(txn, "counterparty_name", None):
        rule_name = extract_counterparty_rule_based(txn.description_raw)
        if rule_name and rule_name not in SKIP_PARTS:
            txn.counterparty_name = normalize_counterparty_name(rule_name)

    if not getattr(txn, "payment_purpose", None):
        purpose = extract_payment_purpose_rule_based(txn.description_raw)
        if purpose:
            txn.payment_purpose = purpose

    if txn.category in (None, "", "unknown"):
        if category_hint:
            txn.category = category_hint
        if direction_hint and not txn.direction:
            txn.direction = direction_hint

    if not getattr(txn, "counterparty_name", None):
        default_counterparty = default_counterparty_for_category(txn.category, txn.description_raw)
        if default_counterparty:
            txn.counterparty_name = default_counterparty
    elif txn.category in {"salary_payment", "pos_settlement"}:
        txn.counterparty_name = default_counterparty_for_category(txn.category, txn.description_raw)

    if use_llm and txn.category in (None, "", "unknown"):
        try:
            cls = classify_transaction(txn.description_raw, abs(txn.amount))
            if cls.get("confidence", 0) >= 0.75:
                txn.category = cls["transaction_type"]
                txn.direction = cls["direction"]
                txn.is_cash_deposit = cls["is_cash_deposit"]
                txn.is_cash_withdrawal = cls["is_cash_withdrawal"]
        except Exception as e:
            txn.enrichment_error = f"classification_error: {e}"

    if (
        not getattr(txn, "counterparty_name", None)
        and txn.category in {"transfer_in", "transfer_out", "internal_transfer", None, "", "unknown"}
        and any(k in text for k in TRANSFER_KEYWORDS)
        and use_llm
    ):
        try:
            cp = extract_counterparty(txn.description_raw)
            if cp.get("confidence", 0) >= 0.75:
                llm_name = normalize_counterparty_name(cp["counterparty_name"])
                if llm_name not in OWN_ACCOUNT_NAMES:
                    txn.counterparty_name = llm_name
                txn.counterparty_role = cp["counterparty_role"]
                if not getattr(txn, "payment_purpose", None):
                    txn.payment_purpose = cp["payment_purpose"]
        except Exception as e:
            txn.enrichment_error = f"counterparty_error: {e}"

    txn.counterparty_name = normalize_counterparty_name(getattr(txn, "counterparty_name", None))

    if txn.counterparty_name in OWN_ACCOUNT_NAMES:
        txn.counterparty_name = None

    return txn
