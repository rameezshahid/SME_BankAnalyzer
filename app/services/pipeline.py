from __future__ import annotations

from dataclasses import dataclass

from app.services.analytics import build_analytics
from app.services.detector import detect_statement
from app.services.parsers.registry import parse_with_detected_parser
from app.services.processor import process_transactions
from app.services.review import generate_review_questions
from app.services.validator import validate_transactions


@dataclass
class PipelineResult:
    detection: object
    parse_result: object
    transactions: list
    validation: object
    analytics: dict
    review_questions: list[dict]


def analyze_statement(file_path: str, review_question_limit: int = 12) -> PipelineResult:
    detection, _pages = detect_statement(file_path)
    parse_result = parse_with_detected_parser(file_path, detection)
    enriched = process_transactions(parse_result.transactions)
    validation = validate_transactions(enriched, detection)
    analytics = build_analytics(enriched)
    review_questions = generate_review_questions(
        enriched,
        detection,
        validation,
        limit=review_question_limit,
    )

    return PipelineResult(
        detection=detection,
        parse_result=parse_result,
        transactions=enriched,
        validation=validation,
        analytics=analytics,
        review_questions=review_questions,
    )


def result_to_response(filename: str, result: PipelineResult) -> dict:
    detection = result.detection
    validation = result.validation

    return {
        "filename": filename,
        "bank_name": detection.bank_name,
        "template_name": detection.template_name,
        "parser_used": detection.parser_name,
        "is_scanned": detection.is_scanned,
        "status": validation.status,
        "parse_confidence": validation.parse_confidence,
        "quality_metrics": validation.metrics,
        "warnings": validation.warnings,
        "review_required": bool(result.review_questions) or validation.status == "review_required",
        "review_questions": result.review_questions,
        "transaction_count": len(result.transactions),
        "analytics": result.analytics,
        "transactions": [txn.__dict__ for txn in result.transactions],
    }
