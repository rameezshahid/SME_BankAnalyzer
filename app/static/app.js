const state = {
  result: null,
  file: null,
  filteredTransactions: [],
};

const els = {
  fileInput: document.querySelector("#fileInput"),
  fileName: document.querySelector("#fileName"),
  uploadButton: document.querySelector("#uploadButton"),
  dropZone: document.querySelector("#dropZone"),
  runTitle: document.querySelector("#runTitle"),
  runMessage: document.querySelector("#runMessage"),
  confidenceBar: document.querySelector("#confidenceBar"),
  report: document.querySelector("#report"),
  review: document.querySelector("#review"),
  statusBadge: document.querySelector("#statusBadge"),
  summaryCards: document.querySelector("#summaryCards"),
  analyticsCards: document.querySelector("#analyticsCards"),
  warningsList: document.querySelector("#warningsList"),
  reviewQuestions: document.querySelector("#reviewQuestions"),
  applyReviewButton: document.querySelector("#applyReviewButton"),
  transactionRows: document.querySelector("#transactionRows"),
  transactionSearch: document.querySelector("#transactionSearch"),
  emptyStateTemplate: document.querySelector("#emptyStateTemplate"),
  themeToggle: document.querySelector("#themeToggle"),
  savedReports: document.querySelector("#savedReports"),
  refreshReportsButton: document.querySelector("#refreshReportsButton"),
  downloadCurrentButton: document.querySelector("#downloadCurrentButton"),
};

function applyTheme(theme) {
  const isDark = theme === "dark";
  document.body.classList.toggle("dark", isDark);
  els.themeToggle.textContent = isDark ? "Light mode" : "Dark mode";
  localStorage.setItem("statementAnalyzerTheme", theme);
}

function initTheme() {
  const saved = localStorage.getItem("statementAnalyzerTheme");
  if (saved) {
    applyTheme(saved);
    return;
  }

  const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches;
  applyTheme(prefersDark ? "dark" : "light");
}

function formatMoney(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "Not available";
  }

  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(value));
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "0%";
  }
  return `${Math.round(Number(value) * 100)}%`;
}

function formatDate(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value).slice(0, 10);
  }
  return date.toLocaleDateString("en-GB");
}

function formatDateTime(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return date.toLocaleString();
}

function setStatus(title, message, confidence = 0) {
  els.runTitle.textContent = title;
  els.runMessage.textContent = message;
  els.confidenceBar.style.width = formatPercent(confidence);
}

function showError(error) {
  setStatus("Something needs attention", error.message || "The request failed.", 0);
  els.runTitle.style.color = "#b42318";
}

function resetErrorColor() {
  els.runTitle.style.color = "";
}

function metric(label, value) {
  const item = document.createElement("div");
  item.className = "metric";
  item.innerHTML = `<span></span><strong></strong>`;
  item.querySelector("span").textContent = label;
  item.querySelector("strong").textContent = value;
  return item;
}

function setBadge(status) {
  els.statusBadge.className = "badge";
  els.statusBadge.textContent = status || "unknown";

  if (status === "review_required") {
    els.statusBadge.classList.add("danger");
  } else if (status === "parsed_with_warnings") {
    els.statusBadge.classList.add("warn");
  }
}

function renderSummary(result) {
  const metrics = result.quality_metrics || {};
  if (result.document_type === "zatca_vat_return") {
    els.summaryCards.replaceChildren(
      metric("Document", "ZATCA VAT return"),
      metric("Period", result.analytics?.quarter || "Unknown"),
      metric("From", formatDate(result.analytics?.period_start)),
      metric("To", formatDate(result.analytics?.period_end)),
      metric("Confidence", formatPercent(result.parse_confidence || 0)),
      metric("Parser", result.parser_used || "Unknown")
    );
  } else {
    els.summaryCards.replaceChildren(
      metric("Parser", result.parser_used || "Unknown"),
      metric("Bank", result.bank_name || "Unknown"),
      metric("Transactions", String(result.transaction_count || 0)),
      metric("Confidence", formatPercent(result.parse_confidence || 0)),
      metric("Date coverage", `${metrics.date_coverage_pct || 0}%`),
      metric("Balance coverage", `${metrics.balance_coverage_pct || 0}%`),
      metric("Classified rows", `${metrics.classified_rows_pct || 0}%`),
      metric("Counterparty coverage", `${metrics.counterparty_coverage_pct || 0}%`)
    );
  }

  const warnings = result.warnings || [];
  els.warningsList.replaceChildren();
  warnings.forEach((warning) => {
    const item = document.createElement("div");
    item.className = "warning";
    item.textContent = warning;
    els.warningsList.appendChild(item);
  });
}

