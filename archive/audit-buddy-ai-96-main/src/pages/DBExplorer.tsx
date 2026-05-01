import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useDbTables, useDbSchema, useDbQuery, executeSql } from "@/hooks/useWebSocketDB";
import { Database, Search, Loader2, AlertTriangle, RefreshCw, Wand2, TerminalSquare } from "lucide-react";
import { syncTerminology } from "@/services/api";
import { Textarea } from "@/components/ui/textarea";

export default function DBExplorerPage() {
  const { tables, loading: tablesLoading, error: tablesError, refresh } = useDbTables();
  const [selectedTable, setSelectedTable] = useState("");
  const [customSql, setCustomSql] = useState("");
  const [activeSql, setActiveSql] = useState("");
  
  // DDL / Arbitrary script state
  const [scriptSql, setScriptSql] = useState("");
  const [scriptResult, setScriptResult] = useState<{ msg?: string; error?: string } | null>(null);
  const [scriptRunning, setScriptRunning] = useState(false);
  const [terminologyLoading, setTerminologyLoading] = useState(false);

  const handleTerminologySync = async () => {
    try {
      setTerminologyLoading(true);
      await syncTerminology();
      // Optional: you could refresh data here if terminology affects tables, or just show a success message
      refresh();
    } catch (e) {
      console.error("Error executing terminology agent:", e);
    } finally {
      setTerminologyLoading(false);
    }
  };

  const { schema, loading: schemaLoading } = useDbSchema(selectedTable);

  const defaultSql = selectedTable ? `SELECT * FROM ${selectedTable} LIMIT 50` : "";
  const { data, loading: queryLoading, error: queryError, count } = useDbQuery(
    activeSql || defaultSql,
    !!(activeSql || selectedTable)
  );

  const handleTableSelect = (table: string) => {
    setSelectedTable(table);
    setActiveSql("");
    setCustomSql("");
  };

  const handleCustomQuery = () => {
    if (customSql.trim()) setActiveSql(customSql.trim());
  };

  const handleRunScript = async () => {
    if (!scriptSql.trim()) return;
    setScriptRunning(true);
    setScriptResult(null);
    try {
      const res = await executeSql(scriptSql);
      if (res.ok) {
        setScriptResult({ msg: `Success! Rows affected: ${res.count ?? "unknown"}` });
        refresh(); // Refresh tables in case it was a CREATE/DROP
      } else {
        setScriptResult({ error: (res as any).error || "Unknown error occurred" });
      }
    } catch (e: any) {
      setScriptResult({ error: e.message });
    } finally {
      setScriptRunning(false);
    }
  };

  const columns = data.length > 0 ? Object.keys(data[0] as Record<string, unknown>) : schema.map((s) => s.name);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Database Explorer</h2>
          <p className="text-muted-foreground text-sm">Browse the local audit SQLite database</p>
        </div>
        <div className="flex items-center gap-2">
          <Button 
            variant="outline" 
            size="sm" 
            className="gap-2" 
            onClick={handleTerminologySync}
            disabled={terminologyLoading}
          >
            {terminologyLoading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Wand2 className="h-3.5 w-3.5" />
            )}
            Terminology Agent
          </Button>
          <Button variant="outline" size="sm" className="gap-2" onClick={refresh}>
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </Button>
        </div>
      </div>

      {tablesError && (
        <Card className="border-destructive/50">
          <CardContent className="py-4 flex items-center gap-3 text-destructive">
            <AlertTriangle className="h-5 w-5" />
            <p className="text-sm">{tablesError} — Make sure the backend is running and /local_db has been called.</p>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Tables sidebar */}
        <Card className="lg:col-span-1">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Database className="h-4 w-4" />
              Tables
              {tablesLoading && <Loader2 className="h-3 w-3 animate-spin" />}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            {tables.map((t) => (
              <button
                key={t}
                onClick={() => handleTableSelect(t)}
                className={`w-full text-left text-sm px-3 py-2 rounded-md transition-colors ${
                  selectedTable === t
                    ? "bg-primary/10 text-primary font-medium"
                    : "text-foreground hover:bg-secondary"
                }`}
              >
                {t}
              </button>
            ))}
            {!tablesLoading && tables.length === 0 && !tablesError && (
              <p className="text-xs text-muted-foreground p-3">No tables found. Run DB Sync first.</p>
            )}
          </CardContent>
        </Card>

        {/* Query area */}
        <div className="lg:col-span-3 space-y-4">
          {/* Schema */}
          {selectedTable && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">
                  Schema: <span className="font-mono">{selectedTable}</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {schemaLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {schema.map((col) => (
                      <Badge key={col.name} variant="outline" className="font-mono text-xs">
                        {col.name} <span className="text-muted-foreground ml-1">{col.type}</span>
                      </Badge>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Custom SQL */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Search className="h-4 w-4 text-muted-foreground" />
                Query Data (SELECT)
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-2">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleCustomQuery();
                }}
                className="flex gap-2"
              >
                <Input
                  value={customSql}
                  onChange={(e) => setCustomSql(e.target.value)}
                  placeholder="SELECT * FROM … LIMIT 50"
                  className="flex-1 font-mono text-sm h-10"
                />
                <Button type="submit" className="gap-2 h-10" disabled={!customSql.trim()}>
                  Run Query
                </Button>
              </form>
            </CardContent>
          </Card>

          {/* DDL/DML Scripts */}
          {selectedTable === "sqlite_sequence" && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <TerminalSquare className="h-4 w-4 text-muted-foreground" />
                  Run SQL Script (CREATE / DELETE / UPDATE)
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-2 space-y-3">
                <Textarea
                  value={scriptSql}
                  onChange={(e) => setScriptSql(e.target.value)}
                  placeholder="CREATE TABLE ...; or DROP TABLE ...;"
                  className="font-mono text-sm min-h-[100px]"
                />
                <div className="flex items-center gap-4">
                  <Button 
                    onClick={handleRunScript} 
                    disabled={!scriptSql.trim() || scriptRunning} 
                    className="gap-2 h-9"
                    variant="secondary"
                  >
                    {scriptRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : "Execute Script"}
                  </Button>
                  {scriptResult && (
                    <div className={`text-sm ${scriptResult.error ? "text-destructive" : "text-green-600"}`}>
                      {scriptResult.error || scriptResult.msg}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Results */}
          {queryError && (
            <Card className="border-destructive/50">
              <CardContent className="py-4 text-destructive text-sm">{queryError}</CardContent>
            </Card>
          )}

          {(activeSql || selectedTable) && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">
                  Results {count > 0 && `(${count} rows)`}
                  {queryLoading && <Loader2 className="h-3 w-3 animate-spin inline ml-2" />}
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0 overflow-x-auto">
                {data.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        {columns.map((col) => (
                          <TableHead key={col} className="whitespace-nowrap font-mono text-xs">
                            {col}
                          </TableHead>
                        ))}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {data.map((row: any, i) => (
                        <TableRow key={i}>
                          {columns.map((col) => (
                            <TableCell key={col} className="text-xs max-w-[200px] truncate">
                              {row[col] != null ? String(row[col]) : <span className="text-muted-foreground">null</span>}
                            </TableCell>
                          ))}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  !queryLoading && (
                    <div className="p-8 text-center text-muted-foreground text-sm">No data</div>
                  )
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
