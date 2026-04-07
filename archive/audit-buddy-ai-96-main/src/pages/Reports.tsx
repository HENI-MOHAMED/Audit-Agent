import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RiskBadge } from "@/components/StatusBadges";
import { TableSkeleton } from "@/components/Skeletons";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useState } from "react";
import { useDbQuery } from "@/hooks/useWebSocketDB";
import type { AuditResultRow } from "@/types";

export default function ReportsPage() {
  const [entityFilter, setEntityFilter] = useState("all");

  const whereClause = entityFilter === "all" ? "" : `WHERE entity_type = '${entityFilter}'`;
  const { data, loading } = useDbQuery<AuditResultRow>(
    `SELECT * FROM audit_results ${whereClause} ORDER BY id DESC LIMIT 100`
  );

  const summary = useDbQuery<{ entity_type: string; risk_level: string; cnt: number }>(
    `SELECT entity_type, risk_level, COUNT(*) as cnt FROM audit_results GROUP BY entity_type, risk_level ORDER BY entity_type, risk_level`
  );

  return (
    <div className="space-y-6">
      <div><h2 className="text-2xl font-semibold">Reports</h2><p className="text-muted-foreground text-sm">Audit findings and risk reports from the database</p></div>

      <Card>
        <CardHeader><CardTitle className="text-sm font-medium">Findings Summary</CardTitle></CardHeader>
        <CardContent>
          {summary.loading ? <TableSkeleton rows={3} cols={3} /> : summary.data.length > 0 ? (
            <Table>
              <TableHeader><TableRow>
                <TableHead>Entity Type</TableHead><TableHead>Risk Level</TableHead><TableHead className="text-right">Count</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {summary.data.map((row, i) => (
                  <TableRow key={i}>
                    <TableCell className="text-sm capitalize">{row.entity_type ?? "N/A"}</TableCell>
                    <TableCell><RiskBadge level={row.risk_level} /></TableCell>
                    <TableCell className="text-right text-sm font-medium">{row.cnt}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-4">No audit results yet. Run an audit first.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium">Detailed Findings</CardTitle>
            <Select value={entityFilter} onValueChange={setEntityFilter}>
              <SelectTrigger className="w-36 h-9"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Entities</SelectItem>
                <SelectItem value="invoice">Invoices</SelectItem>
                <SelectItem value="purchase_order">Purchase Orders</SelectItem>
                <SelectItem value="payment">Payments</SelectItem>
                <SelectItem value="product">Products</SelectItem>
                <SelectItem value="contact">Contacts</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? <div className="p-6"><TableSkeleton rows={5} cols={6} /></div> : data.length > 0 ? (
            <Table>
              <TableHeader><TableRow>
                <TableHead>Entity</TableHead><TableHead>Entity ID</TableHead><TableHead>Rule</TableHead>
                <TableHead>Risk</TableHead><TableHead>Issue</TableHead><TableHead>Recommendation</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {data.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="text-sm capitalize">{r.entity_type ?? "N/A"}</TableCell>
                    <TableCell className="text-sm font-mono text-muted-foreground">{r.entity_id ?? "N/A"}</TableCell>
                    <TableCell className="text-sm">{r.rule_name ?? "N/A"}</TableCell>
                    <TableCell><RiskBadge level={r.risk_level} /></TableCell>
                    <TableCell className="text-sm max-w-xs truncate">{r.issue_detected ?? "N/A"}</TableCell>
                    <TableCell className="text-sm max-w-xs truncate text-muted-foreground">{r.recommendation ?? "N/A"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="p-8 text-center text-muted-foreground text-sm">No findings for this filter.</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
