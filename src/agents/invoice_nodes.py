from langchain_core.messages import SystemMessage, HumanMessage
import json
import re
import os

from src.utils.config import get_helper_llm, MAX_TOOL_ITERATIONS, helper_llm_json
from src.api.models import AgentState, invoice
from src.database.db_tools import db_connector
from src.tools.document_tools import scan_documents, search_web
from src.agents.audit_agents import _execute_tool_calls_parallel
from src.agents.local_db_nodes import canonical_desc, clean_llm_json


MAX_AUDIT_SCORE = 100
PASS_RISK_THRESHOLD = 20   # score <= 20 means pass (low risk)

# Severity-weighted penalties used by all verification nodes.
SEVERITY_PENALTIES = {
    "critical": 50,
    "high": 30,
    "medium": 20,
    "low": 10,
}


def apply_severity_penalty(score: int, severity: str) -> int:
    """Add a severity-based penalty while keeping score <= 100."""
    return min(MAX_AUDIT_SCORE, score + SEVERITY_PENALTIES.get(severity, SEVERITY_PENALTIES["low"]))


#invoce Scanning Agent Node
def audit_agent(state: AgentState) -> AgentState:
    """Scans the invoice document and extracts relevant data."""

    print(f"Starting Invoice Scanning Agent with user input: {state['user_input']} \n \n")
    company_name = state.get("company_info", {}).get("company_name", "Unknown")
    system_prompt="""
    json
    You are an Invoice Scanning Agent. Your task is to extract all relevant data from the invoice given by the user, the company you are working for called """ + company_name + """.
    There is 3 senarios for the user request: 
    1. the user give you the invoce Number, in this case you use the db_connector tool with ONLY this exact SQL query (replace INVOICE_NUMBER with the actual invoice number): SELECT i.*, il.*, c.name as supplier_name, c.tax_number, c.email, c.phone, c.address FROM invoices i JOIN invoice_lines il ON i.id = il.invoice_id LEFT JOIN contacts c ON i.supplier_id = c.id WHERE i.invoice_number = 'INVOICE_NUMBER'. Then organize the returned data into the required JSON format.
    2. the user give you the file path of the invoice, in this case you use the scan_documents tool to scan the invoice and extract the data. IMPORTANT: pass the COMPLETE file path exactly as provided by the user (including all directories, e.g. 'email_attachments/sender@example.com/invoice.pdf' or '/home/user/uploads/invoice.pdf'). Never strip the path down to just the filename.
    3. the user give you some information about the invoice but not the file path or the invoice number, ask the user for the invoice number or file path.
    \n\n
    After you extract the invoice data, your output will have two formats base on the seccess of the extraction: 
    1. if the extraction is successful, The output will be a JSON string with the EXACT following format (the output must be strictly valid JSON with double quotes): 
    [{"invoice_number": "Number of the invoice", "state": "waiting", "note": "if you have any notes put them here or anything you want", "invoice_data": {"type": "in_invoice|out_invoice|in_refund|out_refund|external", "supplier_name": "Name of the supplier", "amount": "Amount of the invoice", "customer_name": "Name of the customer", "VAT": "VAT amount", "address": "Address of the supplier", "creation_date": "Creation date of the invoice", "product_name": ["Name of product 1", "Name of product 2"], "price": ["Price of product 1", "Price of product 2"], "quantity": ["Quantity 1", "Quantity 2"], "currency": "Currency of the invoice", "category": ["Category 1", "Category 2"], "VAT_class": ["VAT class 1", "VAT class 2"], "total": "Total amount" } } ]
    2. if the extraction fails, you output an error message exactly in this format: 
    {"error": "Error message"}"""
    # scanner_llm = get_helper_llm().bind_tools([db_connector, scan_documents])
    scanner_llm = helper_llm_json.bind_tools([db_connector, scan_documents])
    msgs = [SystemMessage(content=system_prompt)] + [state["user_input"]]
    for _iteration in range(MAX_TOOL_ITERATIONS):
        response = scanner_llm.invoke(msgs)
        print(f"Invoice Scanning Agent intermediate response: {response.content} \n \n")
        msgs.append(response)
        if not response.tool_calls:
            break
        tool_results = _execute_tool_calls_parallel(response.tool_calls, {"db_connector": db_connector, "scan_documents": scan_documents})
        msgs.extend(tool_results)
    else:
        print("WARNING: Invoice Scanning Agent reached maximum tool iterations.")
    print(f"\n \n Invoice Scanning Agent Response: {response.content} \n \n ")
    json_match = re.search(r'\[.*\]', response.content, re.DOTALL)
    try:
        list_json = json.loads(json_match.group()) if json_match else []
    except json.JSONDecodeError:
        import ast
        try:
            fixed_str = json_match.group().replace('null', 'None').replace('true', 'True').replace('false', 'False')
            list_json = ast.literal_eval(fixed_str) if json_match else []
        except Exception:
            list_json = []
    print(f"Parsed JSON from Invoice Scanning Agent: {len(list_json)} invoices found.")
    for json_response in list_json:
        if "error" in json_response:
            print(f"Invoice scanning failed with error: {json_response['error']}")
            state["invoces"].append(invoice("unknown", json_response["error"], {}, "error"))
        else:
            state['invoces'].append(invoice(json_response["invoice_number"], json_response["note"], json_response["invoice_data"], "waiting"))
            existing_raw = db_connector.invoke({
                "query": f"SELECT id FROM invoices WHERE invoice_number = '{json_response['invoice_number']}' LIMIT 1;",
                "type": "read",
                "source": "local_db"
            })
            existing = json.loads(existing_raw) if isinstance(existing_raw, str) else existing_raw
            if not existing:
                inv_num = json_response.get("invoice_number", "").replace("'", "''")
                sup_name = json_response["invoice_data"].get("supplier_name", "").replace("'", "''")
                cust_name = json_response["invoice_data"].get("customer_name", "").replace("'", "''")
                inv_type = json_response["invoice_data"].get("type", "external").replace("'", "''")
                inv_curr = json_response["invoice_data"].get("currency", "USD").replace("'", "''")
                due_date = str(json_response["invoice_data"].get("due_date", "")).replace("'", "''")
                db_connector.invoke({
                    "query": f""" INSERT INTO invoices (supplier_id, supplier_name, customer_id, customer_name, invoice_number, type, currency, exchange_rate, due_date, total_untaxed, total_tax, total_amount, status) VALUES ((SELECT id FROM contacts WHERE name = '{sup_name}' AND type = 'supplier' LIMIT 1), '{sup_name}', (SELECT id FROM contacts WHERE name = '{cust_name}' AND type = 'customer' LIMIT 1), '{cust_name}', '{inv_num}', '{inv_type}', '{inv_curr}', 1, '{due_date}', {json_response["invoice_data"].get("amount", 0)}, {json_response["invoice_data"].get("VAT", 0)}, {json_response["invoice_data"].get("total", 0)}, 'draft'); """,
                    "type": "write",
                    "source": "local_db"
                })
            # Check if an audit log entry already exists for this invoice with the same details to avoid duplicates
            # existing_audit_raw = db_connector.invoke({
            #     "query": f"SELECT id FROM audit_logs WHERE entity_type = 'invoice' AND entity_id = (SELECT id FROM invoices WHERE invoice_number = '{json_response['invoice_number']}') AND action = 'audit' AND details = '{json_response['note']}' AND datetime(created_at) > datetime('now', '-1 minute') LIMIT 1;",
            #     "type": "read",
            #     "source": "local_db"
            # })
            db_connector.invoke({
                    "query": f""" INSERT INTO audit_logs (entity_type, entity_id,action, details, created_at) VALUES ('invoice', (SELECT id FROM invoices WHERE invoice_number = '{json_response.get("invoice_number", "").replace("'", "''")}'), 'audit', '{json_response.get("note", "").replace("'", "''")}', datetime('now')); """,
                    "type": "write",
                    "source": "local_db"
                })
    print("END of Invoice Scanning Agent processing.\n \n")
    return state




# ──────────────────────────────────────────────────────────────
# Supplier Verification – helper utilities (pure functions, no
# side effects, no changes to the system structure)
# ──────────────────────────────────────────────────────────────

# Words that, on their own, make a supplier name suspiciously generic.
_GENERIC_TOKENS = {
    "consulting", "services", "trading", "company", "enterprise",
    "solutions", "group", "agency", "international", "global",
    "corp", "corporation", "inc", "llc", "ltd", "co",
}


