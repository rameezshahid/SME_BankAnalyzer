from __future__ import annotations

from app.services.parser import parse_snb_business_text
from app.services.parsers.base import ParseResult, apply_metadata


class SnbBusinessV1Parser:
    parser_name = "snb_business_v1"

    def parse(self, file_path: str, detection=None) -> ParseResult:
        transactions = parse_snb_business_text(file_path)
        result = ParseResult(
            transactions=transactions,
            parser_name=self.parser_name,
            source_bank=getattr(detection, "bank_name", "Saudi National Bank"),
            confidence=float(getattr(detection, "confidence", 0.85) or 0.85),
            warnings=list(getattr(detection, "warnings", []) or []),
            debug={"template_name": getattr(detection, "template_name", "snb_business_v1")},
        )
        return apply_metadata(result)
