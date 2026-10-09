from __future__ import annotations

from app.services.parser import parse_sabb_text
from app.services.parsers.base import ParseResult, apply_metadata


class SabbV1Parser:
    parser_name = "sabb_v1"

    def parse(self, file_path: str, detection=None) -> ParseResult:
        transactions = parse_sabb_text(file_path)
        result = ParseResult(
            transactions=transactions,
            parser_name=self.parser_name,
            source_bank=getattr(detection, "bank_name", "SABB"),
            confidence=float(getattr(detection, "confidence", 0.9) or 0.9),
            warnings=list(getattr(detection, "warnings", []) or []),
            debug={"template_name": getattr(detection, "template_name", "sabb_v1")},
        )
        return apply_metadata(result)
