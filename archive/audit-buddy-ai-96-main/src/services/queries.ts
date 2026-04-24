import { useState, useEffect } from "react";
import { useDbQuery } from "@/hooks/useWebSocketDB";
import type {
  Invoice,
  InvoiceLineItem,
  Supplier,
  Product,
  InventoryMovement,
  AuditLog,
  Document,
  DashboardData,
  AuditResultRow,
} from "@/types";

// ── Dashboard (aggregated from multiple tables) ──

export function useDashboard(): { data: DashboardData | undefined; isLoading: boolean } {
  const inv = useDbQuery<{ cnt: number }>("SELECT COUNT(*) as cnt FROM invoices");
  const sup = useDbQuery<{ cnt: number }>("SELECT COUNT(*) as cnt FROM contacts WHERE type = 'supplier'");
  const prod = useDbQuery<{ cnt: number }>("SELECT COUNT(*) as cnt FROM products");
  const findings = useDbQuery<{ cnt: number }>("SELECT COUNT(*) as cnt FROM audit_logs");
  const highRisk = useDbQuery<{ cnt: number }>("SELECT COUNT(*) as cnt FROM audit_logs WHERE risk_level IN ('high', 'critical')");
  const recentAudit = useDbQuery<AuditResultRow>("SELECT * FROM audit_results ORDER BY id DESC LIMIT 10");

  const [predictions, setPredictions] = useState<any>(null);
  const [predictionsLoading, setPredictionsLoading] = useState(true);

  useEffect(() => {
    fetch("/api/dashboard/predictions")
      .then((res) => res.json())
      .then((data) => {
        setPredictions(data);
        setPredictionsLoading(false);
      })
      .catch((err) => {
        console.error("Failed to fetch predictions", err);
        // Fallback incase backend doesn't respond
        setPredictions({
          profit_prediction: [],
          predicted_cash_flow_risk: [],
          predicted_findings_by_risk: []
        });
        setPredictionsLoading(false);
      });
  }, []);

  const isBasicLoading = inv.loading || sup.loading || prod.loading || findings.loading || highRisk.loading || recentAudit.loading;
  const isLoading = isBasicLoading || predictionsLoading;

  if (isLoading) return { data: undefined, isLoading: true };

  const data: DashboardData = {
    total_invoices: inv.data[0]?.cnt ?? 0,
    total_suppliers: sup.data[0]?.cnt ?? 0,
    total_products: prod.data[0]?.cnt ?? 0,
    total_audit_findings: findings.data[0]?.cnt ?? 0,
    high_risk_findings: highRisk.data[0]?.cnt ?? 0,
    predicted_cash_flow_risk: predictions?.predicted_cash_flow_risk || [],
    profit_prediction: predictions?.profit_prediction || [],
    predicted_findings_by_risk: predictions?.predicted_findings_by_risk || [],
    recent_audit_results: recentAudit.data,
  };

  return { data, isLoading: false };
}

// ── Invoices (joined with contacts for supplier name) ──

export function useInvoices() {
  const q = useDbQuery<Invoice>(
    `SELECT i.*, c.name as supplier_name
     FROM invoices i
     LEFT JOIN contacts c ON i.supplier_id = c.id
     ORDER BY i.id DESC`
  );
  return { data: q.data, isLoading: q.loading, error: q.error, refetch: q.refetch };
}

export function useInvoice(id: number) {
  const q = useDbQuery<Invoice>(
    `SELECT i.*, c.name as supplier_name
     FROM invoices i
     LEFT JOIN contacts c ON i.supplier_id = c.id
     WHERE i.id = ${id}`,
    !!id
  );
  return { data: q.data[0] ?? null, isLoading: q.loading };
}

export function useInvoiceLineItems(invoiceId: number) {
  const q = useDbQuery<InvoiceLineItem>(
    `SELECT il.*, p.name as product_name
     FROM invoice_lines il
     LEFT JOIN products p ON il.product_id = p.id
     WHERE il.invoice_id = ${invoiceId}`,
    !!invoiceId
  );
  return { data: q.data, isLoading: q.loading };
}

export function useInvoiceAuditResults(invoiceId: number) {
  const q = useDbQuery<AuditResultRow>(
    `SELECT * FROM audit_results WHERE entity_type = 'invoice' AND entity_id = ${invoiceId}`,
    !!invoiceId
  );
  return { data: q.data, isLoading: q.loading };
}

// ── Suppliers (from contacts table where type = supplier) ──

export function useSuppliers() {
  const q = useDbQuery<Supplier>(
    `SELECT c.*, COALESCE(inv_cnt.cnt, 0) as total_invoices
     FROM contacts c
     LEFT JOIN (SELECT supplier_id, COUNT(*) as cnt FROM invoices GROUP BY supplier_id) inv_cnt
       ON c.id = inv_cnt.supplier_id
     WHERE c.type = 'supplier'
     ORDER BY c.name`
  );
  return { data: q.data, isLoading: q.loading, error: q.error, refetch: q.refetch };
}

// ── Products ──

export function useProducts() {
  const q = useDbQuery<Product>("SELECT * FROM products ORDER BY name");
  return { data: q.data, isLoading: q.loading, error: q.error, refetch: q.refetch };
}

// ── Inventory (inventory_logs joined with products and contacts) ──

export function useInventory() {
  const q = useDbQuery<InventoryMovement>(
    `SELECT il.*, p.name as product_name, c.name as supplier_name
     FROM inventory_logs il
     LEFT JOIN products p ON il.product_id = p.id
     LEFT JOIN contacts c ON il.supplier_id = c.id
     ORDER BY il.id DESC`
  );
  return { data: q.data, isLoading: q.loading, error: q.error, refetch: q.refetch };
}

// ── Audit Logs ──

export function useAuditLogs() {
  const q = useDbQuery<AuditLog>("SELECT * FROM audit_logs ORDER BY id DESC");
  return { data: q.data, isLoading: q.loading, error: q.error, refetch: q.refetch };
}

// ── Documents (attachments joined with invoices for invoice_number) ──

export function useDocuments() {
  const q = useDbQuery<Document>(
    `SELECT a.*, i.invoice_number
     FROM attachments a
     LEFT JOIN invoices i ON a.invoice_id = i.id
     ORDER BY a.id DESC`
  );
  return { data: q.data, isLoading: q.loading, error: q.error, refetch: q.refetch };
}

// ── Full Report (features pipeline + predictions + anomalies) ──

import { getFullReport, type FullReportData } from "@/services/api";

export function useFullReport(): { data: FullReportData | undefined; isLoading: boolean; error: string | null } {
  const [data, setData] = useState<FullReportData | undefined>(undefined);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    getFullReport()
      .then((res) => {
        setData(res);
        setIsLoading(false);
      })
      .catch((err) => {
        console.error("Failed to fetch full report", err);
        setError(err.message || "Failed to load report");
        setIsLoading(false);
      });
  }, []);

  return { data, isLoading, error };
}
