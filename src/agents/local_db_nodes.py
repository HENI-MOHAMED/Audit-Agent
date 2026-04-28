from langchain_core.messages import SystemMessage, HumanMessage
import os
import json
import re

from src.utils.config import get_helper_llm, get_llm, MAX_TOOL_ITERATIONS, helper_llm_json, llm, helper_llm_resoner
from src.api.models import AgentState
from src.database.db_tools import db_connector, import_file_to_local_db
from src.tools.document_tools import scan_documents, Retreave_from_email, Retreave_from_google_drive
from src.agents.audit_agents import _execute_tool_calls_parallel

CANONICAL_SCHEMA: dict[str, list[str]] = {
        "companies":       ["name", "tax_id", "address", "email", "phone"],
        "contacts":        ["company_id", "name", "type", "tax_number", "email", "phone", "address", "source_system", "source_id"],
        "products":        ["company_id", "name", "description", "price", "cost", "type", "source_system", "source_id"],
        "taxes":           ["company_id", "name", "rate", "type", "description"],
        "accounts":        ["company_id", "code", "name", "type", "source_system", "source_id"],
        "journal_entries": ["company_id", "entry_date", "reference", "description", "source_system", "source_id","movement_type"],
        "journal_lines":   ["journal_entry_id", "account_id", "debit", "credit", "description"],
        "invoices":        ["supplier_id", "supplier_name", "customer_id", "customer_name", "invoice_number", "type", "currency", "exchange_rate", "invoice_date", "due_date", "total_untaxed", "total_tax", "total_amount", "status", "source_system", "source_id"],
        "invoice_lines":   ["invoice_id", "product_id", "description", "quantity", "unit_price", "tax_id", "subtotal"],
        "payments":        ["invoice_id", "payment_date", "amount", "payment_method", "reference", "source_system", "source_id"],
        "attachments":     ["invoice_id", "file_name", "file_path"],
        "audit_results":   ["entity_type", "entity_id", "rule_name", "risk_level", "issue_detected", "recommendation", "ai_confidence"],
        "audit_logs":      ["entity_type", "entity_id", "action", "details","average_score","ai_score","risk_level"],
        "purchase_orders":  ["company_id", "contact_id", "order_number", "order_date", "due_date", "total_amount", "status", "source_system", "source_id"],
        "purchase_order_lines": ["purchase_order_id", "product_id", "description", "quantity", "unit_price", "tax_id", "subtotal"],
        "inventory":        ["company_id", "product_id", "quantity_on_hand", "last_updated", "source_system", "source_id"],
        "inventory_logs":   ["supplier_id", "product_id", "change_quantity", "change_type", "timestamp", "source_system", "source_id"]
    }
db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "ai_audit_db.sqlite")

canonical_desc = "\n".join(
            f"{tbl}: {', '.join(cols)}"
            for tbl, cols in CANONICAL_SCHEMA.items()
        )

