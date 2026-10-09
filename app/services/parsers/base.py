from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ParseResult:
    transactions: list
    parser_name: str
    source_bank: str | None = None
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)
    rejected_lines: list[str] = field(default_factory=list)
    debug: dict = field(default_factory=dict)


class StatementParser(Protocol):
    parser_name: str

    def parse(self, file_path: str, detection=None) -> ParseResult:
        ...


def apply_metadata(result: ParseResult) -> ParseResult:
    for txn in result.transactions:
        txn.parser_name = result.parser_name
        txn.source_bank = result.source_bank
        txn.parse_confidence = result.confidence
        txn.warnings.extend(result.warnings)
    return result
