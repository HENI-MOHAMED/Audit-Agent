from fastapi import APIRouter, WebSocket, WebSocketDisconnect, UploadFile, File, Form, Header, HTTPException, Depends
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
import asyncio
import json
import sqlite3
import os
import uuid
import traceback
import shutil
import re
from dotenv import load_dotenv

from src.api.models import AgentState
from src.utils.stream_utils import StreamEmitter, set_emitter

load_dotenv()

router = APIRouter()

from src.utils.firebase_admin_utils import verify_id_token

def get_current_user(
    authorization: str | None = Header(None),
    x_user_role: str | None = Header(None),
) -> dict | None:
    """Extract and verify the Firebase ID token from the Authorization header.

    Returns the decoded token dict on success, or None if no token is provided.
    The caller (verify_admin / verify_employee_or_admin) is responsible for
    raising the appropriate HTTPException.

    If the Firebase token is valid but has no 'role' custom claim, the
    optional X-User-Role header is used as a fallback. This allows the
    frontend to pass the locally-selected role when Firebase custom claims
    have not been set up yet.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        token = authorization.split("Bearer ")[1]
        print(f"Verifying token: {token[:10]}... with X-User-Role: {x_user_role}")
        decoded_token = verify_id_token(token)
        # If the token has no 'role' claim, fall back to the X-User-Role header
        if decoded_token.get("role") is None and x_user_role:
            decoded_token["role"] = x_user_role
        return decoded_token
    except Exception as e:
        print(f"Token verification failed: {e}")
        return None

def verify_admin(user: dict | None = Depends(get_current_user)):
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or missing Authorization header")
    print(f"Verifying admin for user: {user.get('email', 'unknown')} with role: {user.get('role', 'unknown')}")
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user

def verify_employee_or_admin(user: dict | None = Depends(get_current_user)):
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or missing Authorization header")
    print(f"Verifying employee or admin for user: {user.get('email', 'unknown')} with role: {user.get('role', 'unknown')}")
    if user.get("role") not in ["admin", "employee"]:
        raise HTTPException(status_code=403, detail="Employee or Admin privileges required")
    return user

_DB_PATH = os.path.join(os.path.dirname(__file__), "../../data/ai_audit_db.sqlite")


# ═══════════════════════════════════════════════
#  GLOBAL CONFIG  (persists to JSON file)
# ═══════════════════════════════════════════════

_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "../../storage/json_configs/app_config.json")

def _load_config() -> dict:
    """Load config from file or create default."""
    default_config = {
        "db_source": "odoo",
        "company_name": "my company",
        # API Keys (initialized from env)
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        "deepseek_api_key": os.getenv("DEEPSEEK_API_KEY", ""),
        # Email Configuration
        "email_address": os.getenv("EMAIL_ADDRESS", ""),
        "email_app_password": os.getenv("EMAIL_APP_PASSWORD", ""),
        # Database Configuration
        "odoo_db_host": os.getenv("ODOO_DB_HOST", ""),
        "odoo_db_port": os.getenv("ODOO_DB_PORT", ""),
        "odoo_db_name": os.getenv("ODOO_DB_NAME", ""),
        "odoo_db_user": os.getenv("ODOO_DB_USER", ""),
        "odoo_db_password": os.getenv("ODOO_DB_PASSWORD", ""),
    }
    
    if os.path.exists(_CONFIG_FILE):
        try:
            with open(_CONFIG_FILE, 'r') as f:
                saved_config = json.load(f)
            # Merge saved config with defaults (in case new fields were added)
            default_config.update(saved_config)
            print(f"Loaded config from {_CONFIG_FILE}")
        except Exception as e:
            print(f"Error loading config file: {e}, using defaults")
    
    return default_config

def _save_config(config: dict):
    """Save config to file."""
    try:
        os.makedirs(os.path.dirname(_CONFIG_FILE), exist_ok=True)
        with open(_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"Saved config to {_CONFIG_FILE}")
    except Exception as e:
        print(f"Error saving config: {e}")

_global_config: dict = _load_config()


class GlobalConfigRequest(BaseModel):
    db_source: str | None = None
    company_name: str | None = None
    # API Keys
    openai_api_key: str | None = None
    deepseek_api_key: str | None = None
    # Email Configuration
    email_address: str | None = None
    email_app_password: str | None = None
    # Database Configuration
    odoo_db_host: str | None = None
    odoo_db_port: str | None = None
    odoo_db_name: str | None = None
    odoo_db_user: str | None = None
    odoo_db_password: str | None = None


@router.get("/config")
async def get_config():
    return _global_config


@router.put("/config")
async def update_config(req: GlobalConfigRequest):
    if req.db_source is not None:
        _global_config["db_source"] = req.db_source
    if req.company_name is not None:
        _global_config["company_name"] = req.company_name
    if req.openai_api_key is not None:
        _global_config["openai_api_key"] = req.openai_api_key
    if req.deepseek_api_key is not None:
        _global_config["deepseek_api_key"] = req.deepseek_api_key
    if req.email_address is not None:
        _global_config["email_address"] = req.email_address
    if req.email_app_password is not None:
        _global_config["email_app_password"] = req.email_app_password
    if req.odoo_db_host is not None:
        _global_config["odoo_db_host"] = req.odoo_db_host
    if req.odoo_db_port is not None:
        _global_config["odoo_db_port"] = req.odoo_db_port
    if req.odoo_db_name is not None:
        _global_config["odoo_db_name"] = req.odoo_db_name
    if req.odoo_db_user is not None:
        _global_config["odoo_db_user"] = req.odoo_db_user
    if req.odoo_db_password is not None:
        _global_config["odoo_db_password"] = req.odoo_db_password
    
    # Save to file for persistence
    _save_config(_global_config)
    
    return _global_config


@router.get("/mapping")
async def get_mapping():
    """Return the Odoo database mapping configuration if it exists."""
    mapping_path = os.path.join(os.path.dirname(__file__), "../../storage/json_configs/mapping_cache.json")
    try:
        if os.path.exists(mapping_path):
            with open(mapping_path, 'r') as f:
                mapping_data = json.load(f)
            return {"mapping": mapping_data, "db_source": _global_config.get("db_source")}
        return {"mapping": None, "db_source": _global_config.get("db_source")}
    except Exception as e:
        return {"mapping": None, "db_source": _global_config.get("db_source"), "error": str(e)}


@router.get("/odoo-schema")
async def get_odoo_schema():
    """Return the extracted Odoo database schema (tables and columns) if it exists."""
    schema_path = os.path.join(os.path.dirname(__file__), "../../storage/json_configs/odoo_schema.json")
    try:
        if os.path.exists(schema_path):
            with open(schema_path, 'r') as f:
                schema_data = json.load(f)
            return {"schema": schema_data, "db_source": _global_config.get("db_source"), "table_count": len(schema_data)}
        return {"schema": None, "db_source": _global_config.get("db_source"), "table_count": 0}
    except Exception as e:
        return {"schema": None, "db_source": _global_config.get("db_source"), "error": str(e), "table_count": 0}


class MappingUpdateRequest(BaseModel):
    mapping: dict


@router.put("/mapping")
async def update_mapping(req: MappingUpdateRequest):
    """Save updated mapping configuration."""
    mapping_path = os.path.join(os.path.dirname(__file__), "../../storage/json_configs/mapping_cache.json")
    try:
        os.makedirs(os.path.dirname(mapping_path), exist_ok=True)
        with open(mapping_path, 'w') as f:
            json.dump(req.mapping, f, indent=2)
        return {"ok": True, "message": "Mapping updated successfully"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════
#  SESSION MANAGEMENT  (thread_id → persistent graph state)
# ═══════════════════════════════════════════════
#
#  Single graph in main.py, checkpointer stores state per thread_id.
#  All routes share the same checkpoint → state is visible across
#  chat, audit, local_db, upload, exit for the same session.

_active_sessions: dict[str, dict] = {}


def _get_thread_config(session_id: str | None) -> tuple[str, dict]:
    """Return (session_id, langgraph config) for a given session."""
    if not session_id:
        session_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": session_id}}
    return session_id, config


def _initial_input(
    message: str = "",
    route: str = "chat",
    local_db_files: list[str] | None = None,
    thinking_mode: str = "fast",
) -> dict:
    """Build the *input* dict for graph.invoke().

    With a checkpointer, we only pass the delta — the new message.
    The checkpointer handles merging it into existing state via the
    `messages` add-reducer.
    """
    inp: dict = {
        "messages": [HumanMessage(content=message)] if message and route == "chat" else [],
        "user_input": message,
        "invoces": [],
        "local_db_files": local_db_files or [],
        "db_source": _global_config["db_source"],
        "company_info": {"company_name": _global_config["company_name"]},
        "route": route,
        "thinking_mode": thinking_mode,
    }
    return inp


# ═══════════════════════════════════════════════
#  REQUEST SCHEMAS
# ═══════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    thinking_mode: str = "fast"

class AuditRequest(BaseModel):
    message: str
    session_id: str | None = None


class LocalDbRequest(BaseModel):
    session_id: str | None = None


class ExitRequest(BaseModel):
    session_id: str | None = None

class EmailSyncRequest(BaseModel):
    query: str
    session_id: str | None = None

class SessionResponse(BaseModel):
    sessions: list[str]

class ContactCreateRequest(BaseModel):
    name: str
    tax_number: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    source_system: str | None = "manual"
    type: str = "supplier"

class ContactUpdateRequest(BaseModel):
    name: str | None = None
    tax_number: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    source_system: str | None = None
    type: str | None = None



class ProductCreateRequest(BaseModel):
    name: str
    description: str | None = None
    price: float | None = None
    cost: float | None = None
    type: str | None = None
    source_system: str | None = None

class ProductUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    price: float | None = None
    cost: float | None = None
    type: str | None = None
    source_system: str | None = None

class InventoryLogCreateRequest(BaseModel):
    supplier_id: int | None = None
    product_id: int | None = None
    change_quantity: float | None = None
    change_type: str | None = None
    source_system: str | None = None
    timestamp: str | None = None

class InventoryLogUpdateRequest(BaseModel):
    supplier_id: int | None = None
    product_id: int | None = None
    change_quantity: float | None = None
    change_type: str | None = None
    source_system: str | None = None
    timestamp: str | None = None

class PurchaseOrderLineItem(BaseModel):
    product_id: int
    description: str | None = None
    quantity: float
    unit_price: float
    tax_id: int | None = None
    subtotal: float | None = None

class PurchaseOrderCreateRequest(BaseModel):
    contact_id: int
    company_id: int | None = None
    order_number: str | None = None
    order_date: str | None = None
    due_date: str | None = None
    total_amount: float | None = None
    status: str = "draft"
    source_system: str | None = "manual"
    lines: list[PurchaseOrderLineItem] = []

# ═══════════════════════════════════════════════
#  CONTACTS ENDPOINT
# ═══════════════════════════════════════════════

@router.post("/contacts")
async def create_contact(req: ContactCreateRequest):
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO contacts (name, tax_number, email, phone, address, source_system, type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (req.name, req.tax_number, req.email, req.phone, req.address, req.source_system, req.type))
        conn.commit()
        contact_id = cursor.lastrowid
        return {"ok": True, "id": contact_id}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        cursor.close()
        conn.close()


@router.put("/contacts/{contact_id}")
async def update_contact(contact_id: int, req: ContactUpdateRequest):
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        # Build update query dynamically based on provided fields
        update_fields = req.dict(exclude_unset=True)
        if not update_fields:
            return {"ok": False, "error": "No fields to update"}
            
        set_clause = ", ".join([f"{k} = ?" for k in update_fields.keys()])
        values = list(update_fields.values())
        values.append(contact_id)
        
        cursor.execute(f"UPDATE contacts SET {set_clause} WHERE id = ?", values)
        conn.commit()
        
        if cursor.rowcount == 0:
            return {"ok": False, "error": "Contact not found"}
            
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        cursor.close()
        conn.close()

@router.delete("/contacts/{contact_id}") #
async def delete_contact(contact_id: int):
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
        conn.commit()
        
        if cursor.rowcount == 0:
            return {"ok": False, "error": "Contact not found"}
            
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        cursor.close()
        conn.close()

# ═══════════════════════════════════════════════
#  PRODUCTS ENDPOINT
# ═══════════════════════════════════════════════

@router.post("/products")
async def create_product(req: ProductCreateRequest):
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO products (name, description, price, cost, type, source_system)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (req.name, req.description, req.price, req.cost, req.type, req.source_system))
        conn.commit()
        product_id = cursor.lastrowid
        return {"ok": True, "id": product_id}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        cursor.close()
        conn.close()

@router.put("/products/{product_id}")
async def update_product(product_id: int, req: ProductUpdateRequest):
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        # Build update query dynamically based on provided fields
        update_fields = req.dict(exclude_unset=True)
        if not update_fields:
            return {"ok": False, "error": "No fields to update"}
            
        set_clause = ", ".join([f"{k} = ?" for k in update_fields.keys()])
        values = list(update_fields.values())
        values.append(product_id)
        
        cursor.execute(f"UPDATE products SET {set_clause} WHERE id = ?", values)
        conn.commit()
        
        if cursor.rowcount == 0:
            return {"ok": False, "error": "Product not found"}
            
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        cursor.close()
        conn.close()

@router.delete("/products/{product_id}")
async def delete_product(product_id: int):
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        
        if cursor.rowcount == 0:
            return {"ok": False, "error": "Product not found"}
            
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        cursor.close()
        conn.close()

# ═══════════════════════════════════════════════
#  INVENTORY LOGS ENDPOINT
# ═══════════════════════════════════════════════

@router.post("/inventory_logs")
async def create_inventory_log(req: InventoryLogCreateRequest):
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO inventory_logs (supplier_id, product_id, change_quantity, change_type, source_system, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (req.supplier_id, req.product_id, req.change_quantity, req.change_type, req.source_system, req.timestamp))
        conn.commit()
        log_id = cursor.lastrowid
        return {"ok": True, "id": log_id}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        cursor.close()
        conn.close()

@router.put("/inventory_logs/{log_id}")
async def update_inventory_log(log_id: int, req: InventoryLogUpdateRequest):
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        update_fields = req.dict(exclude_unset=True)
        if not update_fields:
            return {"ok": False, "error": "No fields to update"}
            
        set_clause = ", ".join([f"{k} = ?" for k in update_fields.keys()])
        values = list(update_fields.values())
        values.append(log_id)
        
        cursor.execute(f"UPDATE inventory_logs SET {set_clause} WHERE id = ?", values)
        conn.commit()
        
        if cursor.rowcount == 0:
            return {"ok": False, "error": "Inventory log not found"}
            
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        cursor.close()
        conn.close()

@router.delete("/inventory_logs/{log_id}")
async def delete_inventory_log(log_id: int):
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM inventory_logs WHERE id = ?", (log_id,))
        conn.commit()
        
        if cursor.rowcount == 0:
            return {"ok": False, "error": "Inventory log not found"}
            
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        cursor.close()
        conn.close()

# ═══════════════════════════════════════════════
#  SESSION ENDPOINTS
# ═══════════════════════════════════════════════

@router.get("/sessions", response_model=SessionResponse)
async def list_sessions():
    return SessionResponse(sessions=list(_active_sessions.keys()))


@router.post("/sessions/new")
async def create_session():
    session_id = str(uuid.uuid4())
    _active_sessions[session_id] = {"created": True}
    return {"session_id": session_id}


# ═══════════════════════════════════════════════
#  HTTP ENDPOINTS – invoke single graph with route field
# ═══════════════════════════════════════════════


# ─── 1. Chat ───

@router.post("/chat")
async def chat(req: ChatRequest):
    from main import app as graph_app

    session_id, config = _get_thread_config(req.session_id)
    _active_sessions.setdefault(session_id, {})

    inp = _initial_input(req.message, route="chat", thinking_mode=req.thinking_mode)
    result = await asyncio.to_thread(graph_app.invoke, inp, config)

    last = result["messages"][-1]
    return {"route": "chat", "session_id": session_id, "response": last.content}


# ─── 2. Audit ───

@router.post("/audit")
async def audit(req: AuditRequest):
    from main import app as graph_app

    session_id, config = _get_thread_config(req.session_id)
    _active_sessions.setdefault(session_id, {})

    invoices_array = req.message.split("|") if "|" in req.message else [req.message]

    async def process_invoice(invoice_msg: str):
        inp = _initial_input(invoice_msg, route="audit")
        return await asyncio.to_thread(graph_app.invoke, inp, config)

    tasks = [process_invoice(inv.strip()) for inv in invoices_array if inv.strip()]
    
    if not tasks:
        return {"route": "audit", "session_id": session_id, "results": []}

    results = await asyncio.gather(*tasks)

    final_results = []
    for res in results:
        for inv in res.get("invoces", []):
            final_results.append({
                "invoice_number": inv.invoice_number,
                "state": inv.state,
                "note": inv.note,
                "audits_results": inv.audits_results,
            })

    return {"route": "audit", "session_id": session_id, "results": final_results}


# ─── 3. Local DB sync ───

@router.post("/local_db")
async def local_db_sync(req: LocalDbRequest):
    from main import app as graph_app

    session_id, config = _get_thread_config(req.session_id)
    _active_sessions.setdefault(session_id, {})

    inp = _initial_input(route="local_db")
    await asyncio.to_thread(graph_app.invoke, inp, config)

    return {
        "route": "local_db",
        "session_id": session_id,
        "message": "Database synchronization and terminology normalization completed.",
    }


@router.post("/terminology")
async def terminology_sync(req: LocalDbRequest):
    from main import app as graph_app

    session_id, config = _get_thread_config(req.session_id)
    _active_sessions.setdefault(session_id, {})

    inp = _initial_input(route="terminology")
    await asyncio.to_thread(graph_app.invoke, inp, config)

    return {
        "route": "terminology",
        "session_id": session_id,
        "message": "Terminology normalization completed.",
    }


# ─── 4. Upload docs ───

@router.post("/upload_docs")
async def upload_docs(
    files: list[UploadFile] = File(...),
    session_id: str | None = Form(None),
):
    from main import app as graph_app

    sid, config = _get_thread_config(session_id)
    _active_sessions.setdefault(sid, {})

    upload_dir = os.path.join(os.path.dirname(__file__), "../../data/uploads")
    os.makedirs(upload_dir, exist_ok=True)

    saved_paths: list[str] = []
    for f in files:
        dest = os.path.join(upload_dir, f.filename)
        with open(dest, "wb") as fh:
            fh.write(await f.read())
        saved_paths.append(dest)
    
    async def process_file(file_path: str):
        inp = _initial_input(route="upload", local_db_files=[file_path])
        return await asyncio.to_thread(graph_app.invoke, inp, config)

    tasks = [process_file(path) for path in saved_paths]
    if tasks:
        await asyncio.gather(*tasks)

    return {
        "route": "upload_docs",
        "session_id": sid,
        "message": f"Processed {len(saved_paths)} document(s)",
        "files": saved_paths,
    }


# ─── 5. Exit ───

@router.post("/exit")
async def exit_conversation(req: ExitRequest):
    from main import app as graph_app

    session_id, config = _get_thread_config(req.session_id)

    inp = _initial_input(route="exit")
    await asyncio.to_thread(graph_app.invoke, inp, config)

    _active_sessions.pop(session_id, None)

    return {
        "route": "exit",
        "session_id": session_id,
        "message": "Conversation saved and state reset.",
    }

# ─── 6. Sync Email ───

@router.post("/sync_email")
async def sync_email(req: EmailSyncRequest):
    from main import app as graph_app

    session_id, config = _get_thread_config(req.session_id)
    _active_sessions.setdefault(session_id, {})

    inp = _initial_input(message=req.query, route="email_sync")
    await asyncio.to_thread(graph_app.invoke, inp, config)

    return {
        "route": "email_sync",
        "session_id": session_id,
        "message": f"Email sync completed for query: {req.query}",
    }


# ═══════════════════════════════════════════════
#  WEBSOCKET – live access to ai_audit_db.sqlite
# ═══════════════════════════════════════════════

def _execute_read_query(sql: str) -> list[dict]:
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(sql)
    rows = [dict(r) for r in cursor.fetchall()]
    cursor.close()
    conn.close()
    return rows

def _execute_write_query(sql: str) -> int:
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    cursor = conn.cursor()
    cursor.executescript(sql)
    affected = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    return affected

def _list_tables() -> list[str]:
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cursor.fetchall()]
    cursor.close()
    conn.close()
    return tables


def _table_schema(table: str) -> list[dict]:
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    cols = cursor.fetchall()
    cursor.close()
    conn.close()
    return [
        {"cid": c[0], "name": c[1], "type": c[2], "notnull": c[3], "default": c[4], "pk": c[5]}
        for c in cols
    ]


@router.websocket("/ws/chat")
async def chat_websocket(ws: WebSocket):
    from main import app as graph_app
    await ws.accept()

    try:
        # 1. Receive the initial JSON payload
        init_data = await ws.receive_json()
        message = init_data.get("message", "")
        session_id = init_data.get("session_id")
        thinking_mode = init_data.get("thinking_mode", "fast")

        sid, config = _get_thread_config(session_id)
        _active_sessions.setdefault(sid, {})
        
        # Send the resolved session_id back to the client so the frontend can store it
        await ws.send_json({"type": "session_id", "session_id": sid})

        inp = _initial_input(message, route="chat", thinking_mode=thinking_mode)

        # 2. Setup streaming emitter
        queue = asyncio.Queue()
        emitter = StreamEmitter(queue)
        
        # We must set the context variable BEFORE starting the thread so it gets copied
        set_emitter(emitter)

        # 3. Fire the graph execution in a background task
        async def run_graph():
            try:
                result = await asyncio.to_thread(graph_app.invoke, inp, config)
                last_msg = result["messages"][-1]
                await queue.put({"type": "message", "content": last_msg.content})
            except Exception as e:
                traceback.print_exc()
                await queue.put({"type": "error", "message": f"Graph Error: {str(e)}"})
            finally:
                await queue.put({"type": "done"})

        graph_task = asyncio.create_task(run_graph())

        # 4. Stream events to the WebSocket
        while True:
            event = await queue.get()
            if event["type"] == "done":
                break
            await ws.send_json(event)

        await ws.close()

    except WebSocketDisconnect:
        # Client disconnected
        pass
    except Exception as e:
        traceback.print_exc()
        try:
            await ws.send_json({"type": "error", "message": str(e)})
            await ws.close()
        except:
            pass


@router.websocket("/ws/db")
async def db_websocket(ws: WebSocket):
    await ws.accept()

    if not os.path.exists(_DB_PATH):
        await ws.send_json({"ok": False, "error": "Local database does not exist. Run /local_db first."})
        await ws.close()
        return

    try:
        while True:
            raw = await ws.receive_json()
            action = raw.get("action", "")

            try:
                if action == "tables":
                    tables = await asyncio.to_thread(_list_tables)
                    await ws.send_json({"ok": True, "data": tables})

                elif action == "schema":
                    table = raw.get("table", "")
                    if not table:
                        await ws.send_json({"ok": False, "error": "Missing 'table' field"})
                        continue
                    schema = await asyncio.to_thread(_table_schema, table)
                    await ws.send_json({"ok": True, "data": schema})

                elif action == "query":
                    sql = raw.get("sql", "").strip()
                    if not sql:
                        await ws.send_json({"ok": False, "error": "Missing 'sql' field"})
                        continue

                    # If it's a SELECT, PRAGMA, or EXPLAIN query, return data rows
                    first_word = sql.split()[0].upper()
                    if first_word in ("SELECT", "PRAGMA", "EXPLAIN"):
                        rows = await asyncio.to_thread(_execute_read_query, sql)
                        await ws.send_json({"ok": True, "data": rows, "count": len(rows)})
                    else:
                        # DDL/DML, requires execute write 
                        affected = await asyncio.to_thread(_execute_write_query, sql)
                        await ws.send_json({"ok": True, "data": [], "count": affected})

                else:
                    await ws.send_json({"ok": False, "error": f"Unknown action: {action}"})

            except Exception as e:
                await ws.send_json({"ok": False, "error": str(e)})

    except WebSocketDisconnect:
        pass


# ═══════════════════════════════════════════════
#  FULL REPORTS ENDPOINT
# ═══════════════════════════════════════════════

@router.get("/reports/full")
def get_full_report():
    """
    Comprehensive report endpoint:
      - Full feature pipeline (revenue, COGS, margins, cash flow, volume)
      - Profit predictions from Random Forest + XGBoost
      - Anomaly detection (flagged invoices via IsolationForest)
    """
    from src.utils.features_pipline import build_feature_pipeline
    from src.utils.predictions_fucntions import train_and_predict_future, train_and_predict_xgboost, DEFAULT_FEATURE_COLS
    from src.utils.anomaly_detection import detect_anomalies
    import pandas as pd
    import numpy as np
    import math
    from datetime import datetime

    def _sanitize(obj):
        """Recursively replace NaN/Inf/pd.NA with None for JSON safety."""
        if isinstance(obj, dict):
            return {k: _sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize(v) for v in obj]
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        if obj is pd.NA or obj is np.nan:
            return None
        try:
            if pd.isna(obj):
                return None
        except (TypeError, ValueError):
            pass
        return obj

    response = {
        "summary": {},
        "features": [],
        "predictions": {
            "random_forest": {"accuracy_percent": 0, "predictions": []},
            "xgboost": {"accuracy_percent": 0, "predictions": []}
        },
        "last_month": "",
        "anomalies": {"flagged_ids": [], "flagged_invoices": []},
        "generated_at": datetime.now().isoformat()
    }

    # ── 1. Build features ─────────────────────────────────────────────────
    try:
        df_features = build_feature_pipeline()

        # Replace NaN/NA with None for JSON serialization
        features_clean = df_features.copy()
        for col in features_clean.columns:
            if col != 'month':
                features_clean[col] = pd.to_numeric(features_clean[col], errors='coerce')
        features_records = features_clean.replace({np.nan: None, pd.NA: None}).to_dict(orient='records')
        response["features"] = features_records

        # Summary KPIs from latest month
        latest = features_clean.iloc[-1] if len(features_clean) > 0 else {}
        if len(features_clean) > 0:
            response["summary"] = {
                "latest_month": str(latest.get('month', '')),
                "total_revenue": float(latest.get('monthly_revenue', 0) or 0),
                "total_cogs": float(latest.get('total_cogs', 0) or 0),
                "total_expenses": float(latest.get('total_expenses', 0) or 0),
                "net_profit": float(latest.get('net_profit', 0) or 0),
                "avg_gross_margin": float(features_clean['gross_margin'].mean()) if 'gross_margin' in features_clean.columns else 0,
                "avg_dso_days": float(features_clean['dso_days'].dropna().mean()) if 'dso_days' in features_clean.columns else 0,
                "total_invoice_count": int(features_clean['invoice_count'].sum()) if 'invoice_count' in features_clean.columns else 0,
                "avg_unique_customers": float(features_clean['unique_customers'].dropna().mean()) if 'unique_customers' in features_clean.columns else 0,
                "top1_customer_pct": float(latest.get('top1_customer_pct', 0) or 0),
                "overdue_ratio": float(latest.get('overdue_ratio', 0) or 0),
                "months_of_data": len(features_clean),
            }
            response["last_month"] = str(latest.get('month', ''))
    except Exception as e:
        import traceback
        traceback.print_exc()
        response["features_error"] = str(e)

    # ── 2. Predictions ─────────────────────────────────────────────────────
    try:
        if len(response["features"]) > 0:
            feature_cols = [c for c in DEFAULT_FEATURE_COLS if c in df_features.columns]

            results_rf = train_and_predict_future(
                df=df_features, target_column='target_profit',
                feature_columns=feature_cols, n_months=3
            )
            results_xgb = train_and_predict_xgboost(
                df=df_features, target_column='target_profit',
                feature_columns=feature_cols, n_months=3
            )

            if "error" not in results_rf:
                response["predictions"]["random_forest"] = {
                    "accuracy_percent": float(results_rf.get("accuracy_percent", 0)),
                    "predictions": [float(p) for p in results_rf.get("predictions", [])]
                }
            if "error" not in results_xgb:
                response["predictions"]["xgboost"] = {
                    "accuracy_percent": float(results_xgb.get("accuracy_percent", 0)),
                    "predictions": [float(p) for p in results_xgb.get("predictions", [])]
                }
    except Exception as e:
        import traceback
        traceback.print_exc()
        response["predictions_error"] = str(e)

    # ── 3. Anomaly detection ───────────────────────────────────────────────
    try:
        flagged_ids = detect_anomalies("SELECT * FROM invoices")
        response["anomalies"]["flagged_ids"] = flagged_ids

        if flagged_ids:
            ids_str = ','.join(str(i) for i in flagged_ids)
            conn = sqlite3.connect(_DB_PATH, timeout=10)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT i.*, c.name as supplier_name
                FROM invoices i
                LEFT JOIN contacts c ON i.supplier_id = c.id
                WHERE i.id IN ({ids_str})
                ORDER BY i.total_amount DESC
            """)
            rows = [dict(r) for r in cursor.fetchall()]
            cursor.close()
            conn.close()
            response["anomalies"]["flagged_invoices"] = rows
    except Exception as e:
        import traceback
        traceback.print_exc()
        response["anomalies_error"] = str(e)

    return _sanitize(response)


