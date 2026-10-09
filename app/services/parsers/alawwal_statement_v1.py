from __future__ import annotations

from app.services.parser import parse_alawwal_statement_text
from app.services.parsers.base import ParseResult, apply_metadata


class AlawwalStatementV1Parser:
    parser_name = "alawwal_statement_v1"

    def parse(self, file_path: str, detection=None) -> ParseResult:
        transactions = parse_alawwal_statement_text(file_path)
        result = ParseResult(
            transactions=transactions,
            parser_name=self.parser_name,
            source_bank=getattr(detection, "bank_name", "Alawwal Bank"),
            confidence=float(getattr(detection, "confidence", 0.88) or 0.88),
            warnings=list(getattr(detection, "warnings", []) or []),
            debug={"template_name": getattr(detection, "template_name", "alawwal_statement_v1")},
        )
        return apply_metadata(result)
