import os

from app.services.enrichment import (
    enrich_transaction,
    infer_category_rule_based,
    extract_counterparty_rule_based,
    extract_payment_purpose_rule_based,
    default_counterparty_for_category,
    normalize_counterparty_name,
)
from app.services.learning import apply_learned_rules
from app.services.llm_enrichment import client, semantic_classify_transaction, extract_counterparty
from app.services.text_normalization import normalize_arabic_text, matching_text


def apply_description_display(txn):
    raw = getattr(txn, "description_raw", "") or ""
    normalized = normalize_arabic_text(raw)
    txn.description_normalized = normalized
    txn.description_display = normalized if normalized else raw
    return txn


def should_use_llm_for_categorization() -> bool:
    """Check if LLM should be used for semantic understanding."""
    mode = os.getenv("OLLAMA_ENABLED", "auto").lower()

    if mode in {"0", "false", "no", "off"}:
        return False

    if mode in {"1", "true", "yes", "on"}:
        return client.is_available()

    # Auto mode: use LLM if available
    return client.is_available()


def apply_semantic_classification(txn):
    """Apply semantic understanding using LLM to understand and classify transactions."""
    try:
        # The timeout is handled by the OllamaClient (30 seconds default)
        result = semantic_classify_transaction(
            txn.description_raw,
            abs(float(getattr(txn, "amount", 0) or 0))
        )
        
        if result.get("confidence", 0) >= 0.6:  # Lower threshold for semantic understanding
            txn.category = result.get("transaction_type", "unknown").lower()
            txn.direction = result.get("direction", "debit").lower()
            txn.is_cash_deposit = result.get("is_cash_deposit", False)
            txn.is_cash_withdrawal = result.get("is_cash_withdrawal", False)
            # Store the English translation and meaning for reference
            txn.semantic_translation = result.get("english_translation", "")
            txn.semantic_meaning = result.get("transaction_meaning", "")
            return txn, True  # Successfully classified
    except Exception as e:
        txn.enrichment_error = f"semantic_classification_error: {type(e).__name__}: {str(e)[:100]}"
    
    return txn, False  # Failed to classify semantically


def extract_counterparty_and_purpose(txn, use_llm=True):
    """Extract counterparty name and payment purpose."""
    # First try rule-based extraction
    if not getattr(txn, "counterparty_name", None):
        rule_name = extract_counterparty_rule_based(txn.description_raw)
        if rule_name:
            txn.counterparty_name = normalize_counterparty_name(rule_name)
    
    # Try default counterparty for category (handles fees, salary, pos, etc.)
    if not getattr(txn, "counterparty_name", None) and txn.category:
        default_cp = default_counterparty_for_category(txn.category, txn.description_raw)
        if default_cp:
            txn.counterparty_name = default_cp
    
    # Try payment purpose extraction
    if not getattr(txn, "payment_purpose", None):
        purpose = extract_payment_purpose_rule_based(txn.description_raw)
        if purpose:
            txn.payment_purpose = purpose
    
    # Use LLM for counterparty extraction if still empty and it's a transfer/significant transaction
    text = matching_text(txn.description_raw).upper()
    if (
        not getattr(txn, "counterparty_name", None)
        and txn.category in {"transfer_in", "transfer_out", "internal_transfer", "bill_payment", "loan_repayment"}
        and use_llm
    ):
        try:
            cp = extract_counterparty(txn.description_raw)
            if cp.get("confidence", 0) >= 0.6:  # Lower threshold
                llm_name = normalize_counterparty_name(cp.get("counterparty_name", ""))
                if llm_name and llm_name not in {"UNKNOWN", "REVIEW DESCRIPTION"}:
                    txn.counterparty_name = llm_name
                if cp.get("counterparty_role"):
                    txn.counterparty_role = cp["counterparty_role"]
                if not getattr(txn, "payment_purpose", None) and cp.get("payment_purpose"):
                    txn.payment_purpose = cp["payment_purpose"]
        except Exception as e:
            pass  # Silently fail, counterparty extraction is not critical
    
    # Final normalization
    txn.counterparty_name = normalize_counterparty_name(getattr(txn, "counterparty_name", None))
    
    return txn


def process_transactions(transactions):
    enriched_transactions = []
    llm_calls = 0
    max_llm_calls = int(os.getenv("OLLAMA_MAX_CALLS", "10"))
    
    # Determine if we should use semantic understanding
    use_semantic = should_use_llm_for_categorization()

    for txn in transactions:
        try:
            txn = apply_description_display(txn)
            
            # Always try rule-based first (fast)
            rule_category, rule_direction = infer_category_rule_based(
                txn.description_raw,
                getattr(txn, "amount", None)
            )
            
            if rule_category and rule_category != "unknown":
                # Rule-based detected something
                txn.category = rule_category
                txn.direction = rule_direction
                txn.is_cash_deposit = rule_category == "cash_deposit"
                txn.is_cash_withdrawal = rule_category == "cash_withdrawal"
                txn = apply_learned_rules(txn)
            else:
                # Rule-based didn't detect or got "unknown" - try semantic if available and budget allows
                if use_semantic and llm_calls < max_llm_calls:
                    txn, classified = apply_semantic_classification(txn)
                    if classified:
                        llm_calls += 1
                    else:
                        # Semantic failed, fallback to enrichment
                        txn = enrich_transaction(txn, use_llm=False)
                else:
                    # No semantic budget or not enabled, use enrichment
                    txn = enrich_transaction(txn, use_llm=False)
                
                txn = apply_learned_rules(txn)
            
            # IMPORTANT: Always extract counterparty and purpose (even if category was detected quickly)
            txn = extract_counterparty_and_purpose(txn, use_llm=use_semantic and llm_calls < max_llm_calls)
            if txn.counterparty_name:  # Only count if we actually called LLM
                # Counterparty extraction might have used LLM, but we don't strictly count it in llm_calls
                pass
            
            txn = apply_description_display(txn)
            enriched_transactions.append(txn)
            
        except Exception as e:
            txn.enrichment_error = str(e)
            txn = apply_description_display(txn)
            enriched_transactions.append(txn)

    return enriched_transactions
