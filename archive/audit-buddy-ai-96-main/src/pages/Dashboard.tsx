import { FileText, AlertTriangle, Users, Package, ShieldAlert } from "lucide-react";
import { StatCard } from "@/components/StatCard";
import { RiskBadge } from "@/components/StatusBadges";
import { StatsSkeleton, ChartSkeleton } from "@/components/Skeletons";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useDashboard } from "@/services/queries";
import {
  PieChart, Pie, Cell, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from "recharts";

export default function DashboardPage() {
  const { data, isLoading } = useDashboard();

  if (isLoading || !data) {
    return (
      <div className="space-y-6">
        <div><h2 className="text-2xl font-semibold">Dashboard</h2><p className="text-muted-foreground text-sm">AI Audit Overview</p></div>
        <StatsSkeleton />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4"><ChartSkeleton /><ChartSkeleton /><ChartSkeleton /></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div><h2 className="text-2xl font-semibold">Dashboard</h2><p className="text-muted-foreground text-sm">AI Financial Audit Agent — System Overview</p></div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard title="Total Invoices" value={data.total_invoices} icon={FileText} />
        <StatCard title="Suppliers" value={data.total_suppliers} icon={Users} />
        <StatCard title="Products" value={data.total_products} icon={Package} />
        <StatCard title="Audit Findings" value={data.total_audit_findings} icon={ShieldAlert} variant="warning" />
        <StatCard title="High Risk" value={data.high_risk_findings} icon={AlertTriangle} variant="danger" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="animate-fade-in">
          <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Profit Prediction</CardTitle></CardHeader>
          <CardContent>
            {data.profit_prediction.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={data.profit_prediction}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="month" tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }} />
                  <YAxis tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }} />
                  <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "8px", fontSize: "12px", color: "hsl(var(--card-foreground))" }} />
                  <Line type="monotone" dataKey="profit" stroke="hsl(var(--primary))" strokeWidth={2} dot={{ r: 3, fill: "hsl(var(--primary))" }} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[220px] flex items-center justify-center text-sm text-muted-foreground">No prediction data</div>
            )}
          </CardContent>
        </Card>

        <Card className="animate-fade-in">
          <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Cash Flow Risk Deficit Probability</CardTitle></CardHeader>
          <CardContent>
            {data.predicted_cash_flow_risk.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={data.predicted_cash_flow_risk} cx="50%" cy="50%" innerRadius={55} outerRadius={80} paddingAngle={4} dataKey="value">
                    {data.predicted_cash_flow_risk.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "8px", fontSize: "12px", color: "hsl(var(--card-foreground))" }} />
                  <Legend iconSize={8} wrapperStyle={{ fontSize: "12px" }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[220px] flex items-center justify-center text-sm text-muted-foreground">No risk data</div>
            )}
          </CardContent>
        </Card>

        <Card className="animate-fade-in">
          <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Predicted Future Findings by Risk</CardTitle></CardHeader>
          <CardContent>
            {data.predicted_findings_by_risk.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={data.predicted_findings_by_risk} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis type="number" tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }} />
                  <YAxis dataKey="category" type="category" width={90} tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} />
                  <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "8px", fontSize: "12px", color: "hsl(var(--card-foreground))" }} />
                  <Bar dataKey="count" fill="hsl(var(--primary))" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[220px] flex items-center justify-center text-sm text-muted-foreground">No prediction data</div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="animate-fade-in">
        <CardHeader className="pb-3"><CardTitle className="text-sm font-medium">Recent Audit Findings</CardTitle></CardHeader>
        <CardContent>
          {data.recent_audit_results.length > 0 ? (
            <div className="space-y-3">
              {data.recent_audit_results.map((r) => (
                <div key={r.id} className="flex items-start gap-3 p-3 rounded-lg bg-secondary/50">
                  <RiskBadge level={r.risk_level} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium">
                      {r.rule_name ? String(r.rule_name).replace(/_/g, " ").toUpperCase() : "AUDIT CHECK"}
                    </p>
                    <div className="text-sm text-muted-foreground mt-1">
                      {(() => {
                        let issues = r.issue_detected;
                        if (typeof issues === "string") {
                          try {
                            issues = JSON.parse(issues);
                          } catch (e) {
                            if (issues.trim().startsWith("[") && issues.trim().endsWith("]")) {
                              issues = issues
                                .trim()
                                .slice(1, -1)
                                .split(/',\s*'|",\s*"|',\s*"|",\s*'/)
                                .map((s) => s.replace(/(^["'])|(["']$)/g, ""));
                            } else {
                              issues = [issues];
                            }
                          }
                        }
                        
                        return Array.isArray(issues) && issues.length > 0 ? (
                          <ul className="list-inside list-disc">
                            {issues.map((issue, idx) => (
                              <li key={idx} className="mt-1">{String(issue).replace(/^["']|["']$/g, "")}</li>
                            ))}
                          </ul>
                        ) : (
                          <span>{r.issue_detected ?? "No issue"}</span>
                        );
                      })()}
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      {r.entity_type} #{r.entity_id}
                      {r.ai_confidence != null && ` · Confidence: ${(r.ai_confidence * 100).toFixed(0)}%`}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-4">No audit findings yet. Run an audit or sync the local DB first.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