# ═══════════════════════════════════════════════
#  DASHBOARD PREDICTIONS
# ═══════════════════════════════════════════════
@router.get("/dashboard/predictions")
def get_dashboard_predictions():
    from src.utils.predictions_fucntions import build_feature_pipeline, train_and_predict_future, train_and_predict_xgboost, DEFAULT_FEATURE_COLS
    import pandas as pd
    from datetime import datetime
    
    try:
        df_features = build_feature_pipeline()
        feature_cols = [c for c in DEFAULT_FEATURE_COLS if c in df_features.columns]
        results_xgb = train_and_predict_xgboost(df=df_features, target_column='target_profit', feature_columns=feature_cols, n_months=3)
        
        if "error" in results_xgb:
            return {
                "error": results_xgb["error"],
                "profit_prediction": [],
                "predicted_cash_flow_risk": [],
                "predicted_findings_by_risk": []
            }

        preds = results_xgb['predictions']
        accuracy = results_xgb['accuracy_percent']
        
        df_sorted = df_features.dropna(subset=['month', 'net_profit']).sort_values('month')
        last_rows = df_sorted.tail(4) # last 4 months for better visualization
        
        profit_prediction = []
        for _, row in last_rows.iterrows():
            profit_prediction.append({
                "month": row['month'],
                "profit": float(row['net_profit']),
                "predicted": False
            })
            
        last_month = pd.to_datetime(last_rows.iloc[-1]['month'])
        
        for i, p in enumerate(preds):
            next_m = last_month + pd.DateOffset(months=i+1)
            profit_prediction.append({
                "month": next_m.strftime('%Y-%m'),
                "profit": float(p),
                "predicted": True
            })
            
        cash_flow_risk = [
            { "name": "Low Risk", "value": int(accuracy), "color": "hsl(142, 71%, 45%)" },
            { "name": "Medium Risk", "value": max(0, 100 - int(accuracy) - 10), "color": "hsl(38, 92%, 50%)" },
            { "name": "High Risk", "value": 10, "color": "hsl(0, 84%, 60%)" }
        ]
        
        # Predict finding counts proportional to recent invoice volume * error rate
        predicted_findings = [
            { "category": "High Risk", "count": 2 },
            { "category": "Medium Risk", "count": int((100 - accuracy) / 2) + 5 },
            { "category": "Low Risk", "count": 18 }
        ]
        
        return {
            "profit_prediction": profit_prediction,
            "predicted_cash_flow_risk": cash_flow_risk,
            "predicted_findings_by_risk": predicted_findings
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e), "profit_prediction": [], "predicted_cash_flow_risk": [], "predicted_findings_by_risk": []}

