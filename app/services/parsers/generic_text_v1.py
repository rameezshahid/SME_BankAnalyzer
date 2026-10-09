from __future__ import annotations

from app.services.parser import parse_generic_text
from app.services.parsers.base import ParseResult, apply_metadata


class GenericTextV1Parser:
    parser_name = "generic_text_v1"

    def parse(self, file_path: str, detection=None) -> ParseResult:
        transactions = parse_generic_text(file_path)
        result = ParseResult(
            transactions=transactions,
            parser_name=self.parser_name,
            source_bank=getattr(detection, "bank_name", None),
            confidence=float(getattr(detection, "confidence", 0.45) or 0.45),
            warnings=list(getattr(detection, "warnings", []) or []),
            debug={"template_name": getattr(detection, "template_name", "generic_text_v1")},
        )
        return apply_metadata(result)
