from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


REPORTS_DIR = Path("reports")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _report_path(report_id: str) -> Path:
    safe_id = "".join(ch for ch in report_id if ch.isalnum() or ch in {"-", "_"})
    return REPORTS_DIR / f"{safe_id}.json"


def save_report(report: dict, report_id: str | None = None) -> dict:
    REPORTS_DIR.mkdir(exist_ok=True)

    now = _now_iso()
    stored = dict(report)
    stored["report_id"] = report_id or stored.get("report_id") or uuid4().hex
    stored.setdefault("created_at", now)
    stored["updated_at"] = now

    path = _report_path(stored["report_id"])
    path.write_text(
        json.dumps(stored, indent=2, ensure_ascii=False, default=_json_default),
        encoding="utf-8",
    )

    return stored


def load_report(report_id: str) -> dict | None:
    path = _report_path(report_id)
    if not path.exists():
        return None

    return json.loads(path.read_text(encoding="utf-8"))


def list_reports() -> list[dict]:
    REPORTS_DIR.mkdir(exist_ok=True)
    summaries = []

    for path in sorted(REPORTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        summaries.append({
            "report_id": report.get("report_id") or path.stem,
            "filename": report.get("filename"),
            "document_type": report.get("document_type"),
            "bank_name": report.get("bank_name"),
            "parser_used": report.get("parser_used"),
            "status": report.get("status"),
            "parse_confidence": report.get("parse_confidence"),
            "transaction_count": report.get("transaction_count"),
            "review_required": report.get("review_required"),
            "created_at": report.get("created_at"),
            "updated_at": report.get("updated_at"),
        })

    return summaries
