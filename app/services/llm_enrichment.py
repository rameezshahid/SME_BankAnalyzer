from __future__ import annotations

from typing import Any, Dict

from app.services.ollama_client import OllamaClient

client = OllamaClient()

COUNTERPARTY_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "counterparty_name": {"type": "string"},
        "counterparty_role": {"type": "string"},
        "payment_purpose": {"type": "string"},
        "is_cash": {"type": "boolean"},
        "confidence": {"type": "number"}
    },
    "required": [
        "counterparty_name",
        "counterparty_role",
        "payment_purpose",
        "is_cash",
        "confidence"
    ]
}

CLASSIFICATION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "transaction_type": {"type": "string"},
        "direction": {"type": "string"},
        "is_cash_deposit": {"type": "boolean"},
        "is_cash_withdrawal": {"type": "boolean"},
        "confidence": {"type": "number"}
    },
    "required": [
        "transaction_type",
        "direction",
        "is_cash_deposit",
        "is_cash_withdrawal",
        "confidence"
    ]
}

SEMANTIC_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "english_translation": {"type": "string"},
        "transaction_meaning": {"type": "string"},
        "transaction_type": {"type": "string"},
        "direction": {"type": "string"},
        "is_cash_deposit": {"type": "boolean"},
        "is_cash_withdrawal": {"type": "boolean"},
        "confidence": {"type": "number"}
    },
    "required": [
        "english_translation",
        "transaction_meaning",
        "transaction_type",
        "direction",
        "is_cash_deposit",
        "is_cash_withdrawal",
        "confidence"
    ]
}


def semantic_classify_transaction(description: str, amount: float) -> Dict[str, Any]:
    """
    Intelligently classify transactions with semantic understanding.
    
    1. Translates Arabic text if needed
    2. Understands the actual meaning and context
    3. Categorizes based on semantic understanding
    """
    system = (
        "You are a banking transaction classifier that understands multilingual text. "
        "First, translate any Arabic text to English. Then, analyze the semantic meaning. "
        "Finally, classify based on understanding, not just keywords. "
        "Return only schema-valid JSON."
    )
    user = f"""
Transaction narrative (may contain Arabic):
{description}

Amount: {amount} SAR

Task:
1. If text contains Arabic, translate it to English
2. Explain the actual meaning of this transaction
3. Classify into one of these categories based on semantic understanding:
   - cash_deposit: Direct cash deposits into account
   - cash_withdrawal: Cash taken out from account (ATM, counter, etc.)
   - transfer_in: Money received from another party
   - transfer_out: Money sent to another party
   - fee: Service charges, commissions, bank fees
   - vat: Tax deductions
   - salary: Employee income received
   - pos_settlement: Point of sale settlement
   - bill_payment: Payments for utilities, services
   - loan_repayment: Loan or financing repayment
   - cheque: Cheque related
   - internal_transfer: Transfer between own accounts
   - unknown: Cannot determine

Return:
- english_translation: The English meaning of the narrative
- transaction_meaning: What this transaction actually represents
- transaction_type: The category (from list above)
- direction: 'credit' (money in) or 'debit' (money out)
- is_cash_deposit: true if cash deposit
- is_cash_withdrawal: true if cash withdrawal
- confidence: 0-1, how confident you are
"""
    return client.chat_json(system, user, SEMANTIC_SCHEMA)


def extract_counterparty(description: str) -> Dict[str, Any]:
    system = (
        "You extract structured banking data from transaction narratives. "
        "Return only schema-valid JSON."
    )
    user = f"""
Transaction narrative:
{description}

Extract:
- counterparty_name
- counterparty_role (sender, beneficiary, merchant, bank, unknown)
- payment_purpose
- is_cash
- confidence
"""
    return client.chat_json(system, user, COUNTERPARTY_SCHEMA)


def classify_transaction(description: str, amount: float) -> Dict[str, Any]:
    system = (
        "You classify bank transactions into strict categories. "
        "Return only schema-valid JSON."
    )
    user = f"""
Transaction narrative:
{description}

Amount:
{amount}

Possible transaction_type values:
cash_deposit, cash_withdrawal, transfer_in, transfer_out, fee, vat, pos_settlement,
internal_transfer, cheque, salary, unknown

Determine direction as one of:
credit, debit, unknown
"""
    return client.chat_json(system, user, CLASSIFICATION_SCHEMA)