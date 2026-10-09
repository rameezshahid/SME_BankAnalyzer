from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta


def _amount_value(transaction) -> float | None:
    try:
        return float(getattr(transaction, "amount", 0))
    except Exception:
        return None


def _direction(transaction) -> str | None:
    amount = _amount_value(transaction)
    explicit_direction = getattr(transaction, "direction", None)

    if amount is not None and amount < 0:
        return "debit"

    if explicit_direction in {"credit", "debit"}:
        return explicit_direction

    if amount is not None and amount > 0:
        return "credit"

    return None


def total_cash_deposits(transactions) -> float:
    return round(
        sum(abs(t.amount) for t in transactions if getattr(t, "is_cash_deposit", False)),
        2,
    )


def total_cash_withdrawals(transactions) -> float:
    return round(
        sum(abs(t.amount) for t in transactions if getattr(t, "is_cash_withdrawal", False)),
        2,
    )


def major_transfers_to(transactions, top_n: int = 10):
    totals = defaultdict(float)

    for t in transactions:
        if (
            _direction(t) == "debit"
            and getattr(t, "category", None) in {"transfer_out", "internal_transfer"}
            and getattr(t, "counterparty_name", None)
        ):
            totals[t.counterparty_name] += abs(t.amount)

    return [
        {"counterparty_name": name, "amount": round(amount, 2)}
        for name, amount in sorted(totals.items(), key=lambda x: x[1], reverse=True)[:top_n]
    ]


def major_deposits_by(transactions, top_n: int = 10):
    totals = defaultdict(float)

    for t in transactions:
        if (
            _direction(t) == "credit"
            and getattr(t, "category", None) in {"transfer_in", "cash_deposit"}
            and getattr(t, "counterparty_name", None)
        ):
            totals[t.counterparty_name] += abs(t.amount)

    return [
        {"counterparty_name": name, "amount": round(amount, 2)}
        for name, amount in sorted(totals.items(), key=lambda x: x[1], reverse=True)[:top_n]
    ]


def monthwise_credits(transactions):
    totals = defaultdict(float)

    for t in transactions:
        if _direction(t) == "credit" and getattr(t, "txn_date", None):
            month_key = t.txn_date.strftime("%Y-%m")
            totals[month_key] += abs(t.amount)

    return {
        month: round(amount, 2)
        for month, amount in sorted(totals.items(), key=lambda x: x[0])
    }


def monthwise_debits(transactions):
    totals = defaultdict(float)

    for t in transactions:
        if _direction(t) == "debit" and getattr(t, "txn_date", None):
            month_key = t.txn_date.strftime("%Y-%m")
            totals[month_key] += abs(t.amount)

    return {
        month: round(amount, 2)
        for month, amount in sorted(totals.items(), key=lambda x: x[0])
    }


def average_credit_balance(transactions):
    """
    Time-weighted average daily closing balance across the statement period.
    Uses the latest seen balance for each transaction date.
    Only positive balances count toward 'credit balance'.
    """
    dated_balances = []

    for t in transactions:
        txn_date = getattr(t, "txn_date", None)
        balance = getattr(t, "balance", None)
        if txn_date and balance is not None:
            dated_balances.append((txn_date.date(), float(balance)))

    if not dated_balances:
        return None

    dated_balances.sort(key=lambda x: x[0])

    daily_balance = {}
    for d, bal in dated_balances:
        daily_balance[d] = bal  # keep latest balance seen for that date

    start_date = min(daily_balance.keys())
    end_date = max(daily_balance.keys())

    total_positive_balance = 0.0
    days_count = 0

    current_day = start_date
    last_known_balance = None

    while current_day <= end_date:
        if current_day in daily_balance:
            last_known_balance = daily_balance[current_day]

        if last_known_balance is not None:
            total_positive_balance += max(last_known_balance, 0.0)
            days_count += 1

        current_day += timedelta(days=1)

    if days_count == 0:
        return None

    return round(total_positive_balance / days_count, 2)


def build_analytics(transactions):
    return {
        "total_cash_deposits": total_cash_deposits(transactions),
        "total_cash_withdrawals": total_cash_withdrawals(transactions),
        "average_credit_balance": average_credit_balance(transactions),
        "major_transfers_to": major_transfers_to(transactions),
        "major_deposits_by": major_deposits_by(transactions),
        "monthwise_credits": monthwise_credits(transactions),
        "monthwise_debits": monthwise_debits(transactions),
    }
