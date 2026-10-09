from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.models.transaction import Transaction


@dataclass
class ReviewOption:
    value: str
    label: str
    confidence: float | None = None


@dataclass
class ReviewQuestion:
    id: str
    scope: str
    field: str
    question: str
    options: list[ReviewOption]
    reason: str
    required: bool = False
    transaction_index: int | None = None
    current_value: str | None = None
    context: dict = field(default_factory=dict)


def _question_to_dict(question: ReviewQuestion) -> dict:
    return {
        "id": question.id,
        "scope": question.scope,
        "field": question.field,
        "question": question.question,
        "options": [option.__dict__ for option in question.options],
        "reason": question.reason,
        "required": question.required,
        "transaction_index": question.transaction_index,
        "current_value": question.current_value,
        "context": question.context,
    }


def _bank_template_question(detection) -> ReviewQuestion | None:
    if detection is None:
        return None

    if getattr(detection, "confidence", 1.0) >= 0.75 and getattr(detection, "bank_name", None):
        return None

    return ReviewQuestion(
        id="statement.template",
        scope="statement",
        field="template_name",
        question="Which bank statement template is this?",
        reason="The template detector did not find a strong known-bank match.",
        required=True,
        current_value=getattr(detection, "template_name", None),
        options=[
            ReviewOption("sabb_v1", "SABB / Saudi Awwal Bank"),
            ReviewOption("alawwal_icorp_v1", "Alawwal iCorp / SABB Arabic layout"),
            ReviewOption("alawwal_statement_v1", "Alawwal account statement"),
            ReviewOption("bsf_transaction_history_v1", "Banque Saudi Fransi transaction history"),
            ReviewOption("snb_business_v1", "Saudi National Bank business statement"),
            ReviewOption("albilad_ocr_v1", "Bank Albilad scanned/OCR"),
            ReviewOption("generic_text_v1", "Unknown text-based statement"),
            ReviewOption("unsupported", "Not listed / needs new template"),
        ],
        context={
            "detected_bank_name": getattr(detection, "bank_name", None),
            "detected_parser": getattr(detection, "parser_name", None),
            "is_scanned": getattr(detection, "is_scanned", None),
        },
    )


def _category_options(txn) -> list[ReviewOption]:
    amount = float(getattr(txn, "amount", 0) or 0)
    text = (getattr(txn, "description_raw", "") or "").upper()

    if "FEE" in text or "CHARGES" in text or "VAT" in text:
        return [
            ReviewOption("fee", "Fee / bank charge", 0.7),
            ReviewOption("vat", "VAT", 0.55),
            ReviewOption("unknown", "Not sure"),
        ]

    if amount < 0:
        return [
            ReviewOption("transfer_out", "Outgoing transfer"),
            ReviewOption("cash_withdrawal", "Cash withdrawal"),
            ReviewOption("fee", "Fee / bank charge"),
            ReviewOption("pos_settlement", "POS settlement"),
            ReviewOption("unknown", "Not sure"),
        ]

    return [
        ReviewOption("transfer_in", "Incoming transfer"),
        ReviewOption("cash_deposit", "Cash deposit"),
        ReviewOption("salary", "Salary / payroll"),
        ReviewOption("unknown", "Not sure"),
    ]


def _transaction_context(txn) -> dict:
    txn_date = getattr(txn, "txn_date", None)
    return {
        "date": txn_date.isoformat() if txn_date else None,
        "amount": getattr(txn, "amount", None),
        "balance": getattr(txn, "balance", None),
        "description": getattr(txn, "description_display", None) or getattr(txn, "description_raw", None),
        "description_raw": getattr(txn, "description_raw", None),
    }


