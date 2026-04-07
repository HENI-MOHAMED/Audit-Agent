import { Badge } from "@/components/ui/badge";

// ── Risk Level Badge (for audit_results.risk_level and audit_logs.risk_level) ──

const RISK_STYLES: Record<string, { label: string; className: string }> = {
  low: { label: "Low", className: "bg-risk-low/10 text-risk-low border-risk-low/20" },
  medium: { label: "Medium", className: "bg-risk-medium/10 text-risk-medium border-risk-medium/20" },
  high: { label: "High", className: "bg-risk-high/10 text-risk-high border-risk-high/20" },
  critical: { label: "Critical", className: "bg-risk-critical/10 text-risk-critical border-risk-critical/20" },
};

export function RiskBadge({ level }: { level: string | null }) {
  const key = (level ?? "").toLowerCase();
  const config = RISK_STYLES[key];
  if (!config) {
    return <Badge variant="outline" className="bg-muted text-muted-foreground border-border capitalize">{level ?? "N/A"}</Badge>;
  }
  return <Badge variant="outline" className={config.className}>{config.label}</Badge>;
}

// ── Status Badge (for invoices.status, purchase_orders.status, etc.) ──

const STATUS_STYLES: Record<string, { label: string; className: string }> = {
  draft: { label: "Draft", className: "bg-muted text-muted-foreground border-border" },
  pending: { label: "Pending", className: "bg-risk-medium/10 text-risk-medium border-risk-medium/20" },
  posted: { label: "Posted", className: "bg-risk-low/10 text-risk-low border-risk-low/20" },
  paid: { label: "Paid", className: "bg-primary/10 text-primary border-primary/20" },
  cancelled: { label: "Cancelled", className: "bg-risk-high/10 text-risk-high border-risk-high/20" },
  reversed: { label: "Reversed", className: "bg-risk-high/10 text-risk-high border-risk-high/20" },
  in_progress: { label: "In Progress", className: "bg-primary/10 text-primary border-primary/20" },
  approved: { label: "Approved", className: "bg-risk-low/10 text-risk-low border-risk-low/20" },
  completed: { label: "Completed", className: "bg-risk-low/10 text-risk-low border-risk-low/20" },
  open: { label: "Open", className: "bg-primary/10 text-primary border-primary/20" },
};

export function StatusBadge({ status }: { status: string | null }) {
  const key = (status ?? "").toLowerCase();
  const config = STATUS_STYLES[key];
  if (!config) {
    return <Badge variant="outline" className="bg-muted text-muted-foreground border-border capitalize">{status ?? "N/A"}</Badge>;
  }
  return <Badge variant="outline" className={config.className}>{config.label}</Badge>;
}
