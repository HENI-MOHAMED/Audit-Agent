import { useInvoices, useInvoiceLineItems, useInvoiceAuditResults } from "@/services/queries";
import { StatusBadge, RiskBadge } from "@/components/StatusBadges";
import { TableSkeleton } from "@/components/Skeletons";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useState } from "react";
import type { Invoice } from "@/types";

function InvoiceDetailPanel({ invoice, open, onClose }: { invoice: Invoice | null; open: boolean; onClose: () => void }) {
  const { data: lineItems, isLoading: linesLoading } = useInvoiceLineItems(invoice?.id ?? 0);
  const { data: auditResults, isLoading: auditLoading } = useInvoiceAuditResults(invoice?.id ?? 0);

  if (!invoice) return null;
  return (
    <Sheet open={open} onOpenChange={onClose}>
      <SheetContent className="sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-3">
            {invoice.invoice_number ?? `#${invoice.id}`}
            <StatusBadge status={invoice.status} />
          </SheetTitle>
        </SheetHeader>
        <div className="mt-6 space-y-6">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div><p className="text-muted-foreground">Supplier</p><p className="font-medium">{invoice.supplier_name ?? "N/A"}</p></div>
            <div><p className="text-muted-foreground">Date</p><p className="font-medium">{invoice.invoice_date ?? "N/A"}</p></div>
            <div><p className="text-muted-foreground">Total</p><p className="font-medium">{(invoice.total_amount ?? 0).toLocaleString()} {invoice.currency ?? ""}</p></div>
            <div><p className="text-muted-foreground">Tax</p><p className="font-medium">{(invoice.total_tax ?? 0).toLocaleString()} {invoice.currency ?? ""}</p></div>
            <div><p className="text-muted-foreground">Type</p><p className="font-medium capitalize">{invoice.type ?? "N/A"}</p></div>
            <div><p className="text-muted-foreground">Due Date</p><p className="font-medium">{invoice.due_date ?? "N/A"}</p></div>
          </div>

          <div>
            <h4 className="text-sm font-medium mb-2">Line Items</h4>
            {linesLoading ? (
              <TableSkeleton rows={3} cols={4} />
            ) : lineItems.length > 0 ? (
              <div className="rounded-lg border">
                <Table>
                  <TableHeader><TableRow><TableHead>Product / Description</TableHead><TableHead className="text-right">Qty</TableHead><TableHead className="text-right">Price</TableHead><TableHead className="text-right">Subtotal</TableHead></TableRow></TableHeader>
                  <TableBody>
                    {lineItems.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell className="text-sm">{item.product_name ?? item.description ?? "N/A"}</TableCell>
                        <TableCell className="text-right text-sm">{item.quantity ?? 0}</TableCell>
                        <TableCell className="text-right text-sm">{(item.unit_price ?? 0).toLocaleString()}</TableCell>
                        <TableCell className="text-right text-sm">{(item.subtotal ?? 0).toLocaleString()}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No line items</p>
            )}
          </div>

          <div>
            <h4 className="text-sm font-medium mb-2">Audit Results</h4>
            {auditLoading ? (
              <TableSkeleton rows={2} cols={3} />
            ) : auditResults.length > 0 ? (
              <div className="space-y-2">
                {auditResults.map((r) => (
                  <div key={r.id} className="flex items-start gap-3 p-3 rounded-lg bg-secondary/50">
                    <RiskBadge level={r.risk_level} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium">
                        {r.rule_name ? String(r.rule_name).replace(/_/g, " ").toUpperCase() : "AUDIT CHECK"}
                      </p>
                      <div className="text-xs text-muted-foreground mt-1">
                        {(() => {
                          let issues: string | string[] = r.issue_detected;
                          if (typeof issues === "string") {
                            try {
                              issues = JSON.parse(issues);
                            } catch (e) {
                              if (typeof issues === "string" && issues.trim().startsWith("[") && issues.trim().endsWith("]")) {
                                issues = issues
                                  .trim()
                                  .slice(1, -1)
                                  .split(/',\s*'|",\s*"|',\s*"|",\s*'/)
                                  .map((s) => s.replace(/(^["'])|(["']$)/g, ""));
                              } else {
                                issues = [typeof issues === "string" ? issues : ""];
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
                      {r.recommendation && <p className="text-xs text-muted-foreground mt-1">{r.recommendation}</p>}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No audit results for this invoice</p>
            )}
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}

export default function InvoicesPage() {
  const { data: invoices, isLoading } = useInvoices();
  const [selected, setSelected] = useState<Invoice | null>(null);

  return (
    <div className="space-y-6">
      <div><h2 className="text-2xl font-semibold">Invoices</h2><p className="text-muted-foreground text-sm">Monitor and analyze invoice data</p></div>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6"><TableSkeleton rows={6} cols={7} /></div>
          ) : invoices.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Invoice #</TableHead><TableHead>Supplier</TableHead><TableHead>Type</TableHead><TableHead>Date</TableHead>
                  <TableHead className="text-right">Amount</TableHead><TableHead className="text-right">Tax</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invoices.map((inv) => (
                  <TableRow key={inv.id} className="cursor-pointer hover:bg-muted/50" onClick={() => setSelected(inv)}>
                    <TableCell className="font-medium text-sm">{inv.invoice_number ?? `#${inv.id}`}</TableCell>
                    <TableCell className="text-sm">{inv.supplier_name ?? "N/A"}</TableCell>
                    <TableCell className="text-sm capitalize text-muted-foreground">{inv.type ?? "N/A"}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{inv.invoice_date ?? "N/A"}</TableCell>
                    <TableCell className="text-right text-sm">{(inv.total_amount ?? 0).toLocaleString()}</TableCell>
                    <TableCell className="text-right text-sm text-muted-foreground">{(inv.total_tax ?? 0).toLocaleString()}</TableCell>
                    <TableCell><StatusBadge status={inv.status} /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="p-8 text-center text-muted-foreground text-sm">No invoices found. Sync the local DB first.</div>
          )}
        </CardContent>
      </Card>

      <InvoiceDetailPanel invoice={selected} open={!!selected} onClose={() => setSelected(null)} />
    </div>
  );
}
