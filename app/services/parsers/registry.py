from __future__ import annotations

from app.services.parsers.alawwal_icorp_v1 import AlawwalIcorpV1Parser
from app.services.parsers.alawwal_statement_v1 import AlawwalStatementV1Parser
from app.services.parsers.bsf_transaction_history_v1 import BsfTransactionHistoryV1Parser
from app.services.parsers.generic_text_v1 import GenericTextV1Parser
from app.services.parsers.sabb_v1 import SabbV1Parser
from app.services.parsers.snb_business_v1 import SnbBusinessV1Parser


PARSERS = {
    "alawwal_icorp_v1": AlawwalIcorpV1Parser(),
    "alawwal_statement_v1": AlawwalStatementV1Parser(),
    "bsf_transaction_history_v1": BsfTransactionHistoryV1Parser(),
    "sabb_v1": SabbV1Parser(),
    "snb_business_v1": SnbBusinessV1Parser(),
    "generic_text_v1": GenericTextV1Parser(),
}


def get_parser(parser_name: str):
    return PARSERS.get(parser_name) or PARSERS["generic_text_v1"]


def parse_with_detected_parser(file_path: str, detection):
    parser = get_parser(getattr(detection, "parser_name", "generic_text_v1"))
    return parser.parse(file_path, detection)