function analyticsRows(name, rows) {
  if (!Array.isArray(rows) || rows.length === 0) {
    return metric(name, "None found");
  }

  const item = document.createElement("div");
  item.className = "metric wide-metric";
  const list = document.createElement("ol");
  list.className = "ranked-list";

  rows.slice(0, 6).forEach((row) => {
    const listItem = document.createElement("li");
    const nameEl = document.createElement("span");
    const amountEl = document.createElement("strong");
    nameEl.textContent = row.counterparty_name || "Unknown";
    amountEl.textContent = formatMoney(row.amount);
    listItem.append(nameEl, amountEl);
    list.appendChild(listItem);
  });

  item.innerHTML = `<span></span>`;
  item.querySelector("span").textContent = name;
  item.appendChild(list);
  return item;
}

function monthKey(value) {
  if (!value) {
    return null;
  }
  const text = String(value);
  if (text.length >= 7 && text[4] === "-") {
    return text.slice(0, 7);
  }
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function inferDirection(txn) {
  const amount = Number(txn.amount);
  if (!Number.isNaN(amount) && amount < 0) {
    return "debit";
  }
  if (txn.direction === "credit" || txn.direction === "debit") {
    return txn.direction;
  }
  if (!Number.isNaN(amount) && amount > 0) {
    return "credit";
  }
  return null;
}

function buildMonthwiseFromTransactions(transactions, direction) {
  const totals = {};
  (transactions || []).forEach((txn) => {
    if (inferDirection(txn) !== direction) {
      return;
    }
    const month = monthKey(txn.txn_date);
    const amount = Number(txn.amount);
    if (!month || Number.isNaN(amount)) {
      return;
    }
    totals[month] = (totals[month] || 0) + Math.abs(amount);
  });
  return totals;
}

function hasMonthValues(months) {
  return months && Object.values(months).some((value) => Math.abs(Number(value) || 0) > 0);
}

function monthlyMovementTable(credits, debits, transactions) {
  const creditMonths = hasMonthValues(credits)
    ? credits
    : buildMonthwiseFromTransactions(transactions, "credit");
  const debitMonths = hasMonthValues(debits)
    ? debits
    : buildMonthwiseFromTransactions(transactions, "debit");
  const months = Array.from(new Set([
    ...Object.keys(creditMonths),
    ...Object.keys(debitMonths),
  ])).sort();

  const item = document.createElement("div");
  item.className = "metric wide-metric";
  const label = document.createElement("span");
  label.textContent = "Monthwise credits and debits";
  item.appendChild(label);

  if (!months.length) {
    const empty = document.createElement("strong");
    empty.textContent = "None found";
    item.appendChild(empty);
    return item;
  }

  const tableWrap = document.createElement("div");
  tableWrap.className = "mini-table-wrap";
  const table = document.createElement("table");
  table.className = "mini-table";
  table.innerHTML = `
    <thead>
      <tr>
        <th>Month</th>
        <th>Credits</th>
        <th>Debits</th>
        <th>Net</th>
      </tr>
    </thead>
    <tbody></tbody>
  `;

  const body = table.querySelector("tbody");
  months.forEach((month) => {
    const credit = Number(creditMonths[month] || 0);
    const debit = Number(debitMonths[month] || 0);
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${month}</td>
      <td class="amount-credit">${formatMoney(credit)}</td>
      <td class="amount-debit">${formatMoney(debit)}</td>
      <td>${formatMoney(credit - debit)}</td>
    `;
    body.appendChild(row);
  });

  tableWrap.appendChild(table);
  item.appendChild(tableWrap);
  return item;
}

function renderAnalytics(result) {
  const analytics = result.analytics || {};
  if (result.document_type === "zatca_vat_return") {
    els.analyticsCards.replaceChildren(
      metric("Total sales", formatMoney(analytics.total_sales)),
      metric("Total purchases", formatMoney(analytics.total_purchases)),
      metric("Sales tax", formatMoney(analytics.sales_tax)),
      metric("Purchase tax", formatMoney(analytics.purchase_tax)),
      metric("Net taxes", formatMoney(analytics.net_taxes)),
      metric("Quarter", analytics.quarter || "Unknown")
    );
    return;
  }

  const monthwiseCredits = hasMonthValues(analytics.monthwise_credits)
    ? analytics.monthwise_credits
    : buildMonthwiseFromTransactions(result.transactions, "credit");
  const monthwiseDebits = hasMonthValues(analytics.monthwise_debits)
    ? analytics.monthwise_debits
    : buildMonthwiseFromTransactions(result.transactions, "debit");
  els.analyticsCards.replaceChildren(
    metric("Cash deposits", formatMoney(analytics.total_cash_deposits)),
    metric("Cash withdrawals", formatMoney(analytics.total_cash_withdrawals)),
    metric("Average credit balance", formatMoney(analytics.average_credit_balance)),
    metric("Credit months", String(Object.keys(monthwiseCredits).length)),
    metric("Debit months", String(Object.keys(monthwiseDebits).length)),
    monthlyMovementTable(monthwiseCredits, monthwiseDebits, result.transactions),
    analyticsRows("Major transfers to", analytics.major_transfers_to),
    analyticsRows("Major deposits by", analytics.major_deposits_by)
  );
}

function optionLabel(option) {
  if (option.confidence === null || option.confidence === undefined) {
    return option.label;
  }
  return `${option.label} (${Math.round(option.confidence * 100)}%)`;
}

function renderQuestion(question) {
  const item = document.createElement("div");
  item.className = "question";
  item.dataset.questionId = question.id;
  item.dataset.field = question.field;
  if (question.transaction_index !== null && question.transaction_index !== undefined) {
    item.dataset.transactionIndex = String(question.transaction_index);
  }

  const options = question.options || [];
  const selectOptions = [
    `<option value="">No answer yet</option>`,
    ...options.map((option) => `<option value="${option.value}">${optionLabel(option)}</option>`),
    `<option value="__manual__">Enter a different value</option>`,
  ].join("");

  item.innerHTML = `
    <div>
      <strong></strong>
      <p class="reason"></p>
    </div>
    <label>
      Answer
      <select>${selectOptions}</select>
    </label>
    <label class="manual hidden">
      Manual value
      <input type="text" placeholder="Type the value to apply" />
    </label>
    <div class="context"></div>
  `;

  item.querySelector("strong").textContent = question.question;
  item.querySelector(".reason").textContent = question.reason || "";

  const context = item.querySelector(".context");
  const contextParts = [];
  if (question.context?.date) contextParts.push(`Date: ${formatDate(question.context.date)}`);
  if (question.context?.amount !== undefined) contextParts.push(`Amount: ${formatMoney(question.context.amount)}`);
  if (question.context?.description) contextParts.push(question.context.description);
  if (question.context?.detected_parser) contextParts.push(`Detected parser: ${question.context.detected_parser}`);
  context.textContent = contextParts.join(" | ") || "Statement-level review question";

  const select = item.querySelector("select");
  const manual = item.querySelector(".manual");
  select.addEventListener("change", () => {
    manual.classList.toggle("hidden", select.value !== "__manual__");
  });

  return item;
}

function renderReview(result) {
  const questions = result.review_questions || [];
  els.reviewQuestions.replaceChildren();

  if (questions.length === 0) {
    els.reviewQuestions.appendChild(els.emptyStateTemplate.content.cloneNode(true));
    els.applyReviewButton.disabled = true;
    return;
  }

  questions.forEach((question) => els.reviewQuestions.appendChild(renderQuestion(question)));
  els.applyReviewButton.disabled = false;
}

function transactionMatches(txn, term) {
  if (!term) {
    return true;
  }
  const haystack = [
    txn.description_display,
    txn.description_normalized,
    txn.description_raw,
    txn.category,
    txn.counterparty_name,
    txn.amount,
    txn.balance,
  ].join(" ").toLowerCase();
  return haystack.includes(term.toLowerCase());
}

function renderTransactions(result) {
  const term = els.transactionSearch.value.trim();
  const transactions = (result.transactions || []).filter((txn) => transactionMatches(txn, term));
  state.filteredTransactions = transactions;
  els.transactionRows.replaceChildren();

  transactions.slice(0, 500).forEach((txn) => {
    const row = document.createElement("tr");
    const amountClass = Number(txn.amount) < 0 ? "amount-debit" : "amount-credit";
    row.innerHTML = `
      <td>${formatDate(txn.txn_date)}</td>
      <td></td>
      <td class="${amountClass}">${formatMoney(txn.amount)}</td>
      <td>${formatMoney(txn.balance)}</td>
      <td>${txn.category || "-"}</td>
      <td>${txn.counterparty_name || "-"}</td>
    `;
    row.children[1].textContent = txn.description_display || txn.description_normalized || txn.description_raw || "";
    els.transactionRows.appendChild(row);
  });
}

function render(result) {
  state.result = result;
  els.report.classList.remove("hidden");
  els.review.classList.toggle("hidden", result.document_type === "zatca_vat_return");
  setBadge(result.status);
  renderSummary(result);
  renderAnalytics(result);
  if (result.document_type !== "zatca_vat_return") {
    renderReview(result);
    renderTransactions(result);
  }
  els.downloadCurrentButton.disabled = !result.report_id;
  setStatus(
    result.status === "parsed" ? "Statement parsed" : "Review needed",
    result.document_type === "zatca_vat_return"
      ? `${result.parser_used || "Unknown parser"} parsed ${result.analytics?.quarter || "the VAT period"}.`
      : `${result.parser_used || "Unknown parser"} found ${result.transaction_count || 0} transactions.`,
    result.parse_confidence || 0
  );
}

function renderSavedReports(reports) {
  els.savedReports.replaceChildren();

  if (!reports.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<strong>No saved reports yet.</strong><span>Analyze a statement and it will appear here.</span>";
    els.savedReports.appendChild(empty);
    return;
  }

  reports.forEach((report) => {
    const item = document.createElement("div");
    item.className = "saved-item";
    item.innerHTML = `
      <div>
        <strong></strong>
        <div class="saved-meta">
          <span></span>
          <span></span>
          <span></span>
          <span></span>
        </div>
      </div>
      <div class="saved-actions">
        <button type="button" class="open-report">Open</button>
        <button type="button" class="download-report">PDF</button>
      </div>
    `;

    item.querySelector("strong").textContent = report.filename || "Untitled report";
    const meta = item.querySelectorAll(".saved-meta span");
    meta[0].textContent = report.document_type === "zatca_vat_return" ? "ZATCA" : (report.bank_name || "Unknown bank");
    meta[1].textContent = report.parser_used || "Unknown parser";
    meta[2].textContent = `${report.transaction_count || 0} transactions`;
    meta[3].textContent = `Updated ${formatDateTime(report.updated_at)}`;
    item.querySelector(".open-report").addEventListener("click", () => loadReport(report.report_id));
    item.querySelector(".download-report").addEventListener("click", () => downloadReport(report.report_id));
    els.savedReports.appendChild(item);
  });
}

function downloadReport(reportId) {
  if (!reportId) {
    setStatus("No saved report", "Save or open a report before downloading.", 0);
    return;
  }
  window.open(`/reports/${encodeURIComponent(reportId)}/pdf`, "_blank");
}

async function loadSavedReports() {
  try {
    const response = await fetch("/reports");
    if (!response.ok) {
      throw new Error(`Could not load reports: ${response.status}`);
    }
    const data = await response.json();
    renderSavedReports(data.reports || []);
  } catch (error) {
    const item = document.createElement("div");
    item.className = "warning";
    item.textContent = error.message || "Could not load saved reports.";
    els.savedReports.replaceChildren(item);
  }
}

async function loadReport(reportId) {
  try {
    const response = await fetch(`/reports/${encodeURIComponent(reportId)}`);
    if (!response.ok) {
      throw new Error(`Could not open report: ${response.status}`);
    }
    const report = await response.json();
    render(report);
    setStatus("Saved report opened", `${report.filename || "Report"} is loaded.`, report.parse_confidence || 0);
  } catch (error) {
    showError(error);
  }
}

async function uploadStatement() {
  resetErrorColor();

  if (!state.file) {
    setStatus("Choose a PDF", "Select a statement before analyzing.", 0);
    return;
  }

  const form = new FormData();
  form.append("file", state.file);

  els.uploadButton.disabled = true;
  setStatus("Analyzing", "Parsing the statement and building the report.", 0.2);

  try {
    const response = await fetch("/upload", {
      method: "POST",
      body: form,
    });

    if (!response.ok) {
      throw new Error(`Upload failed with status ${response.status}`);
    }

    const result = await response.json();
    render(result);
    loadSavedReports();
  } catch (error) {
    showError(error);
  } finally {
    els.uploadButton.disabled = false;
  }
}

function collectAnswers() {
  const answers = [];
  els.reviewQuestions.querySelectorAll(".question").forEach((question) => {
    const select = question.querySelector("select");
    const manual = question.querySelector("input");
    let value = select.value;

    if (value === "__manual__") {
      value = manual.value.trim();
    }

    if (!value) {
      return;
    }

    answers.push({
      question_id: question.dataset.questionId,
      field: question.dataset.field || null,
      transaction_index: question.dataset.transactionIndex
        ? Number(question.dataset.transactionIndex)
        : null,
      value,
    });
  });
  return answers;
}

async function applyReview() {
  if (!state.result) {
    return;
  }

  const answers = collectAnswers();
  if (answers.length === 0) {
    setStatus("No answers selected", "Choose at least one review answer to apply.", state.result.parse_confidence || 0);
    return;
  }

  els.applyReviewButton.disabled = true;
  setStatus("Applying review", "Updating the ledger and recalculating analytics.", state.result.parse_confidence || 0);

  try {
    const response = await fetch("/review/apply", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        report_id: state.result.report_id || null,
        transactions: state.result.transactions,
        answers,
      }),
    });

    if (!response.ok) {
      throw new Error(`Review failed with status ${response.status}`);
    }

    const updated = await response.json();
    state.result = {
      ...state.result,
      analytics: updated.analytics,
      transactions: updated.transactions,
      transaction_count: updated.transaction_count,
      status: updated.status || state.result.status,
      parse_confidence: updated.parse_confidence ?? state.result.parse_confidence,
      quality_metrics: updated.quality_metrics || state.result.quality_metrics,
      warnings: updated.warnings || state.result.warnings,
      review_questions: updated.review_questions || [],
      review_required: Boolean(updated.review_required),
      report_id: updated.report_id || state.result.report_id,
      created_at: updated.created_at || state.result.created_at,
      updated_at: updated.updated_at || state.result.updated_at,
    };
    render(state.result);
    loadSavedReports();
    const remaining = updated.remaining_review_question_count || 0;
    setStatus(
      "Review applied",
      `${updated.applied_answer_count || 0} answers applied. ${updated.learned_rule_count || 0} learning rules saved. ${remaining} review questions remain in this batch.`,
      state.result.parse_confidence || 0
    );
  } catch (error) {
    showError(error);
  } finally {
    els.applyReviewButton.disabled = false;
  }
}

function setFile(file) {
  state.file = file;
  els.fileName.textContent = file ? file.name : "Drop a PDF here or select one from your machine.";
}

els.fileInput.addEventListener("change", (event) => {
  setFile(event.target.files[0] || null);
});

els.uploadButton.addEventListener("click", uploadStatement);
els.applyReviewButton.addEventListener("click", applyReview);
els.refreshReportsButton.addEventListener("click", loadSavedReports);
els.downloadCurrentButton.addEventListener("click", () => downloadReport(state.result?.report_id));
els.themeToggle.addEventListener("click", () => {
  applyTheme(document.body.classList.contains("dark") ? "light" : "dark");
});
els.transactionSearch.addEventListener("input", () => {
  if (state.result) {
    renderTransactions(state.result);
  }
});

["dragenter", "dragover"].forEach((eventName) => {
  els.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    els.dropZone.classList.add("dragging");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  els.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    els.dropZone.classList.remove("dragging");
  });
});

els.dropZone.addEventListener("drop", (event) => {
  const file = event.dataTransfer.files[0];
  if (file) {
    setFile(file);
  }
});

initTheme();
setStatus("Ready", "No statement analyzed yet.", 0);
loadSavedReports();