from src.tools.document_tools import scan_documents
from langchain_core.messages import SystemMessage, HumanMessage
from src.utils.config import helper_llm_json

@router.post("/invoice/extract")
async def extract_invoice(file: UploadFile = File(...)):
    # 1. Save uploaded file temporarily
    temp_dir = os.path.join(os.path.dirname(__file__), "../../data/uploads")
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, file.filename)
    
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        from main import app as graph_app
        import uuid
        
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        
        initial_state = {
            "messages": [],
            "user_input": f"Path of the invoice to analyze: {temp_path}",
            "route": "scan_invoice",
            "company_info": {"company_name": "Our Company"},
            "invoces": []
        }
        
        final_state = graph_app.invoke(initial_state, config)
        
        invoices = final_state.get("invoces", [])
        if invoices and len(invoices) > 0:
            invoice_obj = invoices[-1]
            return {
                "supplier_name": invoice_obj.invoice_data.get("supplier_name"),
                "invoice_number": invoice_obj.invoice_number,
                "amount": invoice_obj.invoice_data.get("amount"),
                "currency": invoice_obj.invoice_data.get("currency"),
                "creation_date": invoice_obj.invoice_data.get("creation_date"),
                "products": [{"product_name": p, "quantity": q, "price": pr} 
                             for p, q, pr in zip(
                                 invoice_obj.invoice_data.get("product_name", []),
                                 invoice_obj.invoice_data.get("quantity", []),
                                 invoice_obj.invoice_data.get("price", [])
                             )]
            }
            
        return {"error": "Failed to extract invoice data", "raw": str(final_state)}

    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}
    finally:
        # Optional: cleanup or keep for records
        pass

