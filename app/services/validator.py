from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParseValidation:
    status: str
    parse_confidence: float
    warnings: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


def _ratio(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count / total, 4)


def _has_meaningful_counterparty(txn) -> bool:
    counterparty = (getattr(txn, "counterparty_name", None) or "").strip().upper()
    return bool(counterparty) and counterparty not in {"UNKNOWN", "REVIEW DESCRIPTION"}


def _needs_counterparty_for_analytics(txn) -> bool:
    category = getattr(txn, "category", None)
    return category in {"transfer_in", "transfer_out", "internal_transfer", "cash_deposit"}


def validate_transactions(transactions, detection=None) -> ParseValidation:
    total = len(transactions)
    warnings = list(getattr(detection, "warnings", []) or [])

    if total == 0:
        warnings.append("No transactions were parsed from the statement.")
        return ParseValidation(
            status="review_required",
            parse_confidence=0.0,
            warnings=warnings,
            metrics={
                "parsed_transactions": 0,
                "date_coverage_pct": 0.0,
                "amount_coverage_pct": 0.0,
                "balance_coverage_pct": 0.0,
                "classified_rows_pct": 0.0,
                "counterparty_coverage_pct": 0.0,
            },
        )

    date_count = sum(1 for txn in transactions if getattr(txn, "txn_date", None))
    amount_count = sum(1 for txn in transactions if getattr(txn, "amount", None) is not None)
    balance_count = sum(1 for txn in transactions if getattr(txn, "balance", None) is not None)
    classified_count = sum(1 for txn in transactions if getattr(txn, "category", None))
    counterparty_eligible = [
        txn for txn in transactions if _needs_counterparty_for_analytics(txn)
    ]
    counterparty_count = sum(
        1 for txn in counterparty_eligible if _has_meaningful_counterparty(txn)
    )

    date_rate = _ratio(date_count, total)
    amount_rate = _ratio(amount_count, total)
    balance_rate = _ratio(balance_count, total)
    classified_rate = _ratio(classified_count, total)
    counterparty_rate = (
        _ratio(counterparty_count, len(counterparty_eligible))
        if counterparty_eligible
        else 1.0
    )

    detector_confidence = float(getattr(detection, "confidence", 0.5) or 0.5)
    row_volume_score = 1.0 if total >= 5 else total / 5

    confidence = (
        detector_confidence * 0.25
        + row_volume_score * 0.15
        + date_rate * 0.2
        + amount_rate * 0.2
        + balance_rate * 0.1
        + max(classified_rate, counterparty_rate) * 0.1
    )
    confidence = round(max(0.0, min(confidence, 0.99)), 2)

    if total < 5:
        warnings.append("Parsed fewer than 5 transactions; confidence is limited.")
    if date_rate < 0.9:
        warnings.append("Date coverage is low; some rows may have been missed or misread.")
    if amount_rate < 0.95:
        warnings.append("Amount coverage is low; totals and analytics may be incomplete.")
    if balance_rate < 0.5:
        warnings.append("Balance coverage is low; average balance analytics may be unreliable.")
    if counterparty_eligible and counterparty_rate < 0.5:
        warnings.append("Counterparty coverage is low; major transfer/deposit analytics may be incomplete.")

    if confidence < 0.7:
        status = "review_required"
    elif confidence < 0.85:
        status = "parsed_with_warnings"
    else:
        status = "parsed"

    metrics = {
        "parsed_transactions": total,
        "date_coverage_pct": round(date_rate * 100, 2),
        "amount_coverage_pct": round(amount_rate * 100, 2),
        "balance_coverage_pct": round(balance_rate * 100, 2),
        "classified_rows_pct": round(classified_rate * 100, 2),
        "counterparty_coverage_pct": round(counterparty_rate * 100, 2),
        "counterparty_required_rows": len(counterparty_eligible),
        "template_match_confidence": round(detector_confidence, 2),
    }

    return ParseValidation(
        status=status,
        parse_confidence=confidence,
        warnings=warnings,
        metrics=metrics,
    )