def local_db(state: "AgentState") -> "AgentState":

    mapping_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage", "json_configs", "mapping_cache.json")

    # ------------------------------------------------
    # CANONICAL SCHEMA DEFINITION (single source of truth)
    # ------------------------------------------------

    
    

    # ------------------------------------------------
    # CREATE OR CONNECT TO AI AUDIT DATABASE
    # Drop and recreate so the schema is always up-to-date
    # ------------------------------------------------

    import sqlite3
    if not os.path.exists(db_path):
        print("Creating new ai_audit_db.sqlite")
        conn = sqlite3.connect(db_path)
        # Disable FK enforcement during bulk import — Odoo IDs don't match
        # the auto-incremented SQLite IDs, so FK checks would always fail.
        conn.execute("PRAGMA foreign_keys = OFF")

        cursor = conn.cursor()

        # ------------------------------------------------
        # CREATE CANONICAL TABLES
        # ------------------------------------------------

        cursor.executescript("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT ,
            tax_id TEXT,
            address TEXT,
            email TEXT,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
            name TEXT,
            type TEXT,
            tax_number TEXT,
            email TEXT,
            phone TEXT,
            address TEXT,
            source_system TEXT,
            source_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_contacts_company ON contacts(company_id);

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
            name TEXT,
            description TEXT,
            price REAL,
            cost REAL,
            type TEXT,
            source_system TEXT,
            source_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_products_company ON products(company_id);

        CREATE TABLE IF NOT EXISTS taxes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
            name TEXT,
            rate REAL,
            type TEXT,
            description TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_taxes_company ON taxes(company_id);

        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
            code TEXT ,
            name TEXT,
            type TEXT,
            source_system TEXT,
            source_id TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_accounts_company ON accounts(company_id);

        CREATE TABLE IF NOT EXISTS journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
            entry_date TEXT ,
            reference TEXT,
            description TEXT,
            source_system TEXT,
            source_id TEXT,
            movement_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_journal_company ON journal_entries(company_id);

        CREATE TABLE IF NOT EXISTS journal_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            journal_entry_id INTEGER REFERENCES journal_entries(id) ON DELETE CASCADE,
            account_id INTEGER REFERENCES accounts(id),
            debit REAL DEFAULT 0,
            credit REAL DEFAULT 0,
            description TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_journal_lines_entry ON journal_lines(journal_entry_id);

        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER REFERENCES contacts(id),
            supplier_name TEXT,
            customer_id INTEGER REFERENCES contacts(id),
            customer_name TEXT,
            invoice_number TEXT,
            type TEXT,
            currency TEXT DEFAULT 'TND',
            exchange_rate REAL DEFAULT 1,
            invoice_date TEXT,
            due_date TEXT,
            total_untaxed REAL,
            total_tax REAL,
            total_amount REAL,
            status TEXT,
            source_system TEXT,
            source_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_invoices_supplier ON invoices(supplier_id);
        CREATE INDEX IF NOT EXISTS idx_invoices_customer ON invoices(customer_id);

        CREATE TABLE IF NOT EXISTS invoice_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER REFERENCES invoices(id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id),
            description TEXT,
            quantity REAL,
            unit_price REAL,
            tax_id INTEGER REFERENCES taxes(id),
            subtotal REAL
        );

        CREATE INDEX IF NOT EXISTS idx_invoice_lines_invoice ON invoice_lines(invoice_id);

        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER REFERENCES invoices(id) ON DELETE CASCADE,
            payment_date TEXT,
            amount REAL,
            payment_method TEXT,
            reference TEXT,
            source_system TEXT,
            source_id TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id);

        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER REFERENCES invoices(id) ON DELETE CASCADE,
            file_name TEXT,
            file_path TEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS audit_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT,
            entity_id INTEGER,
            rule_name TEXT,
            risk_level TEXT,
            issue_detected TEXT,
            recommendation TEXT,
            ai_confidence REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_results(entity_type, entity_id);

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT,
            entity_id INTEGER,
            action TEXT,
            details TEXT,
            average_score REAL,
            ai_score REAL,
            risk_level TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
                             
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
            contact_id INTEGER REFERENCES contacts(id),
            order_number TEXT,
            order_date TEXT,
            due_date TEXT,
            total_amount REAL,
            status TEXT,
            source_system TEXT,
            source_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
                    
        CREATE INDEX IF NOT EXISTS idx_purchase_orders_company ON purchase_orders(company_id);
        CREATE INDEX IF NOT EXISTS idx_purchase_orders_contact ON purchase_orders(contact_id);
                
        CREATE TABLE IF NOT EXISTS purchase_order_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_order_id INTEGER REFERENCES purchase_orders(id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id),
            description TEXT,
            quantity REAL,
            unit_price REAL,
            tax_id INTEGER REFERENCES taxes(id),
            subtotal REAL
        );
                             
        CREATE INDEX IF NOT EXISTS idx_po_lines_order ON purchase_order_lines(purchase_order_id);
                
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id),
            quantity_on_hand REAL,
            last_updated TEXT,
            source_system TEXT,
            source_id TEXT
        );
                             
        CREATE INDEX IF NOT EXISTS idx_inventory_product ON inventory(product_id);
        CREATE INDEX IF NOT EXISTS idx_inventory_company ON inventory(company_id);
                             
        CREATE TABLE IF NOT EXISTS inventory_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER REFERENCES contacts(id),
            product_id INTEGER REFERENCES products(id),
            change_quantity REAL,
            change_type TEXT,
            timestamp TEXT,
            source_system TEXT,
            source_id TEXT
        );
        
        CREATE INDEX IF NOT EXISTS idx_inventory_logs_product ON inventory_logs(product_id);
        CREATE INDEX IF NOT EXISTS idx_inventory_logs_supplier ON inventory_logs(supplier_id);
        
                             
        """)

        conn.commit()
        print("Canonical schema ready")

    # Open connection for the data-transfer loop (always, whether DB was just created or already existed)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA foreign_keys = OFF")
    cursor = conn.cursor()

    # ------------------------------------------------
    # LOAD OR GENERATE MAPPING
    # ------------------------------------------------

    # Always fetch the Odoo schema for schema export
    odoo_schema_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage", "json_configs", "odoo_schema.json")
    
    if os.path.exists(mapping_file):

        with open(mapping_file) as f:
            mapping = json.load(f)

        print("Loaded mapping_cache.json")
        
        # Fetch and save the current Odoo schema even if mapping exists
        print("Fetching current Odoo schema...")
        RELEVANT_TABLE_KEYWORDS = (
            'account','ledger','journal','entry','move','posting',
            'invoice','bill','receipt','voucher','statement',
            'payment','pay','transaction','reconcile','settlement',
            'partner','customer','client','vendor','supplier','contact',
            'product','item','service','inventory','stock',
            'order','purchase','sale','po','so',
            'tax','vat','fiscal','duty','withholding',
            'expense','revenue','income','cost','budget','asset',
            'company','organization','business','branch',
            'currency','rate','exchange',
            'reconcile','match','clearing',
            'salary','payroll','wage',
            'analytic','dimension','cost_center',
            'audit','log','history'
        )
        
        tables_json = db_connector.invoke({"query": """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema='public'
        """, "type": "read", "source": state["db_source"]})
        
        all_tables = json.loads(tables_json)
        tables = [t for t in all_tables if any(kw in t["table_name"].lower() for kw in RELEVANT_TABLE_KEYWORDS)]
        
        schema = {}
        for t in tables:
            table = t["table_name"]
            cols_json = db_connector.invoke({"query": f"""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='{table}'
            """, "type": "read", "source": state["db_source"]})
            cols = json.loads(cols_json)
            schema[table] = [c["column_name"] for c in cols]
        
        os.makedirs(os.path.dirname(odoo_schema_file), exist_ok=True)
        with open(odoo_schema_file, "w") as f:
            json.dump(schema, f, indent=2)
        print(f"Saved Odoo schema with {len(schema)} tables to odoo_schema.json")

    else:

        print("Generating mapping using DeepSeek")

        # Only fetch tables relevant to accounting/audit to keep the prompt small
        RELEVANT_TABLE_KEYWORDS = (
            # accounting core
            'account','ledger','journal','entry','move','posting',

            # invoices / bills
            'invoice','bill','receipt','voucher','statement',

            # payments
            'payment','pay','transaction','reconcile','settlement',

            # partners / contacts
            'partner','customer','client','vendor','supplier','contact',

            # products
            'product','item','service','inventory','stock',

            # orders
            'order','purchase','sale','po','so',

            # taxes
            'tax','vat','fiscal','duty','withholding',

            # finance
            'expense','revenue','income','cost','budget','asset',

            # company / org
            'company','organization','business','branch',

            # currencies
            'currency','rate','exchange',

            # reconciliation
            'reconcile','match','clearing',

            # payroll
            'salary','payroll','wage',

            # analytics
            'analytic','dimension','cost_center',

            # audit
            'audit','log','history'
        )

        tables_json = db_connector.invoke({"query": """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema='public'
        """, "type": "read", "source": state["db_source"]})

        all_tables = json.loads(tables_json)

        # Filter: keep only tables whose name contains a relevant keyword
        tables = []
        for t in all_tables:

            name = t["table_name"].lower()

            if any(kw in name for kw in RELEVANT_TABLE_KEYWORDS):
                tables.append(t)
        print(f"Filtered {len(tables)} relevant tables out of {len(all_tables)} total")

        schema = {}

        for t in tables:

            table = t["table_name"]

            cols_json = db_connector.invoke({"query": f"""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='{table}'
            """, "type": "read", "source": state["db_source"]})

            cols = json.loads(cols_json)

            schema[table] = [c["column_name"] for c in cols]

        # Save the extracted Odoo schema to a JSON file
        odoo_schema_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage", "json_configs", "odoo_schema.json")
        os.makedirs(os.path.dirname(odoo_schema_file), exist_ok=True)
        with open(odoo_schema_file, "w") as f:
            json.dump(schema, f, indent=2)
        print(f"Saved Odoo schema with {len(schema)} tables to odoo_schema.json")



        prompt = f"""
