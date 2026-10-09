# SME Statement Analyzer

Turn a Saudi bank statement PDF into a clean transaction ledger and a one-page business summary: cash in and out, major counterparties, month-by-month credits and debits, and average balance. It is built for SME credit and financial reviews, where an analyst would otherwise rebuild all of this by hand from Arabic/English PDFs.

The app also reads **ZATCA VAT return** PDFs and pulls out sales, purchases and net VAT for the quarter.

## What it does

1. **Detects the template.** It scores the PDF text against known bank layouts and picks a parser. Scanned (image-only) PDFs are flagged.
2. **Parses transactions.** Each bank has its own parser that rebuilds multi-line rows into `date / description / amount / balance`.
3. **Normalizes Arabic text.** PDF extraction often returns Arabic in reversed presentation forms. These are converted back to readable Arabic before matching.
4. **Classifies each row.** It uses a rule engine (English and Arabic keywords such as `ايداع نقدي`, `رواتب`, `تورق`, SADAD, POS settlements, fees and VAT). When rules aren't enough, it can optionally call a **local LLM through Ollama**, so no data leaves the machine.
5. **Extracts counterparties.** It pulls beneficiary and remitter names from narratives (`/BEN:`, `/REM:`, `/Biller:`, Arabic beneficiary fields) and groups them.
6. **Validates and scores confidence.** It measures date, amount, balance, classification and counterparty coverage, then reports a parse confidence and a status (`parsed`, `parsed_with_warnings` or `review_required`).
7. **Runs a human-review loop.** It asks targeted questions only for rows it couldn't resolve. Each answer is applied to the ledger and **saved as a reusable rule**, so the next statement needs less review.
8. **Reports.** Results go to a web dashboard, a JSON API, and a downloadable PDF report.

### Analytics produced

| Metric | Description |
|---|---|
| Total cash deposits / withdrawals | Sum of rows classified as cash in / cash out |
| Average credit balance | Time-weighted average daily closing balance over the period |
| Major transfers to | Top outgoing counterparties by total amount |
| Major deposits by | Top incoming counterparties by total amount |
| Monthwise credits / debits | Totals per calendar month |

### Supported documents

| Parser | Document |
|---|---|
| `sabb_v1` | SABB / Saudi Awwal Bank account statement |
| `alawwal_icorp_v1` | Alawwal iCorp (Arabic/English) export |
| `alawwal_statement_v1` | Alawwal account statement |
| `bsf_transaction_history_v1` | Banque Saudi Fransi transaction history |
| `snb_business_v1` | Saudi National Bank business statement |
| `generic_text_v1` | Fallback for other text-based statements (lower confidence) |
| `zatca_vat_return_v1` | ZATCA quarterly VAT return |

## Tech stack

