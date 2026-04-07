import { useState, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Checkbox } from "@/components/ui/checkbox";
import { Play, Loader2, AlertTriangle, CheckCircle, FileUp, X, Database } from "lucide-react";
import { runAudit, uploadDocs } from "@/services/api";
import { useInvoices } from "@/services/queries";
import { useSessionStore } from "@/stores/sessionStore";
import type { AuditResult } from "@/services/api";
import { stringify } from "querystring";

export default function AuditPage() {
  const { sessionId, setSessionId } = useSessionStore();
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<AuditResult[]>([]);
  const [error, setError] = useState<string | null>(null);

  // File upload state
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // DB selection state
  const { data: invoicesData, isLoading: invoicesLoading } = useInvoices();
  const [selectedInvoices, setSelectedInvoices] = useState<Set<number>>(new Set());

  const handleAudit = async (queryOverride?: string) => {
    const finalQuery = queryOverride || query;
    if (!finalQuery.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const res = await runAudit(finalQuery.trim(), sessionId ?? undefined);
      if (!sessionId) setSessionId(res.session_id);
      setResults(res.results);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) {
      setSelectedFiles((prev) => [...prev, ...Array.from(e.target.files!)]);
    }
  };

  const removeFile = (idx: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleUploadAndAudit = async () => {
    if (selectedFiles.length === 0 || loading) return;
    setLoading(true);
    setError(null);
    try {
      // Tell the Audit agent about the files to audit
      const filePaths = selectedFiles.map(f => f.name).join('|');
      const message = `Audit these invoices: ${filePaths}`;
      const auditRes = await runAudit(message, sessionId ?? undefined);
      if (!sessionId && auditRes.session_id) setSessionId(auditRes.session_id);
      setResults(auditRes.results);

      // Then upload the chosen files to the server
      // const uploadRes = await uploadDocs(selectedFiles, sessionId ?? undefined);
      // if (!sessionId && uploadRes.session_id) setSessionId(uploadRes.session_id);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const toggleInvoice = (id: number) => {
    const next = new Set(selectedInvoices);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedInvoices(next);
  };

  const handleDbAudit = async () => {
    if (selectedInvoices.size === 0 || loading) return;
    
    const invoiceNumbers = invoicesData
      ?.filter(inv => selectedInvoices.has(inv.id))
      .map(inv => inv.invoice_number || inv.id)
      .join('|');

    if (!invoiceNumbers) return;
    
    const message = `Audit these invoices: ${invoiceNumbers}`;
    await handleAudit(message);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold">Run Audit</h2>
        <p className="text-muted-foreground text-sm">Trigger AI-powered invoice audits</p>
      </div>

      <Tabs defaultValue="query" className="w-full">
        <TabsList className="mb-4">
          <TabsTrigger value="query">Custom Query</TabsTrigger>
          <TabsTrigger value="upload">Upload Invoices</TabsTrigger>
          <TabsTrigger value="db">Select from DB</TabsTrigger>
        </TabsList>

        <TabsContent value="query">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Audit Query</CardTitle>
            </CardHeader>
            <CardContent>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleAudit();
                }}
                className="flex gap-3"
              >
                <Input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="e.g., Audit all invoices from last month"
                  className="flex-1 h-10"
                  disabled={loading}
                />
                <Button type="submit" className="gap-2 h-10" disabled={loading || !query.trim()}>
                  {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                  Run Audit
                </Button>
              </form>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="upload">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Upload & Audit</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div
                className="border-2 border-dashed border-border rounded-lg p-8 text-center cursor-pointer hover:border-primary/50 transition-colors"
                onClick={() => fileInputRef.current?.click()}
              >
                <FileUp className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                <p className="text-sm text-muted-foreground">
                  Click to select files or drag & drop
                </p>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                onChange={handleFileSelect}
                className="hidden"
                accept=".pdf,.png,.jpg,.jpeg"
              />

              {selectedFiles.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-sm font-medium">Selected Files ({selectedFiles.length})</h3>
                  <div className="flex flex-col gap-2">
                    {selectedFiles.map((f, i) => (
                      <div key={i} className="flex justify-between items-center text-sm p-2 border rounded-md">
                        <span className="truncate max-w-[250px]" title={f.name}>{f.name}</span>
                        <button className="text-muted-foreground hover:text-destructive" onClick={() => removeFile(i)}>
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                  <Button onClick={handleUploadAndAudit} disabled={loading || selectedFiles.length === 0} className="w-full gap-2">
                    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                    Upload & Run Audit ({selectedFiles.length} files)
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="db">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Select from Database</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {invoicesLoading ? (
                <div className="flex items-center justify-center p-4">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : invoicesData && invoicesData.length > 0 ? (
                <>
                  <div className="max-h-60 overflow-y-auto border rounded-md p-2 space-y-2">
                    {invoicesData.map((inv) => (
                      <div key={inv.id} className="flex items-center gap-3 p-2 hover:bg-muted/50 rounded-md">
                        <Checkbox 
                          id={`inv-${inv.id}`} 
                          checked={selectedInvoices.has(inv.id)} 
                          onCheckedChange={() => toggleInvoice(inv.id)} 
                        />
                        <label htmlFor={`inv-${inv.id}`} className="flex-1 cursor-pointer text-sm">
                          <span className="font-medium">{inv.invoice_number || `Invoice #${inv.id}`}</span>
                          <span className="text-muted-foreground ml-2">
                            {inv.supplier_name ? `- ${inv.supplier_name}` : ''}
                          </span>
                        </label>
                      </div>
                    ))}
                  </div>
                  <Button onClick={handleDbAudit} disabled={loading || selectedInvoices.size === 0} className="w-full gap-2">
                    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                    Run Audit ({selectedInvoices.size} selected)
                  </Button>
                </>
              ) : (
                <div className="text-center py-4 text-sm text-muted-foreground flex flex-col items-center">
                  <Database className="h-6 w-6 mb-2 opacity-50" />
                  No invoices found in database.
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {error && (
        <Card className="border-destructive/50">
          <CardContent className="py-4 flex items-center gap-3 text-destructive">
            <AlertTriangle className="h-5 w-5" />
            <p className="text-sm">{error}</p>
          </CardContent>
        </Card>
      )}

      {results.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">
              Audit Results ({results.length} invoices)
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Invoice #</TableHead>
                  <TableHead>State</TableHead>
                  <TableHead>Note</TableHead>
                  <TableHead>Checks</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {results.map((r, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-mono text-sm font-medium">
                      {r.invoice_number}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={
                          r.state === "passed" || r.state === "verified"
                            ? "bg-risk-low/10 text-risk-low border-risk-low/20"
                            : r.state === "failed" || r.state === "high_risk"
                            ? "bg-risk-high/10 text-risk-high border-risk-high/20"
                            : "bg-risk-medium/10 text-risk-medium border-risk-medium/20"
                        }
                      >
                        {r.state}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm max-w-xs truncate">{r.note}</TableCell>
                    <TableCell className="text-sm">
                      {Array.isArray(r.audits_results) ? (
                        <div className="flex gap-1">
                          {r.audits_results.map((check: any, j: number) => (
                            <span
                              key={j}
                              title={check.description || check.check_type}
                              className={`inline-flex items-center justify-center h-5 w-5 rounded-full ${
                                check.status === "pass"
                                  ? "bg-risk-low/20 text-risk-low"
                                  : check.status === "fail"
                                  ? "bg-risk-high/20 text-risk-high"
                                  : "bg-risk-medium/20 text-risk-medium"
                              }`}
                            >
                              {check.status === "pass" ? (
                                <CheckCircle className="h-3 w-3" />
                              ) : (
                                <AlertTriangle className="h-3 w-3" />
                              )}
                            </span>
                          ))}
                        </div>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