Map this {state['db_source']} schema to the canonical audit schema.

{state['db_source']} schema:
{json.dumps(schema, indent=2)}

Canonical tables and their columns:
{canonical_desc}

CRITICAL RULES — you MUST follow all of them:
1. Include a mapping entry for EVERY canonical column listed above — do NOT omit any.
2. Map each canonical column to the closest {state['db_source']} column in the chosen source table.
4. For `source_id`, map it to the {state['db_source']} table's primary key (almost always `id`).
5. If a column name is identical in both schemas, map it to itself.
6. Never leave a canonical column out of field_mapping, even if the match is approximate.
7. Only use tables that appear in the provided schema.
8. If multiple tables fit a canonical table, choose the most semantically similar.
9. If a source table contains different types of records, use the `where_clause` field to write a valid SQL WHERE condition to isolate only the rows that belong in the respective canonical table.
10. IMPORTANT: If the canonical schema requires a name or detail field (like `supplier_name`) but the source table only has an ID (like `partner_id`), you MUST write a valid SQL scalar subquery in the mapping value to fetch it. Example: "(SELECT name FROM res_partner WHERE res_partner.id = account_move.partner_id) not only for names but everything".
11. You can also use other SQL expressions or functions if needed, like string literals (e.g. "'odoo'").

Return ONLY a JSON object in this exact format (no extra text):
{{
  "canonical_table_name": {{
    "source_table": "{state['db_source']}_table_name",
    "where_clause": "SQL WHERE condition if needed to filter rows, else null",
    "field_mapping": {{
      "canonical_column": "{state['db_source']}_column_or_quoted_constant_or_subquery"
    }}
  }}
}}
"""
        print(f"Prompt length: {len(prompt)} characters")
        response = helper_llm_resoner.invoke([HumanMessage(content=prompt)])
        print(f"DeepSeek mapping response: {response.content} \n \n")

        raw = response.content.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw).strip()
        mapping = json.loads(raw)

        # Validate mapping: only allow canonical columns defined in CANONICAL_SCHEMA
        for canon, cfg in list(mapping.items()):
            src = cfg.get("source_table", "")
            if src not in schema:
                print(f"Warning: source table '{src}' not found, removing '{canon}'")
                del mapping[canon]
                continue
            valid_odoo_cols = set(schema[src])
            valid_canon_cols = set(CANONICAL_SCHEMA.get(canon, []))
            bad = [
                k for k, v in cfg["field_mapping"].items()
                # We can only strictly validate the canonical columns. The value is now a SQL expression, so we can't easily validate it against valid_odoo_cols.
                if k not in valid_canon_cols
            ]
            for k in bad:
                print(f"Warning: dropping invalid mapping '{k}' -> '{cfg['field_mapping'][k]}' for '{canon}'")
                del cfg["field_mapping"][k]

        os.makedirs(os.path.dirname(mapping_file), exist_ok=True)
        with open(mapping_file, "w") as f:
            json.dump(mapping, f, indent=2)

        print("Saved mapping_cache.json")

    # ------------------------------------------------
    # DATA TRANSFER
    # ------------------------------------------------

    for canonical_table, config in mapping.items():

        source_table = config["source_table"]
        field_map = config["field_mapping"]
        where_clause = config.get("where_clause")

        if not field_map:
            print(f"Skipping {canonical_table}: no valid field mappings")
            continue

        select_parts = []
        for c_field, s_expr in field_map.items():
            select_parts.append(f"{s_expr} AS {c_field}")
        source_fields = ", ".join(select_parts)

        query = f"SELECT {source_fields} FROM {source_table}"
        if where_clause:
            query += f" WHERE {where_clause}"

        rows_json = db_connector.invoke({
            "query": query,
            "type": "read",
            "source": state["db_source"]
        })

        rows = json.loads(rows_json)

        if not isinstance(rows, list):
            print(f"Skipping {canonical_table}: query error – {rows}")
            continue

        batch = []
        columns = list(field_map.keys())

        for row in rows:
            values = []

            for c_field, s_field in field_map.items():
                val = row.get(c_field)
                # SQLite can't bind dict/list — serialize to JSON string
                if isinstance(val, (dict, list)):
                    val = json.dumps(val, ensure_ascii=False)
                values.append(val)

            batch.append(values)

        if batch:
            placeholders = ",".join(["?"] * len(columns))
            query = f"""
            INSERT INTO {canonical_table}
            ({",".join(columns)})
            VALUES ({placeholders})
            """
            cursor.executemany(query, batch)

        print(f"Imported {len(rows)} rows into {canonical_table}")

    conn.commit()
    conn.close()
    remove_duplicates_from_all_tables(db_path=db_path)

    return state


#Local database AI Agent Node
def local_db_agent(state: AgentState) -> AgentState:
    """An AI agent that can read from and write to the local SQLite database based on the user's query."""
    
    system_prompt = SystemMessage(content=f"""
You are a Local Database Agent.

Your role is to process document content, extract structured business and accounting data, 
and store it correctly in the local database using the db_connector tool.

You act as a data ingestion and structuring agent for an AI audit system.

--------------------------------------------------
MISSION
--------------------------------------------------

When you receive a document:

1. Extract all relevant structured information from the document.
2. Insert the extracted information directly into the database.
3. Store the extracted information in the correct tables.
4. Maintain proper relationships between entities using the generated IDs that SQLite returns or by executing the inserts sequentially.

You must store structured data so that it can later be audited by other AI agents.

--------------------------------------------------
DATABASE ACCESS TOOL
--------------------------------------------------

You have access to two tools:

1. db_connector
   Arguments:
   - query: SQL query string
   - type: "read" or "write"
   - source: database source
   For ALL queries in this agent you MUST use source = "local_db" and type = "write".
   IMPORTANT: Use db_connector 90% of the time, especially for general document processing.

2. import_file_to_local_db
   Arguments:
   - file_path: Path to the CSV or XLSX file
   - mapping: A JSON mapping linking canonical columns to file columns, optionally including a "where_clause" using pandas query syntax to filter rows (e.g. "status == 'paid'").
   - transformations: (optional) A JSON mapping linking canonical tables and columns to Python expressions that alter the data. Example:""" + """ `{"products": {"name": "str(x).replace('{name: ', '').replace('}', '')"}}` or `{"invoices": {"invoice_date": "(pd.to_datetime(str(x), format='%Y%m%d', errors='coerce').strftime('%Y-%m-%d') if pd.notnull(pd.to_datetime(str(x), format='%Y%m%d', errors='coerce')) else None)"}}`.""" + """ Use `x` as the variable for the column value.
   ONLY use this tool for MASSIVE CSV, XLS, or XLSX files. Do NOT use it for small files or standard documents. When you do use it, make absolutely sure the columns in the mapping matches the ones found in the file chunks.

--------------------------------------------------
DATABASE SCHEMA
--------------------------------------------------

{canonical_desc}

IMPORTANT: You are STRICTLY FORBIDDEN from creating new tables or using any columns not explicitly listed above. You must ONLY use the exact tables and columns provided in this schema.

--------------------------------------------------
DATA INGESTION WORKFLOW
--------------------------------------------------

For the `products` table, use 'sell' as the default value for the `type` column. Only put 'buy' if the document explicitly indicates the company is buying the product to use rather than selling it to a customer.

Always follow this order:

1) Identify the company (vendor or issuer) and insert it.
2) Identify the contact (customer or recipient) and insert it.
3) Identify the invoice or document reference and insert it.
4) Identify products or services and insert them.
5) Insert invoice line items.
6) Insert payment information if present.
7) Create accounting journal entries if enough information exists.
8) Store the document path in attachments.

--------------------------------------------------
DUPLICATE PREVENTION
--------------------------------------------------

DO NOT check for duplicates. NEVER query the database to see if a record already exists. 
Just instantly insert the new records directly into the tables. Do NOT use SELECT queries.

--------------------------------------------------
ACCOUNTING RULES
--------------------------------------------------

Invoices must store financial totals.

If an invoice contains:
    charges
    credits
    taxes

Then:

total_untaxed = sum of positive charges
total_tax = tax amount
total_amount = final payable amount

Do not lose financial information.

Invoice line items must reflect the document exactly.

--------------------------------------------------
WHEN TO IGNORE A DOCUMENT
--------------------------------------------------

If the document does not contain any data relevant to the strict canonical schema (e.g., random textual paragraphs, non-financial/non-accounting files, images with no structural data), YOU MUST SKIP IT. DO NOT FORCE irrelevant data into the tables.
ONLY process documents that actually contain relevant accounting data (such as companies, contacts, invoices, journal entries, products).
If the document is a database export, CSV dump, JSON list, or ANY other tabular format that contains relevant accounting data, YOU ABSOLUTELY MUST PROCESS AND INSERT EVERY SINGLE RECORD. Do NOT ignore it. Do NOT skip records.

--------------------------------------------------
SQL SAFETY RULES
--------------------------------------------------

Only execute valid SQL.

Allowed operations:

INSERT
UPDATE

Avoid:

CREATE
DROP
DELETE
ALTER
SELECT

Never modify the schema, never create new tables, and never use columns that are not explicitly listed in the DATABASE SCHEMA.

--------------------------------------------------
ANTI-LOOP RULES
--------------------------------------------------

To avoid infinite loops:

- Do not repeat the same query multiple times.
- Once you execute an INSERT, assume it works and move on.

--------------------------------------------------
OUTPUT BEHAVIOR
--------------------------------------------------

Your job is to store data, not explain or evaluate it. 
CRITICAL RULE: DO NOT BE LAZY. DO NOT WORRY ABOUT TOKEN LIMITS OR EXHAUSTION.
Even if the data is a massive database export, log file, CSV, or a continuation of an export chunk, you MUST insert ALL OF IT into the local database without making excuses. 

After processing ALL the data, return a VERY short summary of:

- what entities were created
- what data was stored
- what invoice was processed

Keep the final response concise, but DO NOT skip the database insertion step under any circumstances.

--------------------------------------------------
END OF INSTRUCTIONS
--------------------------------------------------
""")
    docs = state["local_db_files"]
    state["local_db_files"] = []  # clear after processing to avoid re-processing in loops
    db_llm = get_helper_llm().bind_tools([db_connector, import_file_to_local_db])
    db_tool_map = {
        "db_connector": db_connector,
        "import_file_to_local_db": import_file_to_local_db
    }

    import concurrent.futures

    def _process_doc(d):
        print(f"Processing document '{d}' with Local Database Agent...")
        try:
            is_large_tabular = False
            total_rows = 0
            sample_data = ""
            
            ext = d.lower().split('.')[-1]
            if ext in ['csv', 'xls', 'xlsx']:
                import pandas as pd
                try:
                    if ext == 'csv':
                        df = pd.read_csv(d)
                    else:
                        df = pd.read_excel(d)
                        
                    total_rows = len(df)
                    if total_rows > 20:
                        is_large_tabular = True
                        sample_data = df.head(10).to_string(index=False)
                except Exception as e:
                    print(f"Error reading tabular file {d} with pandas: {e}")

            msgs = [system_prompt]
            response = None
            
            if is_large_tabular:
                chunk = f"File is a large tabular document with {total_rows} rows.\nHere are the first 10 sample rows:\n{sample_data}\n\nDO NOT USE db_connector. You MUST use import_file_to_local_db to insert the data using a correct mapping. If you need to filter rows, include a `where_clause`. If you need to format dates or clean noise, include `transformations`. Use `x` as the variable for modifications. The file path is: {d}"
                doc_chunks = [chunk]
            else:
                doc_content = scan_documents.invoke(d)
                doc_chunks = [doc_content[i:i+30000] for i in range(0, len(doc_content), 30000)]

            for chunk in doc_chunks:
                msgs.append(HumanMessage(content=f"Document chunk:\n{chunk}\n\n File path: {d}"))
                if len([m for m in msgs if isinstance(m, HumanMessage)]) > 2:
                    for i, m in enumerate(msgs):
                        if isinstance(m, HumanMessage):
                            msgs.pop(i)
                            break
                for _iteration in range(100):  # allow more iterations for complex document processing
                    response = db_llm.invoke(msgs)
                    msgs.append(response)
                    if not response.tool_calls:
                        break
                    tool_results = _execute_tool_calls_parallel(response.tool_calls, db_tool_map)
                    msgs.extend(tool_results)
                else:
                    print(f"WARNING: Local DB Agent reached maximum tool iterations for '{d}'.")
            
            if response:
                print(f"Local Database Agent processed document '{d}' with response: {response.content} \n \n")
        except Exception as e:
            print(f"Error processing document '{d}': {e}")

    # Process documents in parallel using threads
    # Using a modest max_workers to avoid overwhelming the LLM API or locking SQLite concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(_process_doc, d) for d in docs]
        concurrent.futures.wait(futures)
    remove_duplicates_from_all_tables(db_path=db_path)

    return state


