import { useAuditLogs } from "@/services/queries";
import { RiskBadge } from "@/components/StatusBadges";
import { TableSkeleton } from "@/components/Skeletons";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useState } from "react";

export default function AuditLogsPage() {
  const { data: logs, isLoading } = useAuditLogs();
  const [riskFilter, setRiskFilter] = useState<string>("all");

  const filtered = logs?.filter(l => riskFilter === "all" || (l.risk_level ?? "").toLowerCase() === riskFilter);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div><h2 className="text-2xl font-semibold">Audit Logs</h2><p className="text-muted-foreground text-sm">System audit findings and alerts</p></div>
        <Select value={riskFilter} onValueChange={setRiskFilter}>
          <SelectTrigger className="w-36 h-9"><SelectValue placeholder="Filter risk" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="critical">Critical</SelectItem>
            <SelectItem value="high">High</SelectItem>
            <SelectItem value="medium">Medium</SelectItem>
            <SelectItem value="low">Low</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <Card>
        <CardContent className="p-0">
          {isLoading ? <div className="p-6"><TableSkeleton cols={7} /></div> : (filtered && filtered.length > 0) ? (
            <Table>
              <TableHeader><TableRow>
                <TableHead>Entity</TableHead><TableHead>Entity ID</TableHead><TableHead>Action</TableHead>
                <TableHead>Risk</TableHead><TableHead>Scores</TableHead><TableHead>Details</TableHead><TableHead>Time</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {filtered.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell className="text-sm font-medium capitalize">{log.entity_type ?? "N/A"}</TableCell>
                    <TableCell className="text-sm font-mono text-muted-foreground">{log.entity_id ?? "N/A"}</TableCell>
                    <TableCell className="text-sm capitalize">{(log.action ?? "N/A").replace(/_/g, " ")}</TableCell>
                    <TableCell><RiskBadge level={log.risk_level} /></TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {log.average_score != null && `Avg: ${log.average_score.toFixed(1)}`}
                      {log.ai_score != null && ` / AI: ${log.ai_score.toFixed(1)}`}
                      {log.average_score == null && log.ai_score == null && "N/A"}
                    </TableCell>
                    <TableCell className="text-sm max-w-xs truncate">{log.details ?? "N/A"}</TableCell>
                    <TableCell className="text-sm text-muted-foreground whitespace-nowrap">{log.created_at ? new Date(log.created_at).toLocaleString() : "N/A"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="p-8 text-center text-muted-foreground text-sm">No audit logs found. Run an audit first.</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
