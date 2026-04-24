import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ChartSkeleton, StatsSkeleton } from "@/components/Skeletons";
import { useFullReport } from "@/services/queries";
import {
  DollarSign, TrendingUp, TrendingDown, Clock, AlertTriangle,
  Users, FileText, Download, ShieldAlert, BarChart3, PieChart as PieIcon,
  Activity, Target
} from "lucide-react";
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  ComposedChart, ReferenceLine,
} from "recharts";
import type { FlaggedInvoice } from "@/services/api";

/* ───────────────────── helpers ───────────────────── */

const fmt = (n: number | null | undefined, decimals = 0) => {
  if (n == null || isNaN(n)) return "—";
  return n.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
};

const fmtPct = (n: number | null | undefined) => {
  if (n == null || isNaN(n)) return "—";
  return `${(n * 100).toFixed(1)}%`;
};

const fmtCurrency = (n: number | null | undefined) => {
  if (n == null || isNaN(n)) return "—";
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toFixed(0);
};

const CHART_STYLE = {
  grid: "hsl(var(--border))",
  tick: { fontSize: 11, fill: "hsl(var(--muted-foreground))" },
  tooltip: {
    background: "hsl(var(--card))",
    border: "1px solid hsl(var(--border))",
    borderRadius: "8px",
    fontSize: "12px",
    color: "hsl(var(--card-foreground))",
  },
};

const COLORS = {
  primary: "hsl(221, 83%, 53%)",
  success: "hsl(142, 71%, 45%)",
  warning: "hsl(38, 92%, 50%)",
  danger: "hsl(0, 84%, 60%)",
  info: "hsl(199, 89%, 48%)",
  purple: "hsl(262, 83%, 58%)",
  muted: "hsl(var(--muted-foreground))",
};

/* ───────────────────── KPI Card ───────────────────── */