#Get documents for the local database Node
def get_local_db_documents(state: AgentState) -> AgentState:
    """A node that retrieves the file paths of documents that need to be processed and stored in the local database. It updates the state with a list of file paths under the key 'local_db_files'."""
    # For demonstration, we will just use a hardcoded list of file paths. In a real implementation, this could be dynamic based on user input or a directory scan.
    # i will create a better one that takes the files paths from the frontend that the user selected but for now this will do the job.
    doc = str(input("Enter the file path of the document to process for the local database (or 'done' to finish): "))
    files = []
    while doc.lower() != 'done':
        if os.path.exists(doc):
            files.append(doc)
            print(f"Added '{doc}' for processing.")
        else:
            print(f"File '{doc}' not found. Please enter a valid file path.")
        doc = str(input("Enter the file path of the document to process for the local database (or 'done' to finish): "))
    state["local_db_files"] = files
    return state
def clean_llm_json(raw: str):
    import re
    raw = raw.strip()

    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
    if raw.endswith("```"):
        raw = re.sub(r"\n?```$", "", raw).strip()

    import json
    return json.loads(raw)

def local_db_terminology_agent(state: AgentState) -> AgentState:

    import os
    import json
    import re

    mapping_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage", "json_configs", "terminology_mapping.json")

    # ------------------------------------------------
    # CANONICAL TERMINOLOGY
    # ------------------------------------------------

    canonical_hints = {
        "invoices": {
            "type": ["in_invoice", "out_invoice", "in_refund", "out_refund", "external", "sales_invoice", "purchase_invoice", "credit_note", "refund", "proforma"],
            "status": ["draft", "paid", "not_paid", "partial"]
        },
        "contacts": {
            "type": ["supplier", "customer"]
        },
        "products": {
            "type": ["sell", "buy"]
        },
        "purchase_orders": {
            "status": ["purchase", "draft", "sent", "pending", "cancel", "cancelled", "rejected", "done"]
        },
        "audit_logs": {
            "entity_type": ["invoice", "purchase_order", "payment", "inventory", "product", "company", "contact", "journal_entry"],
            "action": ["audit"],
            "risk_level": ["low", "medium", "high", "critical"]
        },
        "audit_results": {
            "entity_type": ["invoice", "purchase_order", "payment", "inventory", "product", "company", "contact", "journal_entry"],
            "rule_name": ["supplier_authenticity", "purchase_order_verification", "inventory_order_verification", "tax_verification", "payment_verification", "ai_review"]
        },
        "inventory_logs": {
            "change_type": ["in", "out"]
        }
    }

    canonical_values = set(
        v for table_hints in canonical_hints.values() for col_hints in table_hints.values() for v in col_hints
    )

    tables = [
        "contacts",
        "products",
        "taxes",
        "accounts",
        "inventory",
        "purchase_orders",
        "inventory_logs",
        "payments",
        "audit_results",
        "invoices",
    ]

    # ------------------------------------------------
    # HELPER FUNCTIONS
    # ------------------------------------------------

    


    def validate_mapping(mapping: dict):

        valid = {}

        for table, columns in mapping.items():

            valid[table] = {}

            for col, value_map in columns.items():

                filtered = {}
                for src, canonical in value_map.items():

                    if canonical in canonical_values:
                        filtered[src] = canonical

                if filtered:
                    valid[table][col] = filtered

        return valid


    def apply_mapping(record: dict, table: str, mapping: dict):

        if table not in mapping:
            return record

        new_record = {}

        for k, v in record.items():

            value = v

            if (
                table in mapping
                and k in mapping[table]
                and isinstance(v, str)
            ):
                value = mapping[table][k].get(v, v)

            new_record[k] = value

        return new_record


    def apply_terminology_to_db(m: dict):
        import sqlite3
        _db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "ai_audit_db.sqlite")
        if not os.path.exists(_db_path):
            return
        conn = sqlite3.connect(_db_path)
        cursor = conn.cursor()
        updated = 0
        for tbl, cols in m.items():
            for col, value_map in cols.items():
                for src_val, canonical_val in value_map.items():
                    if src_val == canonical_val:
                        continue
                    cursor.execute(
                        f"UPDATE {tbl} SET {col} = ? WHERE {col} = ?",
                        (canonical_val, src_val)
                    )
                    updated += cursor.rowcount
        conn.commit()
        conn.close()
        print(f"Terminology mapping applied: {updated} values normalized")


    # ------------------------------------------------
    # LOAD EXISTING MAPPING (CACHE)
    # ------------------------------------------------

    if os.path.exists(mapping_file):

        with open(mapping_file) as f:
            mapping = json.load(f)

        apply_terminology_to_db(mapping)
        state["terminology_mapping"] = mapping
        state["apply_mapping"] = apply_mapping

        return state

    # ------------------------------------------------
    # EXTRACT DISTINCT TERMINOLOGY VALUES
    # ------------------------------------------------

    target_columns = {
        "invoices": ["type", "status"],
        "contacts": ["type"],
        "products": ["type"],
        "purchase_orders": ["status"],
        "audit_logs": ["entity_type", "action", "risk_level"],
        "audit_results": ["entity_type", "rule_name"],
        "inventory_logs": ["change_type"]
    }

    terminology_samples = {}

    for table, columns in target_columns.items():
        for col_name in columns:
            try:
                query = f"""
                SELECT DISTINCT {col_name}
                FROM {table}
                WHERE {col_name} IS NOT NULL
                """

                result = db_connector.invoke({
                    "query": query,
                    "type": "read",
                    "source": "local_db"
                })

                values = json.loads(result)

                values = [
                    v[col_name]
                    for v in values
                    if isinstance(v[col_name], str)
                ]

                if not values:
                    continue

                terminology_samples.setdefault(table, {})
                terminology_samples[table][col_name] = values

            except:
                continue

    # ------------------------------------------------
    # LLM PROMPT
    # ------------------------------------------------

    system_prompt = SystemMessage(content="""
You are a terminology normalization agent for ERP data.

Your job is to map ERP terminology values to canonical audit terminology.

Rules:

1. Only map categorical values.
2. Do NOT map column names.
3. Try to find the closest matching canonical term if an exact match isn't present.
4. Only use canonical values provided.
5. If a value is already canonical, map it to itself.
6. Ignore null or numeric values.
7. For the products table 'type' column, use 'sell' as the default canonical value unless the source value explicitly indicates 'buy'.

Return JSON only.

Format:

{
  "table": {
    "column": {
      "source_value": "canonical_value"
    }
  }
}
""")

    prompt = f"""
ERP terminology values:

{json.dumps(terminology_samples, indent=2)}

Canonical terminology options:

{json.dumps(canonical_hints, indent=2)}

Create the mapping.
Return JSON only.
"""

    # ------------------------------------------------
    # LLM CALL
    # ------------------------------------------------

    response = helper_llm_json.invoke([
        system_prompt,
        HumanMessage(content=prompt)
    ])

    raw = response.content

    try:
        mapping = clean_llm_json(raw)
    except Exception as e:
        print(f"Failed to parse LLM JSON: {e}")
        print(f"Raw response: {raw}")
        mapping = {}

    # ------------------------------------------------
    # VALIDATE MAPPING
    # ------------------------------------------------

    mapping = validate_mapping(mapping)

    # ------------------------------------------------
    # SAVE/MERGE MAPPING
    # ------------------------------------------------

    if os.path.exists(mapping_file):
        try:
            with open(mapping_file, "r") as f:
                old_mapping = json.load(f)
            
            for table, columns in old_mapping.items():
                if table not in mapping:
                    mapping[table] = columns
                else:
                    for col, value_map in columns.items():
                        if col not in mapping[table]:
                            mapping[table][col] = value_map
                        else:
                            # Keep new mapping, backfill old ones not mapped
                            for src, canonical in value_map.items():
                                if src not in mapping[table][col]:
                                    mapping[table][col][src] = canonical
        except:
            pass

    os.makedirs(os.path.dirname(mapping_file), exist_ok=True)
    with open(mapping_file, "w") as f:
        json.dump(mapping, f, indent=2)

    # ------------------------------------------------
    # STORE IN STATE
    # ------------------------------------------------

    apply_terminology_to_db(mapping)
    state["terminology_mapping"] = mapping
    state["apply_mapping"] = apply_mapping

    return state


