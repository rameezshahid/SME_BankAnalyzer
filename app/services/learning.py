from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.services.text_normalization import matching_text


LEARNING_DIR = Path("data")
# Rules learned from review answers can contain real counterparty names, so the
# live file is git-ignored and starts from the committed seed rules.
RULES_PATH = LEARNING_DIR / "learning_rules.json"
SEED_RULES_PATH = LEARNING_DIR / "learning_rules.seed.json"

GENERIC_TOKENS = {
    "NMSC",
    "PAYMENT",
    "TRANSFER",
    "LOCAL",
    "SARIE",
    "DETAILS",
    "ACCOUNT",
    "BANK",
    "DATE",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_learning_rules() -> list[dict]:
    path = RULES_PATH if RULES_PATH.exists() else SEED_RULES_PATH
    if not path.exists():
        return []

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_learning_rules(rules: list[dict]) -> None:
    LEARNING_DIR.mkdir(exist_ok=True)
    RULES_PATH.write_text(
        json.dumps(rules, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _normalize_text(value: str | None) -> str:
    return " ".join((value or "").upper().split())


def _contains_safe_pattern(description: str, pattern: str) -> bool:
    return _normalize_text(pattern) in _normalize_text(description)


def _extract_regex_value(pattern: str, description: str) -> str | None:
    match = re.search(pattern, description or "", re.IGNORECASE)
    if not match:
        return None
    value = match.group(1).strip()
    return " ".join(value.split()).upper()


def apply_learned_rules(txn):
    description = " ".join(
        part for part in [
            getattr(txn, "description_raw", "") or "",
            getattr(txn, "description_display", "") or "",
            getattr(txn, "description_normalized", "") or "",
            matching_text(getattr(txn, "description_raw", "") or ""),
        ]
        if part
    )
    rules = load_learning_rules()
    changed = False

    for rule in sorted(rules, key=lambda item: item.get("confidence", 0), reverse=True):
        if not rule.get("enabled", True):
            continue

        field = rule.get("field")
        value = rule.get("value")
        pattern = rule.get("pattern")
        match_type = rule.get("match_type")

        if not field or not pattern:
            continue

        current_value = getattr(txn, field, None)
        if current_value not in {None, "", "unknown"}:
            continue

        matched_value = None
        if match_type == "contains" and _contains_safe_pattern(description, pattern):
            matched_value = value
        elif match_type == "regex_extract":
            matched_value = _extract_regex_value(pattern, description)
        elif match_type == "regex_value" and re.search(pattern, description, re.IGNORECASE):
            matched_value = value

        if not matched_value:
            continue

        if field == "category":
            matched_value = matched_value.lower()

        setattr(txn, field, matched_value)
        changed = True

        if field == "category":
            if matched_value in {"transfer_in", "cash_deposit", "salary"}:
                txn.direction = txn.direction or "credit"
            elif matched_value in {
                "transfer_out",
                "salary_payment",
                "cash_withdrawal",
                "fee",
                "vat",
                "bill_payment",
                "pos_settlement",
                "loan_repayment",
            }:
                txn.direction = txn.direction or "debit"

        rule["use_count"] = int(rule.get("use_count", 0)) + 1
        rule["updated_at"] = _now_iso()

    if changed:
        save_learning_rules(rules)

    return txn


def _safe_category_patterns(description: str, value: str) -> list[tuple[str, str]]:
    text = _normalize_text(description)
    patterns: list[tuple[str, str]] = []

    keyword_map = [
        ("PAYROLL", "salary_payment"),
        ("SALARY", "salary_payment"),
        ("دفع رواتب", "salary_payment"),
        ("رواتب", "salary_payment"),
        ("DISCOUNTING PAYMENT", "invoice_discounting"),
        ("INSTALLMENT REPAYMENT", "loan_repayment"),
        ("FINANCE REPAYMENT", "loan_repayment"),
        ("TAWARRUQ FINANCE REPAY", "loan_repayment"),
        ("تمويل تورق", "loan_repayment"),
        ("تورق", "loan_repayment"),
        ("SADAD", "bill_payment"),
        ("BILLER:", "bill_payment"),
        ("SFEEMRC", "fee"),
        ("SPANMRC", "pos_settlement"),
        ("ALL POS", "pos_settlement"),
        ("ﻊﻴﺒﻟﺍ ﻁﺎﻘﻧ", "pos_settlement"),
        ("CHARGES", "fee"),
        (" VAT", "fee"),
        ("عموله", "fee"),
        ("عمولة", "fee"),
        ("ATM", "cash_deposit"),
        ("صراف آلي", "cash_deposit"),
        ("ضريبة", "vat"),
        ("القيمة المضافة", "vat"),
        ("ﺔﺒﻳﺮﺿ", "vat"),
        ("ﺔﻓﺎﻀﻤﻟﺍ ﺔﻤﻴﻘﻟﺍ", "vat"),
    ]

    for keyword, suggested_value in keyword_map:
        if keyword in text and value == suggested_value:
            patterns.append(("contains", keyword))

    # Bank trade codes are safer when paired with a user label, but never learn from NMSC alone.
    trade_match = re.search(r"\b(BANKTRADE\s+[A-Z0-9]+\s+\d+\s+[A-Z]{4})\b", text)
    if trade_match and value not in {"unknown", "unknown_reviewed"}:
        patterns.append(("contains", trade_match.group(1)))

    return patterns


def _safe_counterparty_patterns(description: str, value: str) -> list[tuple[str, str, str]]:
    text = description or ""
    patterns: list[tuple[str, str, str]] = []

    if re.search(r"/Biller:", text, re.IGNORECASE):
        patterns.append(("counterparty_name", "regex_extract", r"/Biller:([^/|]+)"))

    if re.search(r"/BEN:", text, re.IGNORECASE):
        patterns.append((
            "counterparty_name",
            "regex_extract",
            r"/BEN:([^|]+?)(?:/BEN ACC|/BEN ADDRESS|/BEN BANK|/DUE|/INVOICE|$)",
        ))

    if re.search(r"/REM:", text, re.IGNORECASE) and value not in {"UNKNOWN", "REVIEW DESCRIPTION"}:
        escaped_value = re.escape(value)
        patterns.append(("counterparty_name", "regex_value", escaped_value))

    normalized_value = _normalize_text(value)
    if (
        len(normalized_value) >= 4
        and normalized_value not in GENERIC_TOKENS
        and normalized_value in _normalize_text(text)
    ):
        patterns.append(("counterparty_name", "contains", normalized_value))

    return patterns


def _upsert_rule(rules: list[dict], field: str, match_type: str, pattern: str, value: str) -> None:
    normalized_pattern = _normalize_text(pattern) if match_type == "contains" else pattern
    normalized_value = _normalize_text(value)

    if normalized_pattern in GENERIC_TOKENS or not normalized_pattern:
        return

    now = _now_iso()
    for rule in rules:
        if (
            rule.get("field") == field
            and rule.get("match_type") == match_type
            and rule.get("pattern") == normalized_pattern
        ):
            if rule.get("value") != normalized_value:
                rule["correction_count"] = int(rule.get("correction_count", 0)) + 1
                rule["value"] = normalized_value
            rule["confidence"] = min(1.0, float(rule.get("confidence", 0.8)) + 0.03)
            rule["updated_at"] = now
            return

    rules.append({
        "id": uuid4().hex,
        "field": field,
        "match_type": match_type,
        "pattern": normalized_pattern,
        "value": normalized_value,
        "confidence": 0.85,
        "enabled": True,
        "source": "user_review",
        "use_count": 0,
        "correction_count": 0,
        "created_at": now,
        "updated_at": now,
    })


def learn_from_review_answers(transactions: list[dict], answers: list[dict]) -> list[dict]:
    rules = load_learning_rules()
    learned: list[dict] = []

    for answer in answers:
        field = answer.get("field")
        value = answer.get("value")
        index = answer.get("transaction_index")
        question_id = answer.get("question_id") or answer.get("id") or ""

        if question_id.startswith("txn."):
            parts = question_id.split(".")
            if len(parts) >= 3:
                try:
                    index = int(parts[1])
                    field = parts[2]
                except Exception:
                    continue

        if index is None or not (0 <= int(index) < len(transactions)):
            continue

        txn = transactions[int(index)]
        description = " ".join(
            part for part in [
                txn.get("description_raw") or "",
                txn.get("description_display") or "",
                txn.get("description_normalized") or "",
                matching_text(txn.get("description_raw") or ""),
            ]
            if part
        )

        if field == "category" and value:
            stored_value = "unknown_reviewed" if value == "unknown" else value
            for match_type, pattern in _safe_category_patterns(description, stored_value):
                _upsert_rule(rules, "category", match_type, pattern, stored_value)
                learned.append({"field": "category", "match_type": match_type, "pattern": pattern, "value": stored_value})

        if field == "counterparty_name" and value:
            stored_value = {
                "bank_charges": "BANK CHARGES",
                "own_account": "OWN ACCOUNT",
                "unknown": "UNKNOWN",
                "description_contains_name": "REVIEW DESCRIPTION",
            }.get(value, value)

            for rule_field, match_type, pattern in _safe_counterparty_patterns(description, stored_value):
                _upsert_rule(rules, rule_field, match_type, pattern, stored_value)
                learned.append({
                    "field": rule_field,
                    "match_type": match_type,
                    "pattern": pattern,
                    "value": stored_value,
                })

    save_learning_rules(rules)
    return learned