def _normalize_address(addr: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation for fuzzy comparison."""
    addr = addr.lower().strip()
    addr = re.sub(r"[^\w\s]", "", addr)   # drop punctuation
    addr = re.sub(r"\s+", " ", addr)      # collapse spaces
    return addr


def _fuzzy_address_match(a: str, b: str) -> str:
    """
    Compare two addresses after normalisation.

    Returns:
        'exact'     – normalised forms are identical
        'partial'   – one is a substring of the other (minor formatting diff)
        'mismatch'  – meaningful difference
    """
    na, nb = _normalize_address(a), _normalize_address(b)
    if na == nb:
        return "exact"
    if na in nb or nb in na:
        return "partial"
    # Token-overlap heuristic: if ≥60 % of tokens overlap it's still close
    ta, tb = set(na.split()), set(nb.split())
    if ta and tb:
        overlap = len(ta & tb) / max(len(ta), len(tb))
        if overlap >= 0.6:
            return "partial"
    return "mismatch"


def _is_generic_name(name: str) -> bool:
    """True when the supplier name consists *entirely* of generic business words."""
    tokens = set(re.sub(r"[^\w\s]", "", name).lower().split())
    return bool(tokens) and tokens.issubset(_GENERIC_TOKENS)


# ──────────────────────────────────────────────────────────────
# Supplier Verification Node
# ──────────────────────────────────────────────────────────────

def supplier_verification_node(state: AgentState) -> AgentState:
    """
    Verify supplier authenticity using the local supplier database.

    Deep-audit checks performed:
      1. Identity consistency   – exact then fuzzy name match
      2. Structural completeness – missing profile fields
      3. Address consistency    – fuzzy comparison
      4. Duplicate detection    – multiple similar suppliers
      5. Generic-name risk      – suspiciously vague names
      6. Single-use supplier    – used in only one invoice
    """
    for i, invoice in enumerate(state["invoces"]):
        invoice.audits_results["supplier_authenticity"] = {
            "status": "not_verified",
            "score": MAX_AUDIT_SCORE,
            "discrepancies": [],
        }

        invoice.status = "verifying_supplier"

        best_score  = MAX_AUDIT_SCORE + 1
        best_result = None

        supplier_name    = (invoice.invoice_data.get("supplier_name") or "").strip()
        supplier_address = (invoice.invoice_data.get("address") or "").strip()

        # ── 0. Missing supplier name ──────────────────────────
        if not supplier_name:
            invoice.audits_results["supplier_authenticity"] = {
                "status": "missing_supplier_name",
                "score": MAX_AUDIT_SCORE,
                "discrepancies": ["missing_supplier_name"],
            }
            invoice.state = "VERIFIED_WITH_ISSUES"
            state["invoces"][i] = invoice
            print("Supplier verification failed: Missing supplier name.")
            continue

        safe_name = supplier_name.replace("'", "''")

        # ── 1a. Exact name lookup (full profile) ─────────────
        exact_query = f"""
            SELECT id, name, tax_number, email, phone, address
            FROM contacts
            WHERE name = '{safe_name}'
            UNION 
            SELECT id, name, tax_id as tax_number, email, phone, address FROM companies WHERE name = '{safe_name}';
        """
        exact_query
        try:
            results_raw = db_connector.invoke({
                "query": exact_query,
                "type": "read",
                "source": "local_db",
            })
            results = json.loads(results_raw) if isinstance(results_raw, str) else results_raw
            print(f"Exact search : {results} \n \n")
        except Exception as e:
            print(f"DB ERROR during supplier verification: {e}")
            invoice.audits_results["supplier_authenticity"] = {
                "status": "db_error",
                "score": MAX_AUDIT_SCORE,
                "discrepancies": ["db_error"],
            }
            invoice.state = "VERIFIED_WITH_ISSUES"
            state["invoces"][i] = invoice
            continue

        name_match_type = "exact"   # track how we matched

        # ── 1b. Fuzzy fallback (LIKE search) ──────────────────
        if not results:
            # Pick the longest significant token for a LIKE search
            tokens = [t for t in supplier_name.split() if t.lower() not in _GENERIC_TOKENS and len(t) > 2]
            keyword = max(tokens, key=len) if tokens else supplier_name
            safe_keyword = keyword.replace("'", "''")

            fuzzy_query = f"""
                SELECT id, name, tax_number, email, phone, address
                FROM contacts
                WHERE name LIKE '%{safe_keyword}%'
                UNION 
                SELECT id, name, tax_id as tax_number, email, phone, address FROM companies WHERE name LIKE '%{safe_keyword}%';
            """
            try:
                results_raw = db_connector.invoke({
                    "query": fuzzy_query,
                    "type": "read",
                    "source": "local_db",
                })
                results = json.loads(results_raw) if isinstance(results_raw, str) else results_raw
                print(f"Fuzzy search : {results} \n \n")
            except Exception:
                results = []

            if results:
                name_match_type = "partial"

        # ── Supplier still not found after fuzzy search ───────
        if not results:
            score = apply_severity_penalty(0, "critical")
            disc  = [f"supplier_not_found: no contact matching '{supplier_name}'"]

            # Still flag generic-name risk even when not found
            if _is_generic_name(supplier_name):
                score = apply_severity_penalty(score, "low")
                disc.append(f"supplier name is suspiciously generic: '{supplier_name}'")

            invoice.audits_results["supplier_authenticity"] = {
                "status": "supplier_not_found",
                "score": score,
                "discrepancies": disc,
            }
            invoice.state = "VERIFIED_WITH_ISSUES"
            state["invoces"][i] = invoice
            print(f"Supplier verification result: {invoice.audits_results['supplier_authenticity']}")
            continue

        # ── 4. Duplicate / similar supplier detection ─────────
        if len(results) > 1:
            dup_names = [r.get("name", "?") for r in results]
            # This is a signal, not blocking – noted on every candidate below
            dup_warning = f"multiple similar suppliers found ({len(results)} matches: {', '.join(dup_names)})"
        else:
            dup_warning = None

        # ── Evaluate every candidate, keep the best ───────────
        for supplier_record in results:
            if not isinstance(supplier_record, dict):
                continue
            
            score = 0
            discrepancies = []

            db_name    = (supplier_record.get("name") or "").strip()
            db_address = (supplier_record.get("address") or "").strip()

            # ── 1c. Name-match penalty ────────────────────────
            if name_match_type == "partial":
                if db_name.lower() == supplier_name.lower():
                    # case-only difference – no penalty
                    pass
                else:
                    score = apply_severity_penalty(score, "medium")
                    discrepancies.append(
                        f"partial name match: invoice='{supplier_name}' vs db='{db_name}'"
                    )

            # ── 2. Structural completeness ────────────────────
            profile_fields = {
                "tax_number": supplier_record.get("tax_number"),
                "email":      supplier_record.get("email"),
                "phone":      supplier_record.get("phone"),
                "address":    supplier_record.get("address"),
            }
            if not profile_fields["tax_number"]:
                profile_fields["tax_number"] = supplier_record.get("tax_id")  # fallback for companies table
            missing = [k for k, v in profile_fields.items() if not v]
            if len(missing) >= 3:
                score = apply_severity_penalty(score, "high")
                discrepancies.append(
                    f"supplier record incomplete: missing {', '.join(missing)}"
                )
            elif len(missing) >= 2:
                score = apply_severity_penalty(score, "medium")
                discrepancies.append(
                    f"supplier record partially incomplete: missing {', '.join(missing)}"
                )

            # ── 3. Fuzzy address comparison ───────────────────
            if supplier_address and db_address:
                addr_result = _fuzzy_address_match(supplier_address, db_address)
                if addr_result == "mismatch":
                    score = apply_severity_penalty(score, "medium")
                    discrepancies.append(
                        f"address mismatch: invoice='{supplier_address}' vs db='{db_address}'"
                    )
                elif addr_result == "partial":
                    score = apply_severity_penalty(score, "low")
                    discrepancies.append(
                        f"minor address difference: invoice='{supplier_address}' vs db='{db_address}'"
                    )
                # 'exact' → no penalty
            elif supplier_address and not db_address:
                # DB has no address to compare – structural gap
                if "address" not in missing:       # avoid duplicate message
                    discrepancies.append("supplier address missing in DB, cannot compare")

            # ── 4b. Attach duplicate warning (if any) ─────────
            if dup_warning:
                score = apply_severity_penalty(score, "low")
                discrepancies.append(dup_warning)

            # ── 5. Generic-name risk ──────────────────────────
            if _is_generic_name(supplier_name):
                score = apply_severity_penalty(score, "low")
                discrepancies.append(
                    f"supplier name is suspiciously generic: '{supplier_name}'"
                )

            # ── 6. Single-use supplier detection ──────────────
            supplier_id = supplier_record.get("id")
            if supplier_id is not None:
                try:
                    usage_raw = db_connector.invoke({
                        "query": f"SELECT COUNT(*) as cnt FROM invoices WHERE supplier_id = {supplier_id};",
                        "type": "read",
                        "source": "local_db",
                    })
                    usage = json.loads(usage_raw) if isinstance(usage_raw, str) else usage_raw
                    if isinstance(usage, list) and usage:
                        cnt = usage[0].get("cnt", 0)
                        if cnt <= 1:
                            score = apply_severity_penalty(score, "low")
                            discrepancies.append(
                                f"supplier used in only {cnt} invoice(s) — limited transaction history"
                            )
                except Exception:
                    pass   # non-blocking; skip if query fails
            
            # ── 7. Tax Format Verification ──────────────
            import re
            def _validate_tunisian_tax_number(tax_num: str) -> bool:
                return bool(re.match(r'^\d{7}[A-Z]{3}\d{3}$', tax_num.strip()))
            tax_num = profile_fields.get("tax_number", "")
            if tax_num and not _validate_tunisian_tax_number(tax_num):
                score = apply_severity_penalty(score, "medium")
                discrepancies.append(
                    f"tax number format invalid: '{tax_num}' (expected Tunisian format)"
                )


            # ── Keep the best candidate ───────────────────────
            if score < best_score:
                best_score  = score
                best_result = {
                    "status": "verified",
                    "score": score,
                    "supplier_id": supplier_id,
                    "match_type": name_match_type,
                    "discrepancies": discrepancies or ["none"],
                }

        if best_result is None:
            invoice.audits_results["supplier_authenticity"] = {
                "status": "processing_error_or_invalid_data",
                "score": MAX_AUDIT_SCORE,
                "discrepancies": ["supplier data invalid or unparseable"],
            }
            invoice.state = "VERIFIED_WITH_ISSUES"
        else:
            invoice.audits_results["supplier_authenticity"] = best_result
            invoice.state = "VERIFIED" if best_score <= PASS_RISK_THRESHOLD else "VERIFIED_WITH_ISSUES"
        
        print(f"Supplier verification result: {invoice.audits_results['supplier_authenticity']}")
        state["invoces"][i] = invoice

    # ── Persist audit results to DB ───────────────────────────
    for invoice in state["invoces"]:
        safe_discrepancies = json.dumps(
            invoice.audits_results["supplier_authenticity"]["discrepancies"]
        ).replace("'", "''")
        db_connector.invoke({
            "query": f""" INSERT INTO audit_results (entity_type, entity_id, rule_name, risk_level, issue_detected, created_at) VALUES ('invoice', (SELECT id FROM invoices WHERE invoice_number = '{invoice.invoice_number}'), 'supplier_authenticity', '{invoice.audits_results["supplier_authenticity"]["score"]}', '{safe_discrepancies}', datetime('now')) """,
            "type": "write",
            "source": "local_db",
        })
    return state


def purchase_order_verification_node(state: AgentState) -> AgentState:
    """
    Verify purchase order consistency against each invoice.

    Deep-audit checks performed:
      1. Temporal logic        – PO must exist before invoice; flag unrealistic gaps
      2. Status validation     – only 'purchase' (confirmed) is fully trusted
      3. Financial consistency – classify amount gaps as rounding vs real mismatch
      4. Quantity logic        – minor vs suspicious deviations
      5. Price logic           – rounding issue vs real discrepancy
      6. Tax consistency       – VAT mismatch considering rounding
      7. Multi-record reasoning – pick the MOST consistent PO, not just first
    """
    from datetime import datetime as _dt

    for i, invoice in enumerate(state["invoces"]):
        invoice.status = "verifying_purchase_order"

        best_score  = -999
        best_result = None

        raw_products = invoice.invoice_data.get("product_name", [])
        if isinstance(raw_products, str):
            products_names = [raw_products]
        else:
            products_names = raw_products

        raw_qty = invoice.invoice_data.get("quantity", [])
        if isinstance(raw_qty, (str, int, float)):
            raw_qty = [raw_qty]
            
        raw_price = invoice.invoice_data.get("price", [])
        if isinstance(raw_price, (str, int, float)):
            raw_price = [raw_price]

        creation_date = invoice.invoice_data.get("creation_date")

        safe_suplier_name = (invoice.invoice_data.get("supplier_name") or "").replace("'", "''")

        final_results = {
            "status": "verified",
            "purchase_order_id": None,
            "order_number": None,
            "score": MAX_AUDIT_SCORE,
            "discrepancies": [],
        }
        
        has_run = False

        for prod_idx, product_name in enumerate(products_names):
            has_run = True
            safe_product_name = str(product_name).replace("'", "''")
            
            try:
                result = db_connector.invoke({
                    "query": f"""
                    SELECT
                        po.id,
                        po.order_number,
                        po.order_date,
                        po.due_date,
                        po.status,
                        po.total_amount,
                        pol.product_id,
                        pol.quantity,
                        pol.unit_price,
                        pol.subtotal
                    FROM purchase_orders po
                    JOIN purchase_order_lines pol ON po.id = pol.purchase_order_id
                    WHERE pol.product_id = (
                        SELECT id FROM products WHERE name = '{safe_product_name}'
                    )
                    AND po.contact_id = (SELECT id FROM contacts WHERE name = '{safe_suplier_name}' LIMIT 1);
                    """,
                    "type": "read",
                    "source": "local_db",
                })
            except Exception as e:
                invoice.audits_results["purchase_order_verification"] = {
                    "status": "db_error",
                    "error": str(e),
                    "score": MAX_AUDIT_SCORE,
                    "discrepancies": ["db_error"],
                }
                final_results = invoice.audits_results["purchase_order_verification"]
                print(f"Purchase order verification failed with DB error: {e}")
                continue

            results = json.loads(result) if isinstance(result, str) else result

            if isinstance(results, dict):
                invoice.audits_results["purchase_order_verification"] = {
                    "status": "db_error",
                    "error": results.get("error", str(results)),
                    "score": MAX_AUDIT_SCORE,
                    "discrepancies": ["db_error"],
                }
                final_results = invoice.audits_results["purchase_order_verification"]
                print(f"Purchase order verification failed with DB error: {results}")
                continue

            if not results:
                score_penalty = apply_severity_penalty(0, "critical")
                discrepancy_msg = f"no purchase order found for product '{safe_product_name}'"
                final_results["score"] += score_penalty
                final_results["discrepancies"].append(discrepancy_msg)
                
                # Make sure we have a valid entry early on if none is found
                if not invoice.audits_results.get("purchase_order_verification"):
                    invoice.audits_results["purchase_order_verification"] = {
                        "status": "purchase_order_not_found",
                        "score": score_penalty,
                        "discrepancies": [discrepancy_msg],
                    }
                print(f"Purchase order verification failed: {discrepancy_msg}")
                continue

            # ── Helper: safe float conversion ─────────────────────
            def _safe_float(val, default=None):
                try:
                    return float(val) if val is not None else default
                except (ValueError, TypeError):
                    return default

            # ── Helper: safe date parse ───────────────────────────
            def _parse_date(d):
                if not d:
                    return None
                for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y", "%m/%d/%Y"):
                    try:
                        from datetime import datetime as _dt
                        return _dt.strptime(str(d).strip()[:10], fmt)
                    except ValueError:
                        continue
                return None

            invoice_date = _parse_date(creation_date)
            inv_total    = _safe_float(invoice.invoice_data.get("total"))
            
            qty_val = raw_qty[prod_idx] if prod_idx < len(raw_qty) else None
            price_val = raw_price[prod_idx] if prod_idx < len(raw_price) else None
            inv_qty      = _safe_float(qty_val)
            inv_price    = _safe_float(price_val)
            inv_vat      = _safe_float(invoice.invoice_data.get("VAT"))

            best_prod_score = MAX_AUDIT_SCORE + 1
            best_prod_result = None

            # ── Evaluate every PO candidate ───────────────────────
            for po in results:
                if not isinstance(po, dict):
                    continue
                
                score = 0
                discrepancies = []

                po_order_date = _parse_date(po.get("order_date"))
                po_due_date   = _parse_date(po.get("due_date"))
                po_status     = (po.get("status") or "").strip().lower()
                po_total      = _safe_float(po.get("total_amount"))
                po_qty        = _safe_float(po.get("quantity"))
                po_price      = _safe_float(po.get("unit_price"))
                po_tax_amt    = _safe_float(po.get("tax_amount"), 0)

                # ── 1. Temporal logic ─────────────────────────────
                if invoice_date and po_order_date:
                    if po_order_date > invoice_date:
                        score = apply_severity_penalty(score, "critical")
                        discrepancies.append(
                            f"PO issued AFTER invoice: po_date='{po.get('order_date')}' vs invoice_date='{creation_date}'"
                        )
                    else:
                        delta_days = (invoice_date - po_order_date).days
                        if delta_days == 0:
                            score = apply_severity_penalty(score, "low")
                            discrepancies.append(
                                "PO and invoice on same day — suspiciously close timing"
                            )
                        elif delta_days > 365:
                            score = apply_severity_penalty(score, "low")
                            discrepancies.append(
                                f"PO is {delta_days} days before invoice — unusually old PO"
                            )

                if invoice_date and po_due_date:
                    if invoice_date > po_due_date:
                        score = apply_severity_penalty(score, "medium")
                        discrepancies.append(
                            f"invoice issued after PO due_date: invoice='{creation_date}' vs po_due='{po.get('due_date')}'"
                        )

                # ── 2. Status validation ──────────────────────────
                if po_status == "purchase":
                    pass  # fully trusted
                elif po_status in ("draft", "sent", "pending"):
                    score = apply_severity_penalty(score, "high")
                    discrepancies.append(
                        f"invoice issued without confirmed PO (status='{po_status}')"
                    )
                elif po_status in ("cancel", "cancelled", "rejected"):
                    score = apply_severity_penalty(score, "critical")
                    discrepancies.append(
                        f"PO is cancelled/rejected but invoice exists (status='{po_status}')"
                    )
                elif po_status:
                    score = apply_severity_penalty(score, "medium")
                    discrepancies.append(
                        f"unusual PO status: '{po_status}'"
                    )
                else:
                    score = apply_severity_penalty(score, "medium")
                    discrepancies.append("PO status is missing")

                # ── 3. Financial consistency ──────────────────────
                if po_total is not None and inv_total is not None:
                    diff = abs(po_total - inv_total)
                    if diff > 0.01:
                        # Classify: rounding (<1 %) vs real mismatch
                        pct = (diff / max(abs(po_total), abs(inv_total), 1)) * 100
                        if pct <= 1:
                            score = apply_severity_penalty(score, "low")
                            discrepancies.append(
                                f"minor amount difference ({pct:.2f}%): po={po_total} vs invoice={inv_total}"
                            )
                        elif pct <= 5:
                            score = apply_severity_penalty(score, "medium")
                            discrepancies.append(
                                f"financial mismatch ({pct:.2f}%): po={po_total} vs invoice={inv_total}"
                            )
                        else:
                            score = apply_severity_penalty(score, "high")
                            discrepancies.append(
                                f"financial mismatch beyond tolerance ({pct:.2f}%): po={po_total} vs invoice={inv_total}"
                            )

                # ── 4. Quantity logic ──────────────────────────────
                if po_qty is not None and inv_qty is not None:
                    qty_diff = abs(po_qty - inv_qty)
                    if qty_diff > 0.001:
                        qty_pct = (qty_diff / max(abs(po_qty), abs(inv_qty), 1)) * 100
                        if qty_pct <= 2:
                            score = apply_severity_penalty(score, "low")
                            discrepancies.append(
                                f"minor quantity difference ({qty_pct:.2f}%): po={po_qty} vs invoice={inv_qty}"
                            )
                        elif qty_pct <= 10:
                            score = apply_severity_penalty(score, "medium")
                            discrepancies.append(
                                f"quantity deviation ({qty_pct:.2f}%): po={po_qty} vs invoice={inv_qty}"
                            )
                        else:
                            score = apply_severity_penalty(score, "high")
                            discrepancies.append(
                                f"quantity deviation not explainable ({qty_pct:.2f}%): po={po_qty} vs invoice={inv_qty}"
                            )

                # ── 5. Price logic ────────────────────────────────
                if po_price is not None and inv_price is not None:
                    price_diff = abs(po_price - inv_price)
                    if price_diff > 0.01:
                        price_pct = (price_diff / max(abs(po_price), abs(inv_price), 1)) * 100
                        if price_pct <= 1:
                            score = apply_severity_penalty(score, "low")
                            discrepancies.append(
                                f"unit price rounding difference ({price_pct:.2f}%): po={po_price} vs invoice={inv_price}"
                            )
                        else:
                            score = apply_severity_penalty(score, "medium")
                            discrepancies.append(
                                f"unit price discrepancy ({price_pct:.2f}%): po={po_price} vs invoice={inv_price}"
                            )

                # ── 6. Tax consistency ────────────────────────────
                if inv_vat is not None and po_tax_amt is not None:
                    tax_diff = abs(po_tax_amt - inv_vat)
                    if tax_diff > 0.50:      # generous tolerance for rounding
                        tax_pct = (tax_diff / max(abs(inv_vat), abs(po_tax_amt), 1)) * 100
                        if tax_pct <= 2:
                            score = apply_severity_penalty(score, "low")
                            discrepancies.append(
                                f"minor VAT rounding difference ({tax_pct:.2f}%): po_tax={po_tax_amt} vs invoice_VAT={inv_vat}"
                            )
                        else:
                            score = apply_severity_penalty(score, "medium")
                            discrepancies.append(
                                f"tax calculation inconsistent with PO ({tax_pct:.2f}%): po_tax={po_tax_amt} vs invoice_VAT={inv_vat}"
                            )

                # ── 7. Keep the MOST consistent candidate ─────────
                if score < best_prod_score:
                    best_prod_score = score
                    best_prod_result = {
                        "status": "verified",
                        "purchase_order_id": po.get("id"),
                        "order_number": po.get("order_number"),
                        "score": score,
                        "discrepancies": discrepancies or ["none"],
                    }
                    
            if best_prod_result:
                final_results["score"] += best_prod_result["score"]
                # Only track the real discrepancies, filter out "none" 
                real_disc = [d for d in best_prod_result["discrepancies"] if d != "none"]
                final_results["discrepancies"].extend(real_disc)

        # ── Final result for this invoice ─────────────────────
        if not has_run:
            final_results = {
                "status": "no_products",
                "score": MAX_AUDIT_SCORE,
                "discrepancies": ["No products found in invoice to verify purchase order against."]
            }
        elif final_results.get("status") == "verified":
             # Normalize score based on number of products
            prod_count = len(products_names) if len(products_names) > 0 else 1
            final_results["score"] = min(100, final_results["score"])
            if not final_results["discrepancies"]:
                final_results["discrepancies"] = ["none"]

        # Only overwrite if we don't already have an overriding db error result
        current_res = invoice.audits_results.get("purchase_order_verification")
        if not current_res or current_res.get("status") not in ("db_error", "purchase_order_not_found"):
            invoice.audits_results["purchase_order_verification"] = final_results

        final_score = invoice.audits_results["purchase_order_verification"].get("score", 0)
        invoice.state = "VERIFIED" if final_score <= PASS_RISK_THRESHOLD else "VERIFIED_WITH_ISSUES"
        print(f"purchase order verification result: {invoice.audits_results['purchase_order_verification']}")
        state["invoces"][i] = invoice

    # ── Persist audit results to DB ───────────────────────────
    for invoice in state["invoces"]:
        po_res = invoice.audits_results.get("purchase_order_verification")
        if po_res is None:
            po_res = {
                "status": "processing_error_or_invalid_data",
                "score": MAX_AUDIT_SCORE,
                "discrepancies": ["purchase order data was invalid or not processed"],
            }
            invoice.audits_results["purchase_order_verification"] = po_res

        safe_discrepancies = json.dumps(
            po_res.get("discrepancies", [])
        ).replace("'", "''")
        db_connector.invoke({
            "query": f""" INSERT INTO audit_results (entity_type, entity_id, rule_name, risk_level, issue_detected, created_at) VALUES ('invoice', (SELECT id FROM invoices WHERE invoice_number = '{invoice.invoice_number}'), 'purchase_order_verification', '{po_res.get("score", 0)}', '{safe_discrepancies}', datetime('now')) """,
            "type": "write",
            "source": "local_db",
        })
    return state


def inventory_order_verification_node(state: AgentState) -> AgentState:
    """
    Verify inventory consistency against the invoice.

    Deep-audit checks performed:
      1. Stock flow logic       – sales→decrease, purchases→increase
      2. Temporal consistency   – logs must align with invoice date
      3. Quantity realism       – graded by % deviation
      4. Direction validation   – invoice type → expected change_type
      5. Inventory sufficiency  – selling more than on-hand is critical
      6. Behavioral anomalies   – sudden large stock changes
      7. Source consistency     – weak signal, low severity
    """
    from datetime import datetime as _dt

    def _parse_date(d):
        if not d:
            return None
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return _dt.strptime(str(d).strip()[:10], fmt)
            except ValueError:
                continue
        return None

    def _safe_float(val, default=None):
        try:
            return float(val) if val is not None else default
        except (ValueError, TypeError):
            return default

    # Expected change_type per invoice type
    _DIRECTION_MAP = {
        "sales_invoice":    "out",
        "purchase_invoice": "in",
        "credit_note":      "in",
        "refund":           "in",
    }

    valid_invoice_types = list(_DIRECTION_MAP.keys()) + ["proforma"]

    for i, invoice in enumerate(state["invoces"]):
        invoice.status = "verifying_inventory"

        creation_date = invoice.invoice_data.get("creation_date")
        invoice_type  = (invoice.invoice_data.get("type") or "").strip().lower()

        raw_qty = invoice.invoice_data.get("quantity", [])
        if isinstance(raw_qty, (str, int, float)):
            raw_qty = [raw_qty]

        raw_products = invoice.invoice_data.get("product_name", [])
        if isinstance(raw_products, str):
            products_names = [raw_products]
        else:
            products_names = raw_products

        final_results = {
            "status": "verified",
            "score": 0,
            "discrepancies": [],
        }
        
        has_run = False

        # Fetch ALL inventory logs (not just ≤ creation_date) so we can
        # detect future movements and reason about timing
        for inx_prod, product_name in enumerate(products_names):
            has_run = True
            safe_product_name = str(product_name).replace("'", "''")

            # Per-product invoice quantity
            inv_qty = _safe_float(raw_qty[inx_prod]) if inx_prod < len(raw_qty) else None

            try:
                result = db_connector.invoke({
                    "query": f"""
                    SELECT
                        inv.company_id,
                        inv.product_id,
                        inv.quantity_on_hand,
                        inv.last_updated,
                        inv.source_system,
                        inv.source_id,
                        il.supplier_id,
                        il.change_quantity,
                        il.change_type,
                        il.timestamp
                    FROM inventory inv
                    JOIN inventory_logs il ON inv.product_id = il.product_id
                    WHERE inv.product_id = (
                        SELECT id FROM products WHERE name = '{safe_product_name}'
                    )
                    ORDER BY il.timestamp DESC;
                    """,
                    "type": "read",
                    "source": "local_db",
                })
            except Exception as e:
                invoice.audits_results["inventory_order_verification"] = {
                    "status": "db_error",
                    "error": str(e),
                    "score": MAX_AUDIT_SCORE,
                    "discrepancies": ["db_error"],
                }
                invoice.state = "VERIFIED_WITH_ISSUES"
                state["invoces"][i] = invoice
                print(f"Inventory verification failed with DB error: {e}")
                continue

            results = json.loads(result) if isinstance(result, str) else result

            if isinstance(results, dict):
                invoice.audits_results["inventory_order_verification"] = {
                    "status": "db_error",
                    "error": results.get("error", str(results)),
                    "score": MAX_AUDIT_SCORE,
                    "discrepancies": ["db_error"],
                }
                invoice.state = "VERIFIED_WITH_ISSUES"
                state["invoces"][i] = invoice
                print(f"Inventory verification failed with DB error: {results}")
                continue

            if not results:
                score_penalty = apply_severity_penalty(0, "critical")
                discrepancy_msg = f"no inventory record found for product '{product_name}'"
                final_results["score"] += score_penalty
                final_results["discrepancies"].append(discrepancy_msg)

                if not invoice.audits_results.get("inventory_order_verification"):
                    invoice.audits_results["inventory_order_verification"] = {
                        "status": "inventory_not_found",
                        "score": score_penalty,
                        "discrepancies": [discrepancy_msg],
                    }
                print(f"Inventory verification failed: {discrepancy_msg}")
                continue

            invoice_dt = _parse_date(creation_date)

            best_prod_score = MAX_AUDIT_SCORE + 1
            best_prod_result = None

            for record in results:
                if not isinstance(record, dict):
                    continue
                    
                score = 0
                discrepancies = []

                on_hand       = _safe_float(record.get("quantity_on_hand"))
                change_qty    = _safe_float(record.get("change_quantity"))
                change_type   = (record.get("change_type") or "").strip().lower()
                log_timestamp = record.get("timestamp")
                log_dt        = _parse_date(log_timestamp)

                # ── 1. Stock flow logic ───────────────────────────
                if invoice_type and change_type:
                    expected = _DIRECTION_MAP.get(invoice_type)
                    if expected and change_type != expected:
                        score = apply_severity_penalty(score, "high")
                        discrepancies.append(
                            f"inventory movement direction mismatch: expected '{expected}' for {invoice_type}, got '{change_type}'"
                        )

                # Invoice type validation
                if invoice_type and invoice_type not in valid_invoice_types:
                    score = apply_severity_penalty(score, "medium")
                    discrepancies.append(f"unrecognized invoice type: '{invoice_type}'")

                # ── 2. Temporal consistency ───────────────────────
                if invoice_dt and log_dt:
                    delta_days = (log_dt - invoice_dt).days
                    if delta_days > 0:
                        # Log is AFTER invoice date — future movement
                        score = apply_severity_penalty(score, "medium")
                        discrepancies.append(
                            f"inventory log inconsistent with invoice timing: log={log_timestamp} is {delta_days} day(s) after invoice={creation_date}"
                        )
                    elif delta_days < -365:
                        score = apply_severity_penalty(score, "low")
                        discrepancies.append(
                            f"inventory log very old relative to invoice: log={log_timestamp}, invoice={creation_date}"
                        )

                # ── 3. Quantity realism ───────────────────────────
                if inv_qty is not None and change_qty is not None:
                    qty_diff = abs(change_qty - inv_qty)
                    if qty_diff > 0.001:
                        qty_pct = (qty_diff / max(abs(inv_qty), abs(change_qty), 1)) * 100
                        if qty_pct <= 5:
                            score = apply_severity_penalty(score, "low")
                            discrepancies.append(
                                f"minor inventory quantity difference ({qty_pct:.2f}%): log={change_qty} vs invoice={inv_qty}"
                            )
                        elif qty_pct <= 20:
                            score = apply_severity_penalty(score, "medium")
                            discrepancies.append(
                                f"inventory quantity mismatch ({qty_pct:.2f}%): log={change_qty} vs invoice={inv_qty}"
                            )
                        else:
                            score = apply_severity_penalty(score, "high")
                            discrepancies.append(
                                f"suspicious inventory quantity deviation ({qty_pct:.2f}%): log={change_qty} vs invoice={inv_qty}"
                            )

                # ── 4. Direction validation (already in #1) ──────

                # ── 5. Inventory sufficiency ──────────────────────
                if invoice_type == "sales_invoice" and on_hand is not None and inv_qty is not None:
                    if on_hand < inv_qty:
                        score = apply_severity_penalty(score, "critical")
                        discrepancies.append(
                            f"insufficient inventory for sale: on_hand={on_hand} but invoice_qty={inv_qty}"
                        )
                    elif on_hand == 0:
                        score = apply_severity_penalty(score, "high")
                        discrepancies.append("zero inventory on hand for a sales invoice")

                # ── 6. Behavioral anomalies ──────────────────────
                if change_qty is not None and on_hand is not None and on_hand > 0:
                    change_ratio = abs(change_qty) / on_hand
                    if change_ratio > 5:
                        score = apply_severity_penalty(score, "medium")
                        discrepancies.append(
                            f"sudden large stock change: change={change_qty} vs on_hand={on_hand} (ratio={change_ratio:.1f}x)"
                        )

                # ── 7. Source consistency ─────────────────────────
                if record.get("source_system") and invoice.invoice_data.get("source_system"):
                    if record["source_system"] != invoice.invoice_data["source_system"]:
                        score = apply_severity_penalty(score, "low")
                        discrepancies.append(
                            f"source system mismatch: inventory='{record['source_system']}' vs invoice='{invoice.invoice_data['source_system']}'"
                        )

                # ── Keep best candidate for this product ─────────
                if score < best_prod_score:
                    best_prod_score = score
                    best_prod_result = {
                        "status": "verified",
                        "product_id": record.get("product_id"),
                        "quantity_on_hand": on_hand,
                        "change_quantity": change_qty,
                        "change_type": change_type,
                        "score": score,
                        "discrepancies": discrepancies or ["none"],
                    }

            if best_prod_result:
                final_results["score"] += best_prod_result["score"]
                real_disc = [d for d in best_prod_result["discrepancies"] if d != "none"]
                final_results["discrepancies"].extend(real_disc)

        # ── Final result for this invoice ─────────────────────
        if not has_run:
            final_results = {
                "status": "no_products",
                "score": MAX_AUDIT_SCORE,
                "discrepancies": ["No products found in invoice to verify inventory against."]
            }
        elif final_results.get("status") == "verified":
            # Normalize score based on number of products
            prod_count = len(products_names) if len(products_names) > 0 else 1
            final_results["score"] = min(100, final_results["score"] / prod_count)
            if not final_results["discrepancies"]:
                final_results["discrepancies"] = ["none"]

        # Only overwrite if we don't already have an overriding db error result
        current_res = invoice.audits_results.get("inventory_order_verification")
        if not current_res or current_res.get("status") not in ("db_error", "inventory_not_found"):
            invoice.audits_results["inventory_order_verification"] = final_results

        final_score = invoice.audits_results["inventory_order_verification"].get("score", 0)
        invoice.state = "VERIFIED" if final_score <= PASS_RISK_THRESHOLD else "VERIFIED_WITH_ISSUES"
        
        print(f"inventory verification result: {invoice.audits_results['inventory_order_verification']}")
        state["invoces"][i] = invoice

    # ── Persist audit results to DB ───────────────────────────
    for invoice in state["invoces"]:
        inv_res = invoice.audits_results.get("inventory_order_verification")
        if inv_res is None:
            inv_res = {
                "status": "processing_error_or_invalid_data",
                "score": MAX_AUDIT_SCORE,
                "discrepancies": ["inventory data was invalid or not processed"],
            }
            invoice.audits_results["inventory_order_verification"] = inv_res

        safe_discrepancies = json.dumps(
            inv_res.get("discrepancies", [])
        ).replace("'", "''")
        db_connector.invoke({
            "query": f""" INSERT INTO audit_results (entity_type, entity_id, rule_name, risk_level, issue_detected, created_at) VALUES ('invoice', (SELECT id FROM invoices WHERE invoice_number = '{invoice.invoice_number}'), 'inventory_order_verification', '{inv_res.get("score", 0)}', '{safe_discrepancies}', datetime('now')) """,
            "type": "write",
            "source": "local_db",
        })
    return state


def tax_verification_node(state: AgentState) -> AgentState:
    """
    Verify tax correctness on each invoice.

    Deep-audit checks performed:
      1. Mathematical validation  – per-line subtotal checks (price × qty)
      2. Tax logic validation     – subtotal → tax → total chain
      3. Rounding awareness       – <0.01 never flagged
      4. Cross-check with DB      – small vs large differences graded
      5. Structural validation    – missing VAT or zero-rate anomalies
      6. Hidden anomalies         – total correct but components wrong = manipulation sign
    """
    def _sf(val, default=None):
        """Safe float conversion."""
        try:
            return float(val) if val is not None else default
        except (ValueError, TypeError):
            return default

    for i, invoice in enumerate(state["invoces"]):
        invoice.status = "verifying_tax"

        score = 0
        discrepancies = []

        # ── Extract multi-product arrays ──────────────────────
        raw_prices = invoice.invoice_data.get("price", [])
        if isinstance(raw_prices, (str, int, float)):
            raw_prices = [raw_prices]

        raw_quantities = invoice.invoice_data.get("quantity", [])
        if isinstance(raw_quantities, (str, int, float)):
            raw_quantities = [raw_quantities]

        raw_vat_classes = invoice.invoice_data.get("VAT_class", [])
        if isinstance(raw_vat_classes, (str, int, float)):
            raw_vat_classes = [raw_vat_classes]

        raw_vat  = _sf(invoice.invoice_data.get("VAT"), 0)
        vat_rate = raw_vat / 100 if raw_vat is not None else None   # VAT as decimal
        total    = _sf(invoice.invoice_data.get("total"))
        amount   = _sf(invoice.invoice_data.get("amount"))           # subtotal / untaxed

        # ── 5. Structural validation ──────────────────────────
        # (run early so we flag even before arithmetic checks)
        if raw_vat is None or raw_vat == 0:
            if total is not None and amount is not None and total != amount:
                score = apply_severity_penalty(score, "medium")
                discrepancies.append(
                    f"VAT is 0 or missing but total({total}) ≠ subtotal({amount}) — inconsistent tax structure"
                )

        # ── 1. Mathematical validation (per-line) ─────────────
        computed_subtotal = 0.0
        has_line_data = False
        num_lines = max(len(raw_prices), len(raw_quantities))

        for line_idx in range(num_lines):
            price = _sf(raw_prices[line_idx]) if line_idx < len(raw_prices) else None
            quantity = _sf(raw_quantities[line_idx]) if line_idx < len(raw_quantities) else None

            if price is not None and quantity is not None:
                has_line_data = True
                line_subtotal = round(price * quantity, 2)
                computed_subtotal += line_subtotal

        # Check computed subtotal vs invoice amount
        if has_line_data and amount is not None:
            diff = abs(computed_subtotal - amount)
            if diff > 0.01:
                pct = (diff / max(abs(computed_subtotal), abs(amount), 1)) * 100
                if pct <= 1:
                    score = apply_severity_penalty(score, "low")
                    discrepancies.append(
                        f"minor subtotal rounding ({pct:.2f}%): computed line total={computed_subtotal}, invoice amount={amount}"
                    )
                else:
                    score = apply_severity_penalty(score, "high")
                    discrepancies.append(
                        f"subtotal mismatch affects VAT ({pct:.2f}%): computed line total={computed_subtotal}, invoice amount={amount}"
                    )

        # ── 2. Tax logic: subtotal + tax = total ──────────────
        if amount is not None and vat_rate is not None and total is not None:
            expected_tax   = round(amount * vat_rate, 2)
            expected_total = round(amount + expected_tax, 2)
            diff = abs(expected_total - total)
            if diff > 0.01:
                pct = (diff / max(abs(expected_total), abs(total), 1)) * 100
                if pct <= 1:
                    score = apply_severity_penalty(score, "low")
                    discrepancies.append(
                        f"minor tax total rounding ({pct:.2f}%): amount({amount}) + VAT({raw_vat}%) = {expected_total}, invoice total={total}"
                    )
                else:
                    score = apply_severity_penalty(score, "high")
                    discrepancies.append(
                        f"invoice total inconsistent with tax structure ({pct:.2f}%): amount({amount}) + VAT({raw_vat}%) = {expected_total}, invoice total={total}"
                    )

        # ── 6. Hidden anomaly: total looks correct but components don't ──
        if has_line_data and amount is not None and total is not None and vat_rate is not None:
            expected_total_2 = round(computed_subtotal + computed_subtotal * vat_rate, 2)
            #  Total matches expectation BUT amount doesn't — manipulation indicator
            if abs(expected_total_2 - total) <= 0.01 and abs(computed_subtotal - amount) > 0.01:
                score = apply_severity_penalty(score, "high")
                discrepancies.append(
                    f"total appears correct ({total}) but subtotal is inconsistent ({amount} vs expected {computed_subtotal}) — possible manipulation"
                )

        # ── 4. Cross-check with DB ────────────────────────────
        invoice_number = (invoice.invoice_number or "").replace("'", "''")

        try:
            result = db_connector.invoke({
                "query": f"""
                SELECT
                    il.quantity,
                    il.unit_price,
                    il.subtotal,
                    t.rate as tax_rate,
                    CASE WHEN t.rate IS NOT NULL THEN il.subtotal * t.rate / 100 ELSE 0 END as tax_amount,
                    i.total_untaxed,
                    i.total_tax,
                    i.total_amount
                FROM invoices i
                JOIN invoice_lines il ON i.id = il.invoice_id
                LEFT JOIN taxes t ON il.tax_id = t.id
                WHERE i.invoice_number = '{invoice_number}';
                """,
                "type": "read",
                "source": "local_db",
            })
        except Exception as e:
            invoice.audits_results["tax_verification"] = {
                "status": "db_error",
                "error": str(e),
                "score": score,
                "discrepancies": discrepancies or ["none"],
            }
            invoice.state = "VERIFIED_WITH_ISSUES"
            state["invoces"][i] = invoice
            print(f"Tax verification failed with DB error: {e}")
            continue

        results = json.loads(result) if isinstance(result, str) else result

        if isinstance(results, dict):
            invoice.audits_results["tax_verification"] = {
                "status": "db_error",
                "error": results.get("error", str(results)),
                "score": score,
                "discrepancies": discrepancies or ["none"],
            }
            invoice.state = "VERIFIED_WITH_ISSUES"
            state["invoces"][i] = invoice
            print(f"Tax verification failed with DB error: {results}")
            continue

        if not results:
            invoice.audits_results["tax_verification"] = {
                "status": "no_db_record",
                "score": score,
                "discrepancies": discrepancies or ["none"],
            }
            invoice.state = "VERIFIED" if score <= PASS_RISK_THRESHOLD else "VERIFIED_WITH_ISSUES"
            state["invoces"][i] = invoice
            print(f"Tax verification result (no DB record): {invoice.audits_results['tax_verification']}")
            continue

        for line in results:
            if not isinstance(line, dict):
                continue
            db_qty          = _sf(line.get("quantity"))
            db_unit_price   = _sf(line.get("unit_price"))
            db_subtotal     = _sf(line.get("subtotal"))
            db_tax_rate     = _sf(line.get("tax_rate"))
            db_tax_amount   = _sf(line.get("tax_amount"), 0)
            db_total_untaxed = _sf(line.get("total_untaxed"))
            db_total_tax     = _sf(line.get("total_tax"))
            db_total_amount  = _sf(line.get("total_amount"))

            # DB line: qty × unit_price = subtotal
            if db_qty is not None and db_unit_price is not None and db_subtotal is not None:
                expected_sub = round(db_unit_price * db_qty, 2)
                diff = abs(expected_sub - db_subtotal)
                if diff > 0.01:
                    pct = (diff / max(abs(expected_sub), abs(db_subtotal), 1)) * 100
                    if pct <= 1:
                        score = apply_severity_penalty(score, "low")
                        discrepancies.append(
                            f"DB line rounding: price({db_unit_price}) × qty({db_qty}) = {expected_sub}, subtotal={db_subtotal}"
                        )
                    else:
                        score = apply_severity_penalty(score, "medium")
                        discrepancies.append(
                            f"tax calculation inconsistent in DB ({pct:.2f}%): price({db_unit_price}) × qty({db_qty}) = {expected_sub}, subtotal={db_subtotal}"
                        )

            # DB line: subtotal × rate = tax
            if db_subtotal is not None and db_tax_rate is not None:
                expected_tax = round(db_subtotal * db_tax_rate / 100, 2)
                diff = abs(expected_tax - db_tax_amount)
                if diff > 0.01:
                    pct = (diff / max(abs(expected_tax), abs(db_tax_amount), 1)) * 100
                    if pct <= 2:
                        score = apply_severity_penalty(score, "low")
                        discrepancies.append(
                            f"minor DB tax rounding: subtotal({db_subtotal}) × rate({db_tax_rate}%) = {expected_tax}, tax_amount={db_tax_amount}"
                        )
                    else:
                        score = apply_severity_penalty(score, "medium")
                        discrepancies.append(
                            f"DB tax mismatch ({pct:.2f}%): subtotal({db_subtotal}) × rate({db_tax_rate}%) = {expected_tax}, tax_amount={db_tax_amount}"
                        )

            # DB invoice: total_untaxed + total_tax = total_amount
            if db_total_untaxed is not None and db_total_tax is not None and db_total_amount is not None:
                expected_db_total = round(db_total_untaxed + db_total_tax, 2)
                diff = abs(expected_db_total - db_total_amount)
                if diff > 0.01:
                    pct = (diff / max(abs(expected_db_total), abs(db_total_amount), 1)) * 100
                    if pct <= 1:
                        score = apply_severity_penalty(score, "low")
                        discrepancies.append(
                            f"minor DB total rounding: untaxed({db_total_untaxed}) + tax({db_total_tax}) = {expected_db_total}, total={db_total_amount}"
                        )
                    else:
                        score = apply_severity_penalty(score, "medium")
                        discrepancies.append(
                            f"DB invoice total inconsistent ({pct:.2f}%): untaxed({db_total_untaxed}) + tax({db_total_tax}) = {expected_db_total}, total={db_total_amount}"
                        )

            # Invoice VAT vs DB computed tax
            if raw_vat is not None and db_tax_amount is not None and raw_vat > 0:
                # raw_vat is percentage, db_tax_amount is absolute — compare absolute amounts
                inv_vat_abs = round(amount * vat_rate, 2) if amount is not None and vat_rate is not None else None
                if inv_vat_abs is not None:
                    tax_diff = abs(inv_vat_abs - db_tax_amount)
                    if tax_diff > 0.50:
                        pct = (tax_diff / max(abs(inv_vat_abs), abs(db_tax_amount), 1)) * 100
                        if pct <= 2:
                            score = apply_severity_penalty(score, "low")
                            discrepancies.append(
                                f"minor invoice-vs-DB tax difference: invoice_tax={inv_vat_abs} vs db_tax={db_tax_amount}"
                            )
                        else:
                            score = apply_severity_penalty(score, "medium")
                            discrepancies.append(
                                f"invoice VAT inconsistent with DB ({pct:.2f}%): invoice_tax={inv_vat_abs} vs db_tax={db_tax_amount}"
                            )

            # Invoice total vs DB total
            if total is not None and db_total_amount is not None:
                total_diff = abs(total - db_total_amount)
                if total_diff > 0.01:
                    pct = (total_diff / max(abs(total), abs(db_total_amount), 1)) * 100
                    if pct <= 1:
                        score = apply_severity_penalty(score, "low")
                        discrepancies.append(
                            f"minor total difference: invoice={total} vs db={db_total_amount}"
                        )
                    else:
                        score = apply_severity_penalty(score, "medium")
                        discrepancies.append(
                            f"invoice total differs from DB ({pct:.2f}%): invoice={total} vs db={db_total_amount}"
                        )

        invoice.audits_results["tax_verification"] = {
            "status": "verified",
            "score": score,
            "discrepancies": discrepancies or ["none"],
        }
        invoice.state = "VERIFIED" if score <= PASS_RISK_THRESHOLD else "VERIFIED_WITH_ISSUES"
        print(f"Tax verification result: {invoice.audits_results['tax_verification']}")
        state["invoces"][i] = invoice

    # ── Persist audit results to DB ───────────────────────────
    for invoice in state["invoces"]:
        tax_res = invoice.audits_results.get("tax_verification")
        if tax_res is None:
            tax_res = {
                "status": "processing_error_or_invalid_data",
                "score": MAX_AUDIT_SCORE,
                "discrepancies": ["tax data was invalid or not processed"],
            }
            invoice.audits_results["tax_verification"] = tax_res

        safe_discrepancies = json.dumps(
            tax_res.get("discrepancies", [])
        ).replace("'", "''")
        db_connector.invoke({
            "query": f""" INSERT INTO audit_results (entity_type, entity_id, rule_name, risk_level, issue_detected, created_at) VALUES ('invoice', (SELECT id FROM invoices WHERE invoice_number = '{invoice.invoice_number}'), 'tax_verification', '{tax_res.get("score", 0)}', '{safe_discrepancies}', datetime('now')) """,
            "type": "write",
            "source": "local_db",
        })
    return state


def payment_verification_node(state: AgentState) -> AgentState:
    """
    Verify payment records against the invoice.

    Deep-audit checks performed:
      1. Payment completeness  – missing payments (except proforma)
      2. Under/Over payment    – graded differences
      3. Timing logic          – payments before invoice, after due date
      4. Payment pattern       – multiple small payments
      5. Behavioral anomalies  – irregular/excessive payment count
      6. Financial consistency – scan vs DB vs actual payments
    """
    from datetime import datetime as _dt

    def _parse_date(d):
        if not d:
            return None
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return _dt.strptime(str(d).strip()[:10], fmt)
            except ValueError:
                continue
        return None

    def _sf(val, default=None):
        try:
            return float(val) if val is not None else default
        except (ValueError, TypeError):
            return default

    for i, invoice in enumerate(state["invoces"]):
        invoice.status = "verifying_payment"

        score = 0
        discrepancies = []

        invoice_number = (invoice.invoice_number or "").replace("'", "''")
        invoice_total = _sf(invoice.invoice_data.get("total"))
        invoice_type = (invoice.invoice_data.get("type", "")).strip().lower()

        try:
            result = db_connector.invoke({
                "query": f"""
                SELECT
                    p.id as payment_id,
                    p.payment_date,
                    p.amount as payment_amount,
                    p.payment_method,
                    p.reference,
                    i.total_amount,
                    i.invoice_date,
                    i.due_date,
                    i.status as invoice_status
                FROM payments p
                JOIN invoices i ON p.invoice_id = i.id
                WHERE i.invoice_number = '{invoice_number}';
                """,
                "type": "read",
                "source": "local_db"
            })
        except Exception as e:
            invoice.audits_results["payment_verification"] = {
                "status": "db_error",
                "error": str(e),
                "score": MAX_AUDIT_SCORE,
                "discrepancies": ["db_error"]
            }
            invoice.state = "VERIFIED_WITH_ISSUES"
            state["invoces"][i] = invoice
            print(f"Payment verification failed with DB error: {e}")
            continue

        results = json.loads(result) if isinstance(result, str) else result

        if isinstance(results, dict):
            invoice.audits_results["payment_verification"] = {
                "status": "db_error",
                "error": results.get("error", str(results)),
                "score": MAX_AUDIT_SCORE,
                "discrepancies": ["db_error"]
            }
            invoice.state = "VERIFIED_WITH_ISSUES"
            state["invoces"][i] = invoice
            print(f"Payment verification failed with DB error: {results}")
            continue

        # ── 1. Payment completeness ───────────────────────────
        valid_results = [r for r in results if isinstance(r, dict)]
        if not valid_results:
            if invoice_type not in ("proforma", "credit_note"):
                score = apply_severity_penalty(score, "critical")
                discrepancies.append(f"no payment records found for invoice ({invoice_type})")
            invoice.audits_results["payment_verification"] = {
                "status": "no_payments_found",
                "score": score,
                "discrepancies": discrepancies or ["none"]
            }
            invoice.state = "VERIFIED" if score <= PASS_RISK_THRESHOLD else "VERIFIED_WITH_ISSUES"
            state["invoces"][i] = invoice
            print(f"Payment verification result: {invoice.audits_results['payment_verification']}")
            continue

        results = valid_results
        total_paid = 0
        db_total_amount = _sf(results[0].get("total_amount"))
        db_due_date = _parse_date(results[0].get("due_date"))
        db_invoice_date = _parse_date(results[0].get("invoice_date"))
        payment_details = []

        # ── Evaluate individual payments ──────────────────────
        for pay in results:
            pay_amount = _sf(pay.get("payment_amount"), 0)
            pay_date_raw = pay.get("payment_date")
            pay_date = _parse_date(pay_date_raw)
            total_paid += pay_amount

            payment_details.append({
                "payment_id": pay.get("payment_id"),
                "amount": pay_amount,
                "date": pay_date_raw,
                "method": pay.get("payment_method"),
                "reference": pay.get("reference")
            })

            # ── 3. Timing logic ───────────────────────────────
            if pay_date and db_due_date and pay_date > db_due_date:
                delay_days = (pay_date - db_due_date).days
                if delay_days <= 7:
                    score = apply_severity_penalty(score, "low")
                    discrepancies.append(
                        f"payment {pay.get('payment_id')} is slightly late ({delay_days} days): paid {pay_date_raw}, due {results[0].get('due_date')}"
                    )
                else:
                    score = apply_severity_penalty(score, "medium")
                    discrepancies.append(
                        f"late payment beyond due date ({delay_days} days late): paid {pay_date_raw}, due {results[0].get('due_date')}"
                    )

            if pay_date and db_invoice_date and pay_date < db_invoice_date:
                early_days = (db_invoice_date - pay_date).days
                score = apply_severity_penalty(score, "low")
                discrepancies.append(
                    f"payment {pay.get('payment_id')} made {early_days} day(s) before invoice date: paid {pay_date_raw}, invoiced {results[0].get('invoice_date')}"
                )

        # ── 4 & 5. Payment pattern & Behavioral anomalies ─────
        pay_count = len(results)
        if pay_count > 3:
            score = apply_severity_penalty(score, "low")
            discrepancies.append(
                f"payment pattern irregular: {pay_count} separate payments made for a single invoice"
            )

        # ── 2 & 6. Under/Over payment & Financial consistency ─
        if db_total_amount is not None:
            diff = abs(total_paid - db_total_amount)
            if diff > 0.01:
                pct = (diff / max(abs(db_total_amount), abs(total_paid), 1)) * 100
                if pct <= 1:
                    score = apply_severity_penalty(score, "low")
                    discrepancies.append(
                        f"minor payment rounding ({pct:.2f}%): total_paid={total_paid} vs invoice_total={db_total_amount}"
                    )
                else:
                    if total_paid < db_total_amount:
                        score = apply_severity_penalty(score, "high")
                        discrepancies.append(
                            f"underpayment detected ({pct:.2f}%): total_paid={total_paid} vs invoice_total={db_total_amount}"
                        )
                    else:
                        score = apply_severity_penalty(score, "high")
                        discrepancies.append(
                            f"overpayment detected ({pct:.2f}%): total_paid={total_paid} vs invoice_total={db_total_amount}"
                        )

        if invoice_total is not None and db_total_amount is not None:
            if abs(invoice_total - db_total_amount) > 0.01:
                score = apply_severity_penalty(score, "medium")
                discrepancies.append(
                    f"scanned total({invoice_total}) differs from DB total_amount({db_total_amount})"
                )

        invoice.audits_results["payment_verification"] = {
            "status": "verified",
            "score": score,
            "total_paid": total_paid,
            "expected_total": db_total_amount,
            "payment_count": pay_count,
            "payments": payment_details,
            "discrepancies": discrepancies or ["none"]
        }
        invoice.state = "VERIFIED" if score <= PASS_RISK_THRESHOLD else "VERIFIED_WITH_ISSUES"
        print(f"Payment verification result: {invoice.audits_results['payment_verification']}")
        state["invoces"][i] = invoice

    for invoice in state["invoces"]:
        pay_res = invoice.audits_results.get("payment_verification")
        if pay_res is None:
            pay_res = {
                "status": "processing_error_or_invalid_data",
                "score": MAX_AUDIT_SCORE,
                "discrepancies": ["payment data was invalid or not processed"],
            }
            invoice.audits_results["payment_verification"] = pay_res

        safe_discrepancies = json.dumps(
            pay_res.get("discrepancies", [])
        ).replace("'", "''")
        db_connector.invoke({
            "query": f""" INSERT INTO audit_results (entity_type, entity_id, rule_name, risk_level, issue_detected, created_at) VALUES ('invoice', (SELECT id FROM invoices WHERE invoice_number = '{invoice.invoice_number}'), 'payment_verification', '{pay_res.get("score", 0)}', '{safe_discrepancies}', datetime('now')) """,
            "type": "write",
            "source": "local_db"
        })
    return state


def ai_review_node(state: AgentState) -> AgentState:
    """Performs an AI-based review of the invoice and all verification results to provide an overall assessment."""
    # review_llm = get_helper_llm().bind_tools([db_connector, search_web])
    review_llm = helper_llm_json.bind_tools([db_connector, search_web])
    for i, invoice in enumerate(state["invoces"]):
        invoice.status = "ai_review"

        review_prompt = f"""
        json
        You are an expert financial auditor reviewing the following invoice and its verification results. 
        Based on the data provided, give an overall assessment of the invoice's authenticity and reliability.

        Invoice Data:
        {json.dumps(invoice.invoice_data, indent=2)}

        Audits Results:
        {json.dumps(invoice.audits_results, indent=2)}

        Please provide a concise summary of your assessment, highlighting any major concerns or confirming if the invoice appears legitimate.
        
        - Tools (use these as needed to support your assessment if necessary):
        1. db_connector: Use this tool to query the local database for any additional information.(you are not allowed to write anything in the database, only read)
                        Database schema details: {canonical_desc}
        2. search_web: Use this tool to search the web for any information about the supplier, product, or invoice number that could help in your assessment.

        Output Format(the output must be in strict JSON format and parsable, and should not contain any text outside the JSON, don't include any explanations, just the JSON):
        {{ "recommendation": "what are your recommendations regarding this invoice? what are your advices? and what do you suggest?", "optimization_suggestions": "if you have any suggestions on how to optimize the invoice", "score": "a score from 0 to 100 indicating the overall risk of the invoice, where 0 means fully reliable and 100 means completely unreliable","issues": "a list of any issues found with the invoice" }}"""
        try:
            msgs = [SystemMessage(content=review_prompt)]
            review_response = review_llm.invoke(msgs)
            while review_response.tool_calls:
                tool_results = _execute_tool_calls_parallel(review_response.tool_calls, {"db_connector": db_connector, "search_web": search_web})
                msgs.append(review_response)
                msgs.extend(tool_results)
                review_response = review_llm.invoke(msgs)
            print(f"AI Review for Invoice {invoice.invoice_number}: {review_response.content}")
            
            # Extract JSON from the response content
            json_match = re.search(r'\{.*\}', review_response.content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
            else:
                # Fallback or error handling if no JSON is found
                result = {"recommendation": "Could not parse AI review.", "optimization_suggestions": "", "score": 50, "issues": ["Failed to parse AI response."]}

            invoice.audits_results["ai_review"] = {"recommendation": result.get("recommendation"), "optimization_suggestions": result.get("optimization_suggestions"), "score": result.get("score"), "issues": result.get("issues")}
            invoice.state = "REVIEWED"
            state["invoces"][i] = invoice
            safe_issues = json.dumps(result.get("issues")).replace("'", "''")
            safe_recommendation = (result.get("recommendation") or "").replace("'", "''")
            db_connector.invoke({
                "query": f""" INSERT INTO audit_results (entity_type, entity_id, rule_name, risk_level, issue_detected, recommendation, created_at) VALUES ('invoice', (SELECT id FROM invoices WHERE invoice_number = '{invoice.invoice_number}'), 'ai_review', '{result.get("score")}', '{safe_issues}', '{safe_recommendation}', datetime('now')) """,
                "type": "write",
                "source": "local_db"
            })
        except Exception as e:
            print(f"AI review failed for Invoice {invoice.invoice_number} with error: {e}")
            invoice.audits_results["ai_review"] = f"AI review failed with error: {str(e)}"
            invoice.state = "REVIEWED_WITH_ISSUES"
            state["invoces"][i] = invoice

    return state

def finalize_node(state: AgentState) -> AgentState:
    """Finalizes the invoice processing, marking it as completed and ready for any downstream actions."""
    for i, invoice in enumerate(state["invoces"]):
        invoice.status = "DONE"
        total_score = 0
        for audit_name, audit_result in invoice.audits_results.items():
            if audit_name == "ai_review":
                continue  # Skip AI review score for final risk level calculation
            if isinstance(audit_result, dict):
                score = audit_result.get("score", 0)
                # Convert to float if it's a string
                total_score += float(score) if score else 0
            else:
                total_score += 0
        avg_score = total_score / (len(invoice.audits_results) - 1) if invoice.audits_results else 0
        db_connector.invoke({
            "query": f""" UPDATE audit_logs SET average_score = {avg_score}, ai_score = {invoice.audits_results.get("ai_review", {}).get("score", 0)}, risk_level = '{risk_level(avg_score)}' WHERE entity_type = 'invoice' AND entity_id = (SELECT id FROM invoices WHERE invoice_number = '{invoice.invoice_number}'); """,
            "type": "write",
            "source": "local_db"
        })
    state["invoces"] = []
    return state

def risk_level(score):
    if score <= 20:
        return "low"
    elif score <= 50:
        return "medium"
    elif score <= 75:
        return "high"
    else:        
        return "critical"