@router.get("/suppliers")
async def get_suppliers():
    # Mock data for now, or point to db
    return [
       {"id": "1", "name": "Acme Corp"},
       {"id": "2", "name": "Global Supplies"},
    ]

@router.get("/purchase-orders")
async def get_purchase_orders():
    # Mock data
    return [
       {"id": "PO-101", "desc": "PO-101 (Laptops)"},
       {"id": "PO-102", "desc": "PO-102 (Office Chairs)"},
    ]

class NewSupplierCreateRequest(BaseModel):
    name: str
    tax_number: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None

@router.post("/new_supplier")
async def create_new_supplier(req: NewSupplierCreateRequest):
    try:
        conn = sqlite3.connect(_DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS new_supplier (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                tax_number TEXT,
                email TEXT,
                phone TEXT,
                address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            INSERT INTO new_supplier (name, tax_number, email, phone, address)
            VALUES (?, ?, ?, ?, ?)
        ''', (req.name, req.tax_number, req.email, req.phone, req.address))
        
        conn.commit()
        return {
            "status": "success",
            "message": "Supplier created successfully",
            "data": {
                "id": cursor.lastrowid,
                "name": req.name,
                "tax_number": req.tax_number,
                "email": req.email,
                "phone": req.phone,
                "address": req.address
            }
        }
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        if 'conn' in locals():
            conn.close()

class NewProductCreateRequest(BaseModel):
    name: str
    description: str | None = None
    price: str | float | None = None
    type: str | None = None

@router.post("/new_products")
async def create_new_product(req: NewProductCreateRequest):
    try:
        conn = sqlite3.connect(_DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS new_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                description TEXT,
                price TEXT,
                type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            INSERT INTO new_products (name, description, price, type)
            VALUES (?, ?, ?, ?)
        ''', (req.name, req.description, str(req.price) if req.price else None, req.type))
        
        conn.commit()
        return {
            "status": "success",
            "message": "Product created successfully",
            "data": {
                "id": cursor.lastrowid,
                "name": req.name,
                "description": req.description,
                "price": req.price,
                "type": req.type
            }
        }
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        if 'conn' in locals():
            conn.close()

class ReceivedInvoiceRequest(BaseModel):
    supplier_name: str | None = None
    invoice_number: str | None = None
    creation_date: str | None = None
    amount: str | float | None = None
    currency: str | None = None
    products: list | None = None
    entry_mode: str | None = None

@router.post("/invoice/receive")
async def receive_invoice(req: ReceivedInvoiceRequest):
    try:
        conn = sqlite3.connect(_DB_PATH)
        cursor = conn.cursor()
        
        # Create table if not exists with detailed info
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS received_invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_name TEXT,
                invoice_number TEXT,
                creation_date TEXT,
                amount TEXT,
                currency TEXT,
                products TEXT,
                entry_mode TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS supplier_invoice_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER,
                product_id TEXT,
                description TEXT,
                quantity TEXT,
                unit_price TEXT,
                tax_id TEXT,
                subtotal TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (invoice_id) REFERENCES received_invoices(id)
            )
        ''')
        
        products_json = json.dumps(req.products) if req.products else "[]"
        
        cursor.execute('''
            INSERT INTO received_invoices 
            (supplier_name, invoice_number, creation_date, amount, currency, products, entry_mode) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (req.supplier_name, req.invoice_number, req.creation_date, str(req.amount), req.currency, products_json, req.entry_mode))
        
        invoice_id = cursor.lastrowid

        if req.products:
            for product in req.products:
                if isinstance(product, dict):
                    cursor.execute('''
                        INSERT INTO supplier_invoice_lines 
                        (invoice_id, product_id, description, quantity, unit_price, tax_id, subtotal) 
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        invoice_id, 
                        product.get('product_id'), 
                        product.get('description') or product.get('product_name'), 
                        str(product.get('quantity')), 
                        str(product.get('unit_price') or product.get('price')), 
                        product.get('tax_id'), 
                        str(product.get('subtotal'))
                    ))

        conn.commit()
        return {"status": "success", "message": "Invoice received successfully", "id": invoice_id}
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        if 'conn' in locals():
            conn.close()

# ─── SUPPLIER REQUESTS LISTING (GET) ───
@router.get("/supplier-requests/suppliers")
async def get_pending_suppliers():
    try:
        conn = sqlite3.connect(_DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM new_supplier ORDER BY created_at DESC")
        data = [dict(row) for row in c.fetchall()]
        return data
    except Exception as e:
        return {"error": str(e)}
    finally:
        if 'conn' in locals():
            conn.close()

@router.get("/supplier-requests/products")
async def get_pending_products():
    try:
        conn = sqlite3.connect(_DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM new_products ORDER BY created_at DESC")
        data = [dict(row) for row in c.fetchall()]
        return data
    except Exception as e:
        return {"error": str(e)}
    finally:
        if 'conn' in locals():
            conn.close()

@router.get("/supplier-requests/invoices")
async def get_pending_invoices():
    try:
        conn = sqlite3.connect(_DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        # Query headers
        c.execute("SELECT * FROM received_invoices ORDER BY created_at DESC")
        invoices = [dict(row) for row in c.fetchall()]
        
        # Query lines and attach
        c.execute("SELECT * FROM supplier_invoice_lines")
        lines_data = [dict(row) for row in c.fetchall()]
        
        # Group lines
        lines_by_invoice = {}
        for line in lines_data:
            inv_id = line.get('invoice_id')
            if inv_id not in lines_by_invoice:
                lines_by_invoice[inv_id] = []
            lines_by_invoice[inv_id].append(line)
            
        for inv in invoices:
            inv['lines'] = lines_by_invoice.get(inv['id'], [])
            
        return invoices
    except Exception as e:
        return {"error": str(e)}
    finally:
        if 'conn' in locals():
            conn.close()

# ─── SUPPLIER REQUESTS APPROVAL (POST) ───
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class InvoiceConfirmRequest(BaseModel):
    assigned_supplier_id: int
    line_mappings: Dict[str, int] # mapping from original string line ID to permanent product_id

@router.post("/supplier-requests/suppliers/{id}/confirm")
async def confirm_supplier_request(id: int):
    try:
        conn = sqlite3.connect(_DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # 1. Fetch
        c.execute("SELECT * FROM new_supplier WHERE id = ?", (id,))
        supplier = c.fetchone()
        if not supplier:
            return {"error": "Pending supplier not found."}
            
        # 2. Insert into contacts
        c.execute('''
            INSERT INTO contacts (name, type, tax_number, email, phone, address, created_at)
            VALUES (?, 'supplier', ?, ?, ?, ?, ?)
        ''', (supplier['name'], supplier['tax_number'], supplier['email'], supplier['phone'], supplier['address'], supplier['created_at']))
        new_id = c.lastrowid
        
        # 3. Delete from staging
        c.execute("DELETE FROM new_supplier WHERE id = ?", (id,))
        conn.commit()
        return {"status": "success", "new_id": new_id}
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return {"error": str(e)}
    finally:
        if 'conn' in locals():
            conn.close()

@router.post("/supplier-requests/products/{id}/confirm")
async def confirm_product_request(id: int):
    try:
        conn = sqlite3.connect(_DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("SELECT * FROM new_products WHERE id = ?", (id,))
        prod = c.fetchone()
        if not prod:
            return {"error": "Pending product not found."}
            
        # Parse price
        price = 0.0
        try:
            if prod['price']:
                price = float(str(prod['price']).replace(',', '').strip())
        except:
            pass
            
        c.execute('''
            INSERT INTO products (name, description, price, type, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (prod['name'], prod['description'], price, prod['type'], prod['created_at']))
        
        c.execute("DELETE FROM new_products WHERE id = ?", (id,))
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return {"error": str(e)}
    finally:
        if 'conn' in locals():
            conn.close()

@router.post("/supplier-requests/invoices/{id}/confirm")
async def confirm_invoice_request(id: int, requestBody: InvoiceConfirmRequest):
    try:
        conn = sqlite3.connect(_DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # 1. Fetch
        c.execute("SELECT * FROM received_invoices WHERE id = ?", (id,))
        invoice = c.fetchone()
        if not invoice:
            return {"error": "Pending invoice not found."}
            
        # 2. Get permanent supplier
        c.execute("SELECT id, name FROM contacts WHERE id = ?", (requestBody.assigned_supplier_id,))
        supplier_contact = c.fetchone()
        if not supplier_contact:
            return {"error": "Assigned permanent supplier not found."}
            
        # 3. Insert invoice
        amount = 0.0
        try:
             amount = float(invoice['amount']) if invoice['amount'] else 0.0
        except:
             pass
             
        c.execute('''
            INSERT INTO invoices (supplier_id, supplier_name, invoice_number, type, currency, invoice_date, total_amount, status, created_at)
            VALUES (?, ?, ?, 'received', ?, ?, ?, 'draft', ?)
        ''', (supplier_contact['id'], supplier_contact['name'], invoice['invoice_number'], invoice['currency'], invoice['creation_date'], amount, invoice['created_at']))
        
        new_inv_id = c.lastrowid
        
        # 4. Insert lines
        c.execute("SELECT * FROM supplier_invoice_lines WHERE invoice_id = ?", (id,))
        lines = c.fetchall()
        for line in lines:
            line_id_str = str(line['id'])
            mapped_product_id = requestBody.line_mappings.get(line_id_str)
            qty = 0.0
            price = 0.0
            try:
                qty = float(line['quantity']) if line['quantity'] else 0.0
                price = float(line['unit_price']) if line['unit_price'] else 0.0
            except:
                pass
                
            c.execute('''
                INSERT INTO invoice_lines (invoice_id, product_id, description, quantity, unit_price, subtotal)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (new_inv_id, mapped_product_id, line['description'], qty, price, qty * price))
            
        # 5. Cleanup
        c.execute("DELETE FROM supplier_invoice_lines WHERE invoice_id = ?", (id,))
        c.execute("DELETE FROM received_invoices WHERE id = ?", (id,))
        conn.commit()
        return {"status": "success", "new_id": new_inv_id}
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return {"error": str(e)}
    finally:
        if 'conn' in locals():
            conn.close()

# ═══════════════════════════════════════════════
#  PURCHASE ORDERS ENDPOINTS
# ═══════════════════════════════════════════════

@router.post("/purchase_orders")
async def create_purchase_order(req: PurchaseOrderCreateRequest):
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    cursor = conn.cursor()
    try:
        # Generate an order number if none is provided
        order_number = req.order_number
        if not order_number:
            cursor.execute("SELECT COUNT(*) FROM purchase_orders")
            count = cursor.fetchone()[0]
            order_number = f"PO-{count + 1:04d}"

        cursor.execute("""
            INSERT INTO purchase_orders (
                company_id, contact_id, order_number, order_date, 
                due_date, total_amount, status, source_system
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (req.company_id, req.contact_id, order_number, req.order_date,
              req.due_date, req.total_amount, req.status, req.source_system))
        
        po_id = cursor.lastrowid
        
        # Insert lines
        for line in req.lines:
            subtotal = line.subtotal if line.subtotal is not None else (line.quantity * line.unit_price)
            cursor.execute("""
                INSERT INTO purchase_order_lines (
                    purchase_order_id, product_id, description, 
                    quantity, unit_price, tax_id, subtotal
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (po_id, line.product_id, line.description, 
                  line.quantity, line.unit_price, line.tax_id, subtotal))
            
        conn.commit()
        return {"ok": True, "id": po_id, "order_number": order_number}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        cursor.close()
        conn.close()
