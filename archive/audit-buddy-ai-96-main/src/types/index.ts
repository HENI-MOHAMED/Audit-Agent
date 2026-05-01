export interface Invoice {
  id: number;
  invoice_number: string | null;
  contact_id: number | null;
  supplier_name: string | null;
  type: string | null;
  currency: string | null;
  invoice_date: string | null;
  due_date: string | null;
  total_untaxed: number | null;
  total_tax: number | null;
  total_amount: number | null;
  status: string | null;
  source_system: string | null;
  line_items?: InvoiceLineItem[];
  audit_results?: AuditResultRow[];
}

export interface InvoiceLineItem {
  id: number;
  description: string | null;
  quantity: number | null;
  unit_price: number | null;
  subtotal: number | null;
  product_name: string | null;
}

export interface AuditResultRow {
  id: number;
  entity_type: string | null;
  entity_id: number | null;
  rule_name: string | null;
  risk_level: string | null;
  issue_detected: string | null;
  recommendation: string | null;
  ai_confidence: number | null;
}

export interface Supplier {
  id: number;
  name: string | null;
  tax_number: string | null;
  address: string | null;
  email: string | null;
  phone: string | null;
  type: string | null;
  source_system: string | null;
  total_invoices: number;
}

export interface Product {
  id: number;
  name: string | null;
  description: string | null;
  price: number | null;
  cost: number | null;
  type: string | null;
  source_system: string | null;
}

export interface InventoryMovement {
  id: number;
  product_name: string | null;
  supplier_name: string | null;
  change_quantity: number | null;
  change_type: string | null;
  timestamp: string | null;
  source_system: string | null;
}

export interface AuditLog {
  id: number;
  entity_type: string | null;
  entity_id: number | null;
  action: string | null;
  details: string | null;
  average_score: number | null;
  ai_score: number | null;
  risk_level: string | null;
  created_at: string | null;
}

export interface Document {
  id: number;
  invoice_id: number | null;
  file_name: string | null;
  file_path: string | null;
  uploaded_at: string | null;
  invoice_number: string | null;
}

export interface DashboardData {
  total_invoices: number;
  total_suppliers: number;
  total_products: number;
  total_audit_findings: number;
  high_risk_findings: number;
  predicted_cash_flow_risk: { name: string; value: number; color: string }[];
  profit_prediction: { month: string; profit: number; predicted: boolean }[];
  predicted_findings_by_risk: { category: string; count: number }[];
  recent_audit_results: AuditResultRow[];
}

export interface PurchaseOrderLineItemPayload {
  product_id: number;
  description?: string;
  quantity: number;
  unit_price: number;
  tax_id?: number | null;
  subtotal?: number | null;
}

export interface PurchaseOrderPayload {
  contact_id: number;
  company_id?: number | null;
  order_number?: string | null;
  order_date?: string | null;
  due_date?: string | null;
  total_amount?: number | null;
  status: string;
  source_system?: string;
  lines: PurchaseOrderLineItemPayload[];
}
