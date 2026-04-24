const API_BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

// ── Config ──
export interface GlobalConfig {
  db_source: string;
  company_name: string;
  // API Keys
  openai_api_key?: string;
  deepseek_api_key?: string;
  // Email Configuration
  email_address?: string;
  email_app_password?: string;
  // Database Configuration
  odoo_db_host?: string;
  odoo_db_port?: string;
  odoo_db_name?: string;
  odoo_db_user?: string;
  odoo_db_password?: string;
}

export const getConfig = () => request<GlobalConfig>("/config");
export const updateConfig = (data: Partial<GlobalConfig>) =>
  request<GlobalConfig>("/config", { method: "PUT", body: JSON.stringify(data) });

// ── Mapping ──
export interface MappingResponse {
  mapping: Record<string, any> | null;
  db_source: string;
  error?: string;
}
export const getMapping = () => request<MappingResponse>("/mapping");
export const updateMapping = (mapping: Record<string, any>) =>
  request<{ ok: boolean; message?: string; error?: string }>("/mapping", {
    method: "PUT",
    body: JSON.stringify({ mapping }),
  });

// ── Odoo Schema ──
export interface OdooSchemaResponse {
  schema: Record<string, string[]> | null;
  db_source: string;
  table_count: number;
  error?: string;
}
export const getOdooSchema = () => request<OdooSchemaResponse>("/odoo-schema");

// ── Sessions ──
export const listSessions = () =>
  request<{ sessions: string[] }>("/sessions");
export const createSession = () =>
  request<{ session_id: string }>("/sessions/new", { method: "POST" });

// ── Chat ──
export interface ChatResponse {
  route: string;
  session_id: string;
  response: string;
}
export const sendChat = (message: string, session_id?: string, thinking_mode: string = "thinking") =>
  request<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({ message, session_id, thinking_mode }),
  });

export const createChatWebSocket = (
  message: string,
  session_id: string | undefined,
  thinking_mode: string,
  onEvent: (event: any) => void,
  onClose: () => void,
  onError: (err: any) => void
) => {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.port === "5173" || window.location.port === "5174" ? "localhost:8000" : window.location.host;
  const wsUrl = `${protocol}//${host}/api/ws/chat`;
  
  const ws = new WebSocket(wsUrl);
  
  ws.onopen = () => {
    ws.send(JSON.stringify({ message, session_id, thinking_mode }));
  };
  
  ws.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      onEvent(data);
    } catch (err) {
      console.error("Failed to parse websocket message", err);
    }
  };
  
  ws.onerror = (err) => onError(err);
  ws.onclose = () => onClose();
  
  return ws;
};

// ── Audit ──
export interface AuditResult {
  invoice_number: string;
  state: string;
  note: string;
  audits_results: Record<string, unknown>[];
}
export interface AuditResponse {
  route: string;
  session_id: string;
  results: AuditResult[];
}
export const runAudit = (message: string, session_id?: string) =>
  request<AuditResponse>("/audit", {
    method: "POST",
    body: JSON.stringify({ message, session_id }),
  });

// ── Local DB Sync ──
export const syncLocalDb = (session_id?: string) =>
  request<{ route: string; session_id: string; message: string }>("/local_db", {
    method: "POST",
    body: JSON.stringify({ session_id }),
  });

// ── Terminology Sync ──
export const syncTerminology = (session_id?: string) =>
  request<{ route: string; session_id: string; message: string }>("/terminology", {
    method: "POST",
    body: JSON.stringify({ session_id }),
  });

// ── Sync Email ──
export const syncEmail = (query: string, session_id?: string) =>
  request<{ route: string; session_id: string; message: string }>("/sync_email", {
    method: "POST",
    body: JSON.stringify({ query, session_id }),
  });

// ── Upload Docs ──
export const uploadDocs = async (files: File[], session_id?: string) => {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  if (session_id) form.append("session_id", session_id);

  const res = await fetch(`${API_BASE}/upload_docs`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json() as Promise<{
    route: string;
    session_id: string;
    message: string;
    files: string[];
  }>;
};

// ── Exit ──
export const exitConversation = (session_id?: string) =>
  request<{ route: string; session_id: string; message: string }>("/exit", {
    method: "POST",
    body: JSON.stringify({ session_id }),
    keepalive: true,
  });

// ── Contacts ──
export interface ContactCreatePayload {
  name: string;
  tax_number?: string;
  email?: string;
  phone?: string;
  address?: string;
  source_system?: string;
  type?: string;
}

export const createContact = (data: ContactCreatePayload) =>
  request<{ ok: boolean; id?: number; error?: string }>("/contacts", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const updateContact = (id: number, data: Partial<ContactCreatePayload>) =>
  request<{ ok: boolean; error?: string }>(`/contacts/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });

export const deleteContact = (id: number) =>
  request<{ ok: boolean; error?: string }>(`/contacts/${id}`, {
    method: "DELETE",
  });

// ── Products ──
export interface ProductCreatePayload {
  name: string;
  description?: string;
  price?: number;
  cost?: number;
  type?: string;
  source_system?: string;
}

export const createProduct = (data: ProductCreatePayload) =>
  request<{ ok: boolean; id?: number; error?: string }>("/products", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const updateProduct = (id: number, data: Partial<ProductCreatePayload>) =>
  request<{ ok: boolean; error?: string }>(`/products/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });

export const deleteProduct = (id: number) =>
  request<{ ok: boolean; error?: string }>(`/products/${id}`, {
    method: "DELETE",
  });

// ── Inventory Logs ──
export interface InventoryLogCreatePayload {
  supplier_id?: number | null;
  product_id?: number | null;
  change_quantity?: number;
  change_type?: string;
  source_system?: string;
  timestamp?: string;
}

export const createInventoryLog = (data: InventoryLogCreatePayload) =>
  request<{ ok: boolean; id?: number; error?: string }>("/inventory_logs", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const updateInventoryLog = (id: number, data: Partial<InventoryLogCreatePayload>) =>
  request<{ ok: boolean; error?: string }>(`/inventory_logs/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });

export const deleteInventoryLog = (id: number) =>
  request<{ ok: boolean; error?: string }>(`/inventory_logs/${id}`, {
    method: "DELETE",
  });

// ── Full Report ──
export interface FullReportSummary {
  latest_month: string;
  total_revenue: number;
  total_cogs: number;
  total_expenses: number;
  net_profit: number;
  avg_gross_margin: number;
  avg_dso_days: number;
  total_invoice_count: number;
  avg_unique_customers: number;
  top1_customer_pct: number;
  overdue_ratio: number;
  months_of_data: number;
}

export interface FullReportPredictions {
  random_forest: { accuracy_percent: number; predictions: number[] };
  xgboost: { accuracy_percent: number; predictions: number[] };
}

export interface FlaggedInvoice {
  id: number;
  invoice_number: string | null;
  supplier_name: string | null;
  type: string | null;
  invoice_date: string | null;
  due_date: string | null;
  total_amount: number | null;
  status: string | null;
}

export interface FullReportData {
  summary: FullReportSummary;
  features: Record<string, unknown>[];
  predictions: FullReportPredictions;
  last_month: string;
  anomalies: { flagged_ids: number[]; flagged_invoices: FlaggedInvoice[] };
  generated_at: string;
  features_error?: string;
  predictions_error?: string;
  anomalies_error?: string;
}

export const getFullReport = () => request<FullReportData>("/reports/full");