Python 3.10+, FastAPI, pdfplumber, ReportLab (PDF reports), vanilla JS/CSS frontend, optional [Ollama](https://ollama.com) for local LLM enrichment.

## Quick start

```bash
git clone https://github.com/rameezshahid/SME_Analyzer.git
cd SME_Analyzer

python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env        # optional; Windows: copy .env.example .env
```

Run the server **from the repository root**, because static files are served from `app/static`:

```bash
python -m uvicorn app.main:app --reload
```

Open:

- **Web app:** http://127.0.0.1:8000
- **Interactive API docs (Swagger):** http://127.0.0.1:8000/docs

## Try it with sample data

The repo does not include real bank statements. Generate a synthetic one (fake names and numbers) instead:

```bash
python scripts/make_sample_statement.py
# -> samples/sample_statement.pdf
```

**In the browser:** open http://127.0.0.1:8000, choose `samples/sample_statement.pdf`, and click **Analyze PDF**. You should see:

- the template detected as **SABB** with a high parse confidence
- 13 transactions in the ledger, classified as transfers, payroll, cash deposits and withdrawals, and fees
- major counterparties such as `DEMO CUSTOMER LLC` (deposits) and `SAMPLE SUPPLIES TRADING CO` (transfers)
- monthly credits and debits for April–June 2025
- a **Download PDF** button for the formatted report

**From the command line:**

```bash
# Analyze a statement (returns the full report as JSON, including report_id)
curl -F "file=@samples/sample_statement.pdf" http://127.0.0.1:8000/upload

# List saved reports
curl http://127.0.0.1:8000/reports

# Download the PDF report
curl -o report.pdf http://127.0.0.1:8000/reports/<report_id>/pdf
```

You can also use your own statement from one of the supported banks. Uploaded files and generated reports stay on your machine, in `uploads/` and `reports/`, and both folders are git-ignored.

## Optional: local LLM enrichment

Rows the rules can't classify can be sent to a local model through Ollama:

```bash
ollama pull qwen3:30b      # or any smaller model, e.g. qwen2.5:14b
```

Set `OLLAMA_ENABLED=true` (or `auto`) and `OLLAMA_MODEL` in `.env`. Check the connection with `GET /health/ollama` and `GET /test/llm`. Without Ollama, the app falls back to rules only and still works end to end.

## Configuration (`.env`)

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_ENABLED` | `auto` | `true` / `false` / `auto` (use it if reachable) |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server |
| `OLLAMA_MODEL` | `qwen3:30b` | Model used for classification |
| `OLLAMA_TIMEOUT` | `30` | Seconds per LLM call |
| `OLLAMA_MAX_CALLS` | `10` | LLM call budget per statement |
| `OWN_ACCOUNT_NAMES` | *(empty)* | Account holder name(s), comma-separated, excluded from counterparty lists |

Truncated beneficiary names can be mapped to full names in `data/counterparty_aliases.json`, for example `{"ACME TRADING INTERNAT": "ACME TRADING INTERNATIONAL"}`. This file is git-ignored.

## API overview

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/upload` | Upload a PDF (bank statement or ZATCA return); returns and saves the report |
| `POST` | `/review/apply` | Submit answers to review questions; updates the report and learns rules |
| `GET` | `/reports` | List saved reports |
| `GET` | `/reports/{id}` | Full report JSON |
| `GET` | `/reports/{id}/pdf` | Download the formatted PDF report |
| `GET` | `/learning/rules` | Current classification rules (seed + learned) |
| `POST` | `/debug/text` | Raw extracted text of the first 3 pages (for building new parsers) |
| `GET` | `/health/ollama` | Show the LLM configuration |

## Project structure

```text
app/
  main.py                     FastAPI routes
  models/transaction.py       Transaction dataclass
  services/
    detector.py               Bank/template detection and scanned-PDF check
    parser.py                 Bank-specific row parsers
    parsers/                  Parser registry (one wrapper per template)
    text_normalization.py     Arabic presentation-form normalization
    enrichment.py             Rule-based classification and counterparty extraction
    llm_enrichment.py         Ollama prompts with JSON-schema outputs
    learning.py               Rules learned from review answers
    review.py                 Review-question generation and answer application
    validator.py              Coverage metrics, confidence and status
    analytics.py              Business metrics
    zatca.py                  ZATCA VAT return extraction
    pdf_export.py             PDF report (ReportLab)
    pipeline.py               detect -> parse -> enrich -> validate -> analyze
  static/                     Web UI
data/learning_rules.seed.json Starter classification rules
scripts/make_sample_statement.py
```

## Limitations

- **No OCR.** Scanned statements are detected and flagged, but their transactions aren't extracted.
- Parsers are built for specific layouts. A bank changing its export format may need a parser update, and other banks go through the lower-confidence generic parser.
- The PDF report uses Arial from `C:/Windows/Fonts` when available. On other systems it falls back to Helvetica, so Arabic text in the report may not render.
- There is no authentication. It is meant to run locally, not as a public service.
