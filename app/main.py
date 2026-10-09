import os
import re
from urllib.parse import quote

from dotenv import load_dotenv

# Load .env before importing services: some of them read settings at import time.
load_dotenv()

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel

from app.services.llm_enrichment import classify_transaction, extract_counterparty, semantic_classify_transaction
from app.services.parser import extract_text_from_pdf
from app.services.pipeline import analyze_statement, result_to_response
from app.services.analytics import build_analytics
from app.services.review import apply_review_answers, generate_review_questions
from app.services.validator import validate_transactions
from app.services.report_store import list_reports, load_report, save_report
from app.services.learning import learn_from_review_answers, load_learning_rules
from app.services.pdf_export import build_report_pdf
from app.services.zatca import analyze_zatca_report

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")


class ReviewAnswer(BaseModel):
    question_id: str
    value: str
    field: str | None = None
    transaction_index: int | None = None


class ReviewApplyRequest(BaseModel):
    report_id: str | None = None
    transactions: list[dict]
    answers: list[ReviewAnswer]


def _safe_pdf_filename(filename: str | None, fallback_stem: str) -> str:
    value = (filename or f"{fallback_stem}.pdf").replace("\\", "_").replace("/", "_")
    value = re.sub(r"[\r\n]+", "_", value).strip()
    if not value.lower().endswith(".pdf"):
        value = f"{value}.pdf"
    return value


def _content_disposition_for_download(filename: str) -> str:
    ascii_filename = filename.encode("ascii", "ignore").decode("ascii")
    ascii_filename = re.sub(r'[\r\n"]+', "_", ascii_filename).strip(" ._")
    if not ascii_filename.lower().endswith(".pdf"):
        ascii_filename = "statement.pdf"

    encoded_filename = quote(filename, safe="")
    return f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{encoded_filename}"


@app.get("/")
def root():
    return FileResponse("app/static/index.html")


@app.get("/api")
def api_root():
    return {
        "status": "ok",
        "message": "Bank Statement Analyzer API is running",
        "docs": "http://127.0.0.1:8000/docs",
    }


@app.get("/health/ollama")
def health_ollama():
    return {
        "OLLAMA_ENABLED": os.getenv("OLLAMA_ENABLED"),
        "OLLAMA_MODEL": os.getenv("OLLAMA_MODEL"),
        "OLLAMA_URL": os.getenv("OLLAMA_URL"),
        "OLLAMA_TIMEOUT": os.getenv("OLLAMA_TIMEOUT"),
    }


@app.get("/test/llm")
def test_llm():
    return classify_transaction(
        "OUTGOING TRANSFER TO AL RAJHI BANK BENEFICIARY SAMPLE SUPPLIES TRADING CO",
        100000.00,
    )


@app.get("/test/semantic")
def test_semantic():
    """Test semantic understanding with Arabic text."""
    return semantic_classify_transaction(
        "دفع رواتب | شركة نموذجية للتجارة",
        50000.00,
    )


@app.get("/test/counterparty")
def test_counterparty():
    return extract_counterparty(
        "OUTGOING TRANSFER TO AL RAJHI BANK BENEFICIARY SAMPLE SUPPLIES TRADING CO FOR BUSINESS PAYMENT"
    )


@app.get("/test/full")
def test_full_pipeline(file_path: str):
    result = analyze_statement(file_path)
    return result_to_response(file_path, result)

@app.post("/upload")
async def upload_statement(file: UploadFile = File(...)):
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)

    file_path = uploads_dir / file.filename

    with open(file_path, "wb") as f:
        f.write(await file.read())

    response = analyze_zatca_report(str(file_path), file.filename)
    if response is None:
        result = analyze_statement(str(file_path))
        response = result_to_response(file.filename, result)
    return save_report(response)

@app.post("/debug/text")
async def debug_text(file: UploadFile = File(...)):
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)

    file_path = uploads_dir / file.filename

    with open(file_path, "wb") as f:
        f.write(await file.read())

    pages = extract_text_from_pdf(str(file_path))

    return {
        "filename": file.filename,
        "pages": pages[:3]  # first 3 pages only
    }


@app.post("/review/apply")
def apply_review(request: ReviewApplyRequest):
    submitted_answer_count = len(request.answers)
    answer_dicts = [answer.model_dump() for answer in request.answers]
    learning_errors = []
    try:
        learned_rules = learn_from_review_answers(request.transactions, answer_dicts)
    except Exception as exc:
        learned_rules = []
        learning_errors.append(str(exc))
    transactions, ignored_answers = apply_review_answers(
        request.transactions,
        answer_dicts,
    )
    validation = validate_transactions(transactions)
    review_questions = generate_review_questions(
        transactions,
        detection=None,
        validation=validation,
    )

    response = {
        "transaction_count": len(transactions),
        "submitted_answer_count": submitted_answer_count,
        "applied_answer_count": submitted_answer_count - len(ignored_answers),
        "learned_rule_count": len(learned_rules),
        "learned_rules": learned_rules,
        "learning_errors": learning_errors,
        "ignored_answers": ignored_answers,
        "status": validation.status,
        "parse_confidence": validation.parse_confidence,
        "quality_metrics": validation.metrics,
        "warnings": validation.warnings,
        "review_required": bool(review_questions),
        "remaining_review_question_count": len(review_questions),
        "review_questions": review_questions,
        "analytics": build_analytics(transactions),
        "transactions": [txn.__dict__ for txn in transactions],
    }

    existing = load_report(request.report_id) if request.report_id else None
    if existing:
        response = {
            **existing,
            **response,
            "filename": existing.get("filename"),
            "bank_name": existing.get("bank_name"),
            "template_name": existing.get("template_name"),
            "parser_used": existing.get("parser_used"),
            "is_scanned": existing.get("is_scanned"),
        }

    return save_report(response, request.report_id)


@app.get("/reports")
def get_reports():
    return {"reports": list_reports()}


@app.get("/reports/{report_id}")
def get_report(report_id: str):
    report = load_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@app.get("/reports/{report_id}/pdf")
def download_report_pdf(report_id: str):
    report = load_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    pdf = build_report_pdf(report)
    filename = _safe_pdf_filename(report.get("filename"), report_id)

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": _content_disposition_for_download(filename)},
    )


@app.get("/learning/rules")
def get_learning_rules():
    return {"rules": load_learning_rules()}
