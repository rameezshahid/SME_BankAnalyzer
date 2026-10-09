from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Transaction:
    description_raw: str
    amount: float
    description_normalized: str | None = None
    description_display: str | None = None
    txn_date: datetime | None = None

    category: str | None = None
    direction: str | None = None

    counterparty_name: str | None = None
    counterparty_role: str | None = None
    payment_purpose: str | None = None

    is_cash_deposit: bool = False
    is_cash_withdrawal: bool = False

    balance: float | None = None

    source_bank: str | None = None
    parser_name: str | None = None
    parse_confidence: float | None = None
    warnings: list[str] = field(default_factory=list)
    
    # Semantic understanding fields
    semantic_translation: str | None = None
    semantic_meaning: str | None = None
    enrichment_error: str | None = None