def _ambiguous_transaction_questions(transactions, limit: int) -> list[ReviewQuestion]:
    questions: list[ReviewQuestion] = []

    for index, txn in enumerate(transactions):
        if len(questions) >= limit:
            break

        category = getattr(txn, "category", None)
        if category in {None, "", "unknown"}:
            questions.append(
                ReviewQuestion(
                    id=f"txn.{index}.category",
                    scope="transaction",
                    field="category",
                    question="What type of transaction is this?",
                    reason="The system could not determine this field from the statement text.",
                    transaction_index=index,
                    current_value=category,
                    options=_category_options(txn),
                    context=_transaction_context(txn),
                )
            )

    for index, txn in enumerate(transactions):
        if len(questions) >= limit:
            break

        category = getattr(txn, "category", None)
        counterparty = getattr(txn, "counterparty_name", None)
        if category in {"fee", "vat"}:
            continue

        if not counterparty:
            label = "transaction"
            if category in {"transfer_in", "transfer_out", "internal_transfer"}:
                label = "transfer"
            elif category:
                label = category.replace("_", " ")

            questions.append(
                ReviewQuestion(
                    id=f"txn.{index}.counterparty_name",
                    scope="transaction",
                    field="counterparty_name",
                    question=f"Who is the counterparty for this {label}?",
                    reason="The system could not determine this field from the statement text.",
                    transaction_index=index,
                    current_value=counterparty,
                    options=[
                        ReviewOption("description_contains_name", "Use the name visible in the description"),
                        ReviewOption("bank_charges", "Bank / fees / charges"),
                        ReviewOption("own_account", "Own account / internal transfer"),
                        ReviewOption("unknown", "Unknown counterparty"),
                    ],
                    context=_transaction_context(txn),
                )
            )

    return questions


def generate_review_questions(transactions, detection, validation, limit: int = 12) -> list[dict]:
    questions: list[ReviewQuestion] = []

    template_question = _bank_template_question(detection)
    if template_question:
        questions.append(template_question)

    remaining = max(0, limit - len(questions))
    questions.extend(_ambiguous_transaction_questions(transactions, remaining))

    return [_question_to_dict(question) for question in questions[:limit]]


def _parse_transaction_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def transaction_from_dict(data: dict) -> Transaction:
    txn = Transaction(
        description_raw=data.get("description_raw") or data.get("description") or "",
        amount=float(data.get("amount") or 0),
        description_normalized=data.get("description_normalized"),
        description_display=data.get("description_display"),
        txn_date=_parse_transaction_date(data.get("txn_date")),
        category=data.get("category"),
        direction=data.get("direction"),
        counterparty_name=data.get("counterparty_name"),
        counterparty_role=data.get("counterparty_role"),
        payment_purpose=data.get("payment_purpose"),
        is_cash_deposit=bool(data.get("is_cash_deposit", False)),
        is_cash_withdrawal=bool(data.get("is_cash_withdrawal", False)),
        balance=data.get("balance"),
        source_bank=data.get("source_bank"),
        parser_name=data.get("parser_name"),
        parse_confidence=data.get("parse_confidence"),
    )
    txn.warnings = list(data.get("warnings") or [])
    return txn


def apply_review_answers(transactions: list[dict], answers: list[dict]) -> tuple[list[Transaction], list[str]]:
    updated = [transaction_from_dict(txn) for txn in transactions]
    ignored: list[str] = []

    for answer in answers:
        question_id = answer.get("question_id") or answer.get("id") or ""
        value = answer.get("value")
        field = answer.get("field")
        index = answer.get("transaction_index")

        if question_id.startswith("txn."):
            parts = question_id.split(".")
            if len(parts) >= 3:
                try:
                    index = int(parts[1])
                    field = parts[2]
                except Exception:
                    ignored.append(question_id)
                    continue

        if index is None or field is None:
            ignored.append(question_id)
            continue

        if not (0 <= int(index) < len(updated)):
            ignored.append(question_id)
            continue

        txn = updated[int(index)]

        if field == "category":
            if value == "unknown":
                value = "unknown_reviewed"

            txn.category = value
            if value in {"transfer_in", "cash_deposit", "salary"}:
                txn.direction = "credit"
            elif value in {"transfer_out", "cash_withdrawal", "fee", "vat", "pos_settlement"}:
                txn.direction = "debit"
            txn.is_cash_deposit = value == "cash_deposit"
            txn.is_cash_withdrawal = value == "cash_withdrawal"
        elif field == "counterparty_name":
            if value == "own_account":
                txn.counterparty_name = "OWN ACCOUNT"
                txn.category = txn.category or "internal_transfer"
            elif value == "bank_charges":
                txn.counterparty_name = "BANK CHARGES"
            elif value == "unknown":
                txn.counterparty_name = "UNKNOWN"
            elif value == "description_contains_name":
                txn.counterparty_name = "REVIEW DESCRIPTION"
            else:
                txn.counterparty_name = value
        elif hasattr(txn, field):
            setattr(txn, field, value)
        else:
            ignored.append(question_id)

    return updated, ignored