function KpiCard({ title, value, subtitle, icon: Icon, color = "primary" }: {
  title: string; value: string; subtitle?: string;
  icon: React.ElementType; color?: "primary" | "success" | "warning" | "danger" | "info";
}) {
  const colorMap = {
    primary: "bg-blue-500/10 text-blue-500",
    success: "bg-emerald-500/10 text-emerald-500",
    warning: "bg-amber-500/10 text-amber-500",
    danger: "bg-red-500/10 text-red-500",
    info: "bg-cyan-500/10 text-cyan-500",
  };
  return (
    <Card className="animate-fade-in">
      <CardContent className="pt-5 pb-4 px-5">
        <div className="flex items-center gap-3">
          <div className={`rounded-lg p-2.5 ${colorMap[color]}`}>
            <Icon className="h-5 w-5" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{title}</p>
            <p className="text-xl font-bold mt-0.5 truncate">{value}</p>
            {subtitle && <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

/* ───────────────────── Section Header ───────────────────── */

function SectionHeader({ icon: Icon, title, description }: {
  icon: React.ElementType; title: string; description: string;
}) {
  return (
    <div className="flex items-center gap-3 mb-4 mt-2">
      <div className="rounded-lg p-2 bg-primary/10 text-primary">
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <h3 className="text-base font-semibold">{title}</h3>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}

/* ───────────────────── Accuracy Badge ───────────────────── */

function AccuracyBadge({ label, accuracy }: { label: string; accuracy: number }) {
  const color = accuracy >= 80 ? "bg-emerald-500/15 text-emerald-600 border-emerald-500/30"
    : accuracy >= 60 ? "bg-amber-500/15 text-amber-600 border-amber-500/30"
    : "bg-red-500/15 text-red-600 border-red-500/30";
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${color}`}>
      <Target className="h-3 w-3" />
      {label}: {accuracy.toFixed(1)}%
    </span>
  );
}

/* ═══════════════════════════════════════════════════════════
   MAIN COMPONENT
   ═══════════════════════════════════════════════════════════ */

export default function ReportsPage() {
  const { data, isLoading, error } = useFullReport();

  const handleExportPdf = () => window.print();

  /* ── Loading ── */
  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-semibold">Financial Intelligence Report</h2>
          <p className="text-muted-foreground text-sm">Loading comprehensive analysis...</p>
        </div>
        <StatsSkeleton />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4"><ChartSkeleton /><ChartSkeleton /></div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4"><ChartSkeleton /><ChartSkeleton /></div>
      </div>
    );
  }

  /* ── Error ── */
  if (error || !data) {
    return (
      <div className="space-y-6">
        <div><h2 className="text-2xl font-semibold">Financial Intelligence Report</h2></div>
        <Card><CardContent className="py-12 text-center">
          <AlertTriangle className="h-10 w-10 mx-auto text-destructive mb-3" />
          <p className="text-sm text-muted-foreground">{error || "Failed to load report data."}</p>
        </CardContent></Card>
      </div>
    );
  }

  const { summary: s, features, predictions, anomalies } = data;

  /* ── Prepare chart data ── */
  const revenueChartData = features.map((row: Record<string, unknown>) => ({
    month: row.month as string,
    revenue: Number(row.monthly_revenue) || 0,
    net_profit: Number(row.net_profit) || 0,
    cogs: Number(row.total_cogs) || 0,
    expenses: Number(row.total_expenses) || 0,
  }));

  const marginChartData = features.map((row: Record<string, unknown>) => ({
    month: row.month as string,
    gross_margin: Number(row.gross_margin) || 0,
    cogs_ratio: Number(row.cogs_to_revenue_ratio) || 0,
    expense_ratio: Number(row.expense_ratio) || 0,
  }));

  const cashFlowData = features.map((row: Record<string, unknown>) => ({
    month: row.month as string,
    dso_days: Number(row.dso_days) || 0,
    overdue_ratio: Number(row.overdue_ratio) || 0,
    billed: Number(row.billed_this_month) || 0,
    collected: Number(row.collected_this_month) || 0,
    collection_gap: Number(row.collection_gap) || 0,
  }));

  const volumeData = features.map((row: Record<string, unknown>) => ({
    month: row.month as string,
    invoice_count: Number(row.invoice_count) || 0,
    avg_invoice_value: Number(row.avg_invoice_value) || 0,
    unique_customers: Number(row.unique_customers) || 0,
    top1_pct: Number(row.top1_customer_pct) || 0,
  }));

  /* prediction chart — historical + forecasts */
  const profitHistory = features.map((row: Record<string, unknown>) => ({
    month: row.month as string,
    actual: Number(row.net_profit) || 0,
  }));

  const lastMonthStr = profitHistory.length > 0 ? profitHistory[profitHistory.length - 1].month : "";
  const lastDate = lastMonthStr ? new Date(lastMonthStr + "-01") : new Date();

  const predictionChartData = [
    ...profitHistory.map(r => ({ ...r, rf: null as number | null, xgb: null as number | null })),
  ];

  // Connect forecast lines to last actual point
  if (predictionChartData.length > 0) {
    const lastPoint = predictionChartData[predictionChartData.length - 1];
    lastPoint.rf = lastPoint.actual;
    lastPoint.xgb = lastPoint.actual;
  }

  predictions.random_forest.predictions.forEach((pred, i) => {
    const nextMonth = new Date(lastDate);
    nextMonth.setMonth(nextMonth.getMonth() + i + 1);
    const monthStr = `${nextMonth.getFullYear()}-${String(nextMonth.getMonth() + 1).padStart(2, '0')}`;
    const existing = predictionChartData.find(d => d.month === monthStr);
    if (existing) {
      existing.rf = pred;
    } else {
      predictionChartData.push({
        month: monthStr,
        actual: 0,
        rf: pred,
        xgb: predictions.xgboost.predictions[i] ?? null,
      });
    }
  });

  predictions.xgboost.predictions.forEach((pred, i) => {
    const nextMonth = new Date(lastDate);
    nextMonth.setMonth(nextMonth.getMonth() + i + 1);
    const monthStr = `${nextMonth.getFullYear()}-${String(nextMonth.getMonth() + 1).padStart(2, '0')}`;
    const existing = predictionChartData.find(d => d.month === monthStr);
    if (existing) {
      existing.xgb = pred;
    }
  });

  return (
    <div className="space-y-8 report-content">
      {/* ═══════ HEADER ═══════ */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Financial Intelligence Report</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Comprehensive analysis from feature engineering, ML predictions & anomaly detection
          </p>
          {data.generated_at && (
            <p className="text-xs text-muted-foreground mt-0.5">
              Generated: {new Date(data.generated_at).toLocaleString()}
            </p>
          )}
        </div>
        <button
          onClick={handleExportPdf}
          className="no-print inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors shadow-sm"
        >
          <Download className="h-4 w-4" />
          Export as PDF
        </button>
      </div>

      {/* ═══════ 1. EXECUTIVE SUMMARY KPIs ═══════ */}
      <div>
        <SectionHeader icon={BarChart3} title="Executive Summary" description={`Data span: ${s.months_of_data} months ending ${s.latest_month}`} />
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <KpiCard title="Revenue" value={fmtCurrency(s.total_revenue)} subtitle="Latest month" icon={DollarSign} color="primary" />
          <KpiCard title="Net Profit" value={fmtCurrency(s.net_profit)} subtitle="Latest month" icon={TrendingUp} color="success" />
          <KpiCard title="Gross Margin" value={fmtPct(s.avg_gross_margin)} subtitle="Avg all months" icon={Activity} color="info" />
          <KpiCard title="Avg DSO" value={`${fmt(s.avg_dso_days, 1)} days`} subtitle="Days sales outstanding" icon={Clock} color="warning" />
          <KpiCard title="Overdue Ratio" value={fmtPct(s.overdue_ratio)} subtitle="Latest month" icon={AlertTriangle} color="danger" />
          <KpiCard title="Customers" value={fmt(s.avg_unique_customers, 0)} subtitle={`Top 1 = ${fmtPct(s.top1_customer_pct)}`} icon={Users} color="info" />
        </div>
      </div>

      {/* ═══════ 2. REVENUE & PROFITABILITY ═══════ */}
      <div>
        <SectionHeader icon={TrendingUp} title="Revenue & Profitability Trend" description="Monthly revenue vs net profit over time" />
        <Card className="animate-fade-in">
          <CardContent className="pt-5">
            {revenueChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <ComposedChart data={revenueChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_STYLE.grid} />
                  <XAxis dataKey="month" tick={CHART_STYLE.tick} />
                  <YAxis tick={CHART_STYLE.tick} tickFormatter={(v) => fmtCurrency(v)} />
                  <Tooltip contentStyle={CHART_STYLE.tooltip} formatter={(v: number) => fmt(v, 0)} />
                  <Legend iconSize={8} wrapperStyle={{ fontSize: "12px" }} />
                  <Area type="monotone" dataKey="revenue" name="Revenue" fill={`${COLORS.primary}20`} stroke={COLORS.primary} strokeWidth={2} />
                  <Line type="monotone" dataKey="net_profit" name="Net Profit" stroke={COLORS.success} strokeWidth={2} dot={{ r: 3, fill: COLORS.success }} />
                  <ReferenceLine y={0} stroke={CHART_STYLE.grid} strokeDasharray="3 3" />
                </ComposedChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[300px] flex items-center justify-center text-sm text-muted-foreground">No revenue data available</div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ═══════ 3. COGS & EXPENSE ANALYSIS ═══════ */}
      <div>
        <SectionHeader icon={PieIcon} title="COGS & Expense Analysis" description="Cost structure breakdown and ratio trends" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card className="animate-fade-in">
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Cost Breakdown Over Time</CardTitle></CardHeader>
            <CardContent>
              {revenueChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={260}>
                  <AreaChart data={revenueChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke={CHART_STYLE.grid} />
                    <XAxis dataKey="month" tick={CHART_STYLE.tick} />
                    <YAxis tick={CHART_STYLE.tick} tickFormatter={(v) => fmtCurrency(v)} />
                    <Tooltip contentStyle={CHART_STYLE.tooltip} formatter={(v: number) => fmt(v, 0)} />
                    <Legend iconSize={8} wrapperStyle={{ fontSize: "12px" }} />
                    <Area type="monotone" dataKey="cogs" name="COGS" stackId="1" fill={`${COLORS.warning}40`} stroke={COLORS.warning} />
                    <Area type="monotone" dataKey="expenses" name="OpEx" stackId="1" fill={`${COLORS.danger}40`} stroke={COLORS.danger} />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[260px] flex items-center justify-center text-sm text-muted-foreground">No data</div>
              )}
            </CardContent>
          </Card>

          <Card className="animate-fade-in">
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Margin & Ratio Trends</CardTitle></CardHeader>
            <CardContent>
              {marginChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={marginChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke={CHART_STYLE.grid} />
                    <XAxis dataKey="month" tick={CHART_STYLE.tick} />
                    <YAxis tick={CHART_STYLE.tick} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
                    <Tooltip contentStyle={CHART_STYLE.tooltip} formatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
                    <Legend iconSize={8} wrapperStyle={{ fontSize: "12px" }} />
                    <Line type="monotone" dataKey="gross_margin" name="Gross Margin" stroke={COLORS.success} strokeWidth={2} dot={{ r: 2 }} />
                    <Line type="monotone" dataKey="cogs_ratio" name="COGS/Revenue" stroke={COLORS.warning} strokeWidth={2} dot={{ r: 2 }} />
                    <Line type="monotone" dataKey="expense_ratio" name="OpEx/Revenue" stroke={COLORS.danger} strokeWidth={1.5} strokeDasharray="4 4" dot={{ r: 2 }} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[260px] flex items-center justify-center text-sm text-muted-foreground">No data</div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* ═══════ 4. CASH FLOW & COLLECTIONS ═══════ */}
      <div>
        <SectionHeader icon={Activity} title="Cash Flow & Collection Metrics" description="Payment behavior, DSO trends, and billed vs collected" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card className="animate-fade-in">
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">DSO & Overdue Trend</CardTitle></CardHeader>
            <CardContent>
              {cashFlowData.length > 0 ? (
                <ResponsiveContainer width="100%" height={260}>
                  <ComposedChart data={cashFlowData}>
                    <CartesianGrid strokeDasharray="3 3" stroke={CHART_STYLE.grid} />
                    <XAxis dataKey="month" tick={CHART_STYLE.tick} />
                    <YAxis yAxisId="left" tick={CHART_STYLE.tick} label={{ value: "DSO days", angle: -90, position: "insideLeft", style: { fontSize: 10, fill: COLORS.muted } }} />
                    <YAxis yAxisId="right" orientation="right" tick={CHART_STYLE.tick} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
                    <Tooltip contentStyle={CHART_STYLE.tooltip} />
                    <Legend iconSize={8} wrapperStyle={{ fontSize: "12px" }} />
                    <Bar yAxisId="left" dataKey="dso_days" name="DSO Days" fill={`${COLORS.info}90`} radius={[3, 3, 0, 0]} />
                    <Line yAxisId="right" type="monotone" dataKey="overdue_ratio" name="Overdue %" stroke={COLORS.danger} strokeWidth={2} dot={{ r: 2 }} />
                  </ComposedChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[260px] flex items-center justify-center text-sm text-muted-foreground">No data</div>
              )}
            </CardContent>
          </Card>

          <Card className="animate-fade-in">
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Billed vs Collected</CardTitle></CardHeader>
            <CardContent>
              {cashFlowData.length > 0 ? (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={cashFlowData}>
                    <CartesianGrid strokeDasharray="3 3" stroke={CHART_STYLE.grid} />
                    <XAxis dataKey="month" tick={CHART_STYLE.tick} />
                    <YAxis tick={CHART_STYLE.tick} tickFormatter={(v) => fmtCurrency(v)} />
                    <Tooltip contentStyle={CHART_STYLE.tooltip} formatter={(v: number) => fmt(v, 0)} />
                    <Legend iconSize={8} wrapperStyle={{ fontSize: "12px" }} />
                    <Bar dataKey="billed" name="Billed" fill={`${COLORS.primary}90`} radius={[3, 3, 0, 0]} />
                    <Bar dataKey="collected" name="Collected" fill={`${COLORS.success}90`} radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[260px] flex items-center justify-center text-sm text-muted-foreground">No data</div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* ═══════ 5. VOLUME & CUSTOMER CONCENTRATION ═══════ */}
      <div>
        <SectionHeader icon={Users} title="Volume & Customer Concentration" description="Invoice volume, average value, and customer dependency risk" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card className="animate-fade-in">
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Invoice Volume & Avg Value</CardTitle></CardHeader>
            <CardContent>
              {volumeData.length > 0 ? (
                <ResponsiveContainer width="100%" height={260}>
                  <ComposedChart data={volumeData}>
                    <CartesianGrid strokeDasharray="3 3" stroke={CHART_STYLE.grid} />
                    <XAxis dataKey="month" tick={CHART_STYLE.tick} />
                    <YAxis yAxisId="left" tick={CHART_STYLE.tick} />
                    <YAxis yAxisId="right" orientation="right" tick={CHART_STYLE.tick} tickFormatter={(v) => fmtCurrency(v)} />
                    <Tooltip contentStyle={CHART_STYLE.tooltip} />
                    <Legend iconSize={8} wrapperStyle={{ fontSize: "12px" }} />
                    <Bar yAxisId="left" dataKey="invoice_count" name="# Invoices" fill={`${COLORS.primary}80`} radius={[3, 3, 0, 0]} />
                    <Line yAxisId="right" type="monotone" dataKey="avg_invoice_value" name="Avg Value" stroke={COLORS.purple} strokeWidth={2} dot={{ r: 2 }} />
                  </ComposedChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[260px] flex items-center justify-center text-sm text-muted-foreground">No data</div>
              )}
            </CardContent>
          </Card>

          <Card className="animate-fade-in">
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Customer Concentration Risk</CardTitle></CardHeader>
            <CardContent>
              {volumeData.length > 0 ? (
                <ResponsiveContainer width="100%" height={260}>
                  <ComposedChart data={volumeData}>
                    <CartesianGrid strokeDasharray="3 3" stroke={CHART_STYLE.grid} />
                    <XAxis dataKey="month" tick={CHART_STYLE.tick} />
                    <YAxis tick={CHART_STYLE.tick} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
                    <Tooltip contentStyle={CHART_STYLE.tooltip} formatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
                    <Legend iconSize={8} wrapperStyle={{ fontSize: "12px" }} />
                    <Area type="monotone" dataKey="top1_pct" name="Top 1 Customer %" fill={`${COLORS.danger}20`} stroke={COLORS.danger} strokeWidth={2} />
                    <Line type="monotone" dataKey="unique_customers" name="Unique Customers" stroke={COLORS.info} strokeWidth={2} dot={{ r: 2 }} />
                    <ReferenceLine y={0.3} stroke={COLORS.warning} strokeDasharray="6 3" label={{ value: "30% risk threshold", position: "insideTopRight", style: { fontSize: 10, fill: COLORS.warning } }} />
                  </ComposedChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[260px] flex items-center justify-center text-sm text-muted-foreground">No data</div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* ═══════ 6. PROFIT PREDICTIONS ═══════ */}
      <div>
        <SectionHeader icon={Target} title="ML Profit Predictions" description="3-month profit forecast from Random Forest & XGBoost models" />
        <Card className="animate-fade-in">
          <CardHeader className="pb-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle className="text-sm font-medium">Net Profit — Historical + 3-Month Forecast</CardTitle>
              <div className="flex gap-2">
                <AccuracyBadge label="Random Forest" accuracy={predictions.random_forest.accuracy_percent} />
                <AccuracyBadge label="XGBoost" accuracy={predictions.xgboost.accuracy_percent} />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {predictionChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={320}>
                <LineChart data={predictionChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_STYLE.grid} />
                  <XAxis dataKey="month" tick={CHART_STYLE.tick} />
                  <YAxis tick={CHART_STYLE.tick} tickFormatter={(v) => fmtCurrency(v)} />
                  <Tooltip contentStyle={CHART_STYLE.tooltip} formatter={(v: number) => v ? fmt(v, 0) : "—"} />
                  <Legend iconSize={8} wrapperStyle={{ fontSize: "12px" }} />
                  <ReferenceLine x={lastMonthStr} stroke={CHART_STYLE.grid} strokeDasharray="6 3" label={{ value: "← Actual | Forecast →", position: "top", style: { fontSize: 10, fill: COLORS.muted } }} />
                  <Line type="monotone" dataKey="actual" name="Actual Profit" stroke={COLORS.primary} strokeWidth={2} dot={{ r: 3, fill: COLORS.primary }} connectNulls />
                  <Line type="monotone" dataKey="rf" name="RF Forecast" stroke={COLORS.success} strokeWidth={2} strokeDasharray="6 3" dot={{ r: 3, fill: COLORS.success }} connectNulls />
                  <Line type="monotone" dataKey="xgb" name="XGB Forecast" stroke={COLORS.purple} strokeWidth={2} strokeDasharray="6 3" dot={{ r: 3, fill: COLORS.purple }} connectNulls />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[320px] flex items-center justify-center text-sm text-muted-foreground">No prediction data</div>
            )}

            {/* Prediction values table */}
            {(predictions.random_forest.predictions.length > 0 || predictions.xgboost.predictions.length > 0) && (
              <div className="mt-4 border rounded-lg overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Forecast Month</TableHead>
                      <TableHead className="text-right">Random Forest</TableHead>
                      <TableHead className="text-right">XGBoost</TableHead>
                      <TableHead className="text-right">Avg Prediction</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {predictions.random_forest.predictions.map((rfPred, i) => {
                      const xgbPred = predictions.xgboost.predictions[i] ?? 0;
                      const nextMonth = new Date(lastDate);
                      nextMonth.setMonth(nextMonth.getMonth() + i + 1);
                      const monthLabel = `${nextMonth.getFullYear()}-${String(nextMonth.getMonth() + 1).padStart(2, '0')}`;
                      return (
                        <TableRow key={i}>
                          <TableCell className="font-medium text-sm">{monthLabel}</TableCell>
                          <TableCell className="text-right text-sm font-mono">{fmt(rfPred, 0)}</TableCell>
                          <TableCell className="text-right text-sm font-mono">{fmt(xgbPred, 0)}</TableCell>
                          <TableCell className="text-right text-sm font-mono font-semibold">{fmt((rfPred + xgbPred) / 2, 0)}</TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ═══════ 7. ANOMALY DETECTION — FLAGGED INVOICES ═══════ */}
      <div>
        <SectionHeader icon={ShieldAlert} title="Anomaly Detection — Flagged Invoices" description={`IsolationForest detected ${anomalies.flagged_ids.length} suspicious invoice(s)`} />
        <Card className="animate-fade-in">
          <CardContent className="p-0">
            {anomalies.flagged_invoices.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Status</TableHead>
                    <TableHead>Invoice #</TableHead>
                    <TableHead>Supplier</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead>Payment Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {anomalies.flagged_invoices.map((inv: FlaggedInvoice) => (
                    <TableRow key={inv.id} className="bg-red-500/5 hover:bg-red-500/10">
                      <TableCell>
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-red-500/15 text-red-600 border border-red-500/30">
                          <AlertTriangle className="h-3 w-3" /> FLAGGED
                        </span>
                      </TableCell>
                      <TableCell className="font-mono text-sm font-medium">{inv.invoice_number ?? `#${inv.id}`}</TableCell>
                      <TableCell className="text-sm">{inv.supplier_name ?? "Unknown"}</TableCell>
                      <TableCell className="text-sm capitalize">{inv.type?.replace(/_/g, " ") ?? "—"}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">{inv.invoice_date ?? "—"}</TableCell>
                      <TableCell className="text-right text-sm font-mono font-semibold">{fmt(inv.total_amount ?? 0, 2)}</TableCell>
                      <TableCell className="text-sm capitalize">{inv.status ?? "—"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <div className="p-8 text-center">
                <FileText className="h-10 w-10 mx-auto text-emerald-500/60 mb-3" />
                <p className="text-sm font-medium text-emerald-600">No Anomalies Detected</p>
                <p className="text-xs text-muted-foreground mt-1">All invoices passed the IsolationForest anomaly detection</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ═══════ 8. FEATURE DATA TABLE ═══════ */}
      <div>
        <SectionHeader icon={BarChart3} title="Raw Feature Data" description={`Complete feature pipeline output — ${features.length} months × ${features.length > 0 ? Object.keys(features[0]).length : 0} features`} />
        <Card className="animate-fade-in">
          <CardContent className="p-0 overflow-x-auto">
            {features.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="sticky left-0 bg-card z-10">Month</TableHead>
                    <TableHead className="text-right">Revenue</TableHead>
                    <TableHead className="text-right">COGS</TableHead>
                    <TableHead className="text-right">Expenses</TableHead>
                    <TableHead className="text-right">Net Profit</TableHead>
                    <TableHead className="text-right">Gross Margin</TableHead>
                    <TableHead className="text-right">DSO Days</TableHead>
                    <TableHead className="text-right">Overdue %</TableHead>
                    <TableHead className="text-right">Invoices</TableHead>
                    <TableHead className="text-right">Customers</TableHead>
                    <TableHead className="text-right">Top1 Cust %</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {features.map((row: Record<string, unknown>, i: number) => (
                    <TableRow key={i}>
                      <TableCell className="font-medium text-sm sticky left-0 bg-card">{row.month as string}</TableCell>
                      <TableCell className="text-right text-sm font-mono">{fmt(Number(row.monthly_revenue) || 0, 0)}</TableCell>
                      <TableCell className="text-right text-sm font-mono">{fmt(Number(row.total_cogs) || 0, 0)}</TableCell>
                      <TableCell className="text-right text-sm font-mono">{fmt(Number(row.total_expenses) || 0, 0)}</TableCell>
                      <TableCell className="text-right text-sm font-mono font-semibold">{fmt(Number(row.net_profit) || 0, 0)}</TableCell>
                      <TableCell className="text-right text-sm">{fmtPct(Number(row.gross_margin))}</TableCell>
                      <TableCell className="text-right text-sm">{fmt(Number(row.dso_days) || 0, 1)}</TableCell>
                      <TableCell className="text-right text-sm">{fmtPct(Number(row.overdue_ratio))}</TableCell>
                      <TableCell className="text-right text-sm">{fmt(Number(row.invoice_count) || 0)}</TableCell>
                      <TableCell className="text-right text-sm">{fmt(Number(row.unique_customers) || 0)}</TableCell>
                      <TableCell className="text-right text-sm">{fmtPct(Number(row.top1_customer_pct))}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <div className="p-8 text-center text-sm text-muted-foreground">No features data available</div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Print footer */}
      <div className="hidden print:block text-center text-xs text-muted-foreground border-t pt-4 mt-8">
        <p>Generated by Audit Agent — AI Financial Intelligence Report</p>
        <p>Report Date: {new Date(data.generated_at).toLocaleDateString()}</p>
      </div>
    </div>
  );
}