# Process emails for the local database Node 
def process_emails_agent(state: AgentState) -> AgentState:
    query = state.get("user_input", "")
    print(f"Processing emails with query: {query}")
    """An AI agent that processes emails to extract structured information about company transactions and invoices, and stores this information in the local database. The agent uses the IMAP protocol to access the email inbox, identifies relevant emails based on the query, and extracts data such as company names, invoice numbers, transaction details, dates, senders, and receivers."""
    system_prompt = SystemMessage(content=f""" You are an email processing agent for an AI audit system.
                                  your task is to read emails and google Drive, extract structured information about company transactions, invoices, supplyers, customers, and all relevant data, and store it in the local database.
                                  tools you can use:
                                  - db_connector: to read/write from the local database. Always use source = "local_db" for this tool.
                                  - Retreave_from_email: to read emails from the inbox using IMAP protocol. It takes a query argument to filter relevant emails. OR(subject=query, text=query, from_=query, to=query)
                                  - scan_documents: to extract text content from email attachments (e.g. invoices, bills, receipts) for further processing.
                                  - Retreave_from_google_drive: to read documents from google drive. It takes a query argument to filter relevant documents based on their name or content.
                                    Follow this workflow:
                                    1) Use Retreave_from_email to find relevant emails based on the user's query.
                                    2) For each relevant email, extract structured information such as:
                                        - company names (suppliers, customers)
                                        - invoice numbers
                                        - transaction details (amounts, dates)
                                        - sender and receiver information
                                    3) Use db_connector to check if the extracted companies, invoices, or transactions already exist in the local database.
                                    4) Insert any new entities or transactions into the appropriate tables in the local database, ensuring to maintain relationships between entities (e.g., linking invoices to the correct company).
                                    5) Handle any necessary data transformations to fit the canonical schema of the local database
                                  
                                  Schema reference for the local database:
                                  {canonical_desc}
                                  each row have id
                                  if the email don't contain any relevant information or useless information do not store it in the database
                                  and return a message saying that the email was ignored because it did not contain relevant information.
                                   """)
    email_llm = get_helper_llm().bind_tools([db_connector, Retreave_from_email, scan_documents, Retreave_from_google_drive])
    email_tool_map = {
        "db_connector": db_connector,
        "Retreave_from_email": Retreave_from_email,
        "scan_documents": scan_documents,
        "Retreave_from_google_drive": Retreave_from_google_drive
    }
    msg = [system_prompt, HumanMessage(content=state["user_input"])]
    for _iteration in range(100):
        response = email_llm.invoke(msg)
        msg.append(response)
        if not response.tool_calls:
            break
        tool_results = _execute_tool_calls_parallel(response.tool_calls, email_tool_map)
        msg.extend(tool_results)
    else:
        print("WARNING: Email Processing Agent reached maximum tool iterations.")
    print(f"Email Processing Agent completed with response: {response.content} \n \n")
    return state

def remove_duplicates_from_all_tables(db_path: str = None) -> None:
    """Removes duplicate rows across all tables in the SQLite database, keeping the lowest ID."""
    import sqlite3
    if not db_path:
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "ai_audit_db.sqlite")
    
    if not os.path.exists(db_path):
        print("Database does not exist to remove duplicates.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall() if row[0] != "sqlite_sequence"]
    
    total_deleted = 0
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Group by all columns except 'id' to identify exact duplicates
        group_by_cols = [col for col in columns if col != 'id']
        
        if not group_by_cols:
            continue
            
        group_by_clause = ", ".join(f'"{col}"' for col in group_by_cols)
        
        try:
            cursor.execute(f"""
                DELETE FROM {table} 
                WHERE id NOT IN (
                    SELECT MIN(id) 
                    FROM {table} 
                    GROUP BY {group_by_clause}
                )
            """)
            deleted = cursor.rowcount
            if deleted > 0:
                print(f"Removed {deleted} duplicate(s) from table '{table}'.")
                total_deleted += deleted
        except Exception as e:
            print(f"Error removing duplicates from {table}: {e}")
            
    conn.commit()
    conn.close()
    print(f"Total duplicates removed across all tables: {total_deleted}")

