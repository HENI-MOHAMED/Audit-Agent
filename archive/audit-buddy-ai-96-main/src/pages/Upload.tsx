import { useState, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Upload, FileUp, Loader2, CheckCircle, AlertTriangle, Database, RefreshCw, Mail, Cloud, Sparkles } from "lucide-react";
import { uploadDocs, syncLocalDb, syncEmail } from "@/services/api";
import { useSessionStore } from "@/stores/sessionStore";
import { useToast } from "@/hooks/use-toast";

export default function UploadPage() {
  const { sessionId, setSessionId } = useSessionStore();
  const [uploading, setUploading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [emailSyncing, setEmailSyncing] = useState(false);
  const [emailQuery, setEmailQuery] = useState("");
  const [driveSyncing, setDriveSyncing] = useState(false);
  const [driveQuery, setDriveQuery] = useState("");
  const [uploadResult, setUploadResult] = useState<string | null>(null);
  const [syncResult, setSyncResult] = useState<string | null>(null);
  const [emailSyncResult, setEmailSyncResult] = useState<string | null>(null);
  const [driveSyncResult, setDriveSyncResult] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setUploading(true);
    setUploadResult(null);
    try {
      const res = await uploadDocs(Array.from(files), sessionId ?? undefined);
      if (!sessionId) setSessionId(res.session_id);
      setUploadResult(res.message);
      toast({ title: "Upload complete", description: res.message });
    } catch (err: any) {
      setUploadResult(`Error: ${err.message}`);
      toast({ title: "Upload failed", description: err.message, variant: "destructive" });
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    setSyncResult(null);
    try {
      const res = await syncLocalDb(sessionId ?? undefined);
      if (!sessionId) setSessionId(res.session_id);
      setSyncResult(res.message);
      toast({ title: "DB Sync complete", description: res.message });
    } catch (err: any) {
      setSyncResult(`Error: ${err.message}`);
      toast({ title: "Sync failed", description: err.message, variant: "destructive" });
    } finally {
      setSyncing(false);
    }
  };

  const handleEmailSync = async () => {
    if (!emailQuery.trim()) return;
    setEmailSyncing(true);
    setEmailSyncResult(null);
    try {
      const res = await syncEmail(`From email: ${emailQuery}`, sessionId ?? undefined);
      if (!sessionId) setSessionId(res.session_id);
      setEmailSyncResult(res.message);
      toast({ title: "Email Sync complete", description: res.message });
    } catch (err: any) {
      setEmailSyncResult(`Error: ${err.message}`);
      toast({ title: "Email Sync failed", description: err.message, variant: "destructive" });
    } finally {
      setEmailSyncing(false);
    }
  };

  const handleDriveSync = async () => {
    if (!driveQuery.trim()) return;
    setDriveSyncing(true);
    setDriveSyncResult(null);
    try {
      const res = await syncEmail(`From google drive: ${driveQuery}`, sessionId ?? undefined);
      if (!sessionId) setSessionId(res.session_id);
      setDriveSyncResult(res.message);
      toast({ title: "Drive Sync complete", description: res.message });
    } catch (err: any) {
      setDriveSyncResult(`Error: ${err.message}`);
      toast({ title: "Drive Sync failed", description: err.message, variant: "destructive" });
    } finally {
      setDriveSyncing(false);
    }
  };

  const StatusMessage = ({ result, isError }: { result: string | null; isError?: boolean }) => {
    if (!result) return null;
    const isErr = isError ?? result.startsWith("Error");
    return (
      <div className={`mt-4 p-3 rounded-md flex items-start gap-2.5 text-sm transition-all ${
        isErr 
          ? "bg-red-50 text-red-700 border border-red-100 dark:bg-red-950/30 dark:text-red-400 dark:border-red-900/50" 
          : "bg-emerald-50 text-emerald-700 border border-emerald-100 dark:bg-emerald-950/30 dark:text-emerald-400 dark:border-emerald-900/50"
      }`}>
        {isErr ? <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" /> : <CheckCircle className="h-4 w-4 shrink-0 mt-0.5" />}
        <span className="leading-relaxed">{result}</span>
      </div>
    );
  };

  return (
    <div className="w-full max-w-5xl mx-auto py-8 space-y-10 animate-in fade-in duration-500">
      
      {/* Clean, simple header */}
      <div className="space-y-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">
            Data Sources
          </h1>
          <p className="text-muted-foreground mt-2 text-base max-w-2xl leading-relaxed">
            Connect your systems to import documents and records. Our AI automatically extracts, structures, and categorizes the information to prepare it for your audit.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* Upload Card */}
        <Card className="shadow-sm border-border/60 hover:border-border transition-colors">
          <CardHeader>
            <CardTitle className="flex items-center gap-2.5 text-lg">
              <FileUp className="h-5 w-5 text-muted-foreground" />
              File Upload
            </CardTitle>
            <CardDescription className="text-sm">
              Upload local tax forms, receipts, or spreadsheets.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div
              className="relative border-2 border-dashed border-muted-foreground/20 rounded-xl p-10 flex flex-col items-center justify-center text-center cursor-pointer hover:bg-muted/30 hover:border-muted-foreground/30 transition-all"
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload className="h-8 w-8 text-muted-foreground mb-3" />
              <p className="text-sm font-medium text-foreground">
                Click to browse or drag files here
              </p>
              <p className="text-xs text-muted-foreground mt-1.5">
                PDF, CSV, and Excel (up to 50MB)
              </p>
              
              {uploading && (
                <div className="absolute inset-0 bg-background/90 backdrop-blur-sm flex flex-col items-center justify-center rounded-xl p-4">
                  <Loader2 className="h-6 w-6 text-primary animate-spin mb-2" />
                  <p className="text-sm font-medium text-foreground">Reading documents...</p>
                </div>
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              onChange={handleUpload}
              className="hidden"
              accept=".pdf,.csv,.xlsx,.xls"
            />
            <StatusMessage result={uploadResult} />
          </CardContent>
        </Card>

        {/* Database Match Card */}
        <Card className="shadow-sm border-border/60 hover:border-border transition-colors flex flex-col">
          <CardHeader>
            <CardTitle className="flex items-center gap-2.5 text-lg">
              <Database className="h-5 w-5 text-muted-foreground" />
              Database Sync
            </CardTitle>
            <CardDescription className="text-sm">
              Synchronize direct records from your ERP system.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col">
            <div className="flex-1 flex flex-col justify-between gap-6">
              <div className="bg-muted/40 rounded-lg p-5 border border-border/50">
                <p className="text-sm text-foreground/80 leading-relaxed">
                  Pulls the latest financial entries from your connected source. The AI will cross-reference your raw data and align them to the central audit terminology.
                </p>
              </div>
              <Button 
                onClick={handleSync} 
                disabled={syncing} 
                variant="secondary"
                className="w-full font-medium"
              >
                {syncing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}
                Sync Records
              </Button>
            </div>
            <StatusMessage result={syncResult} />
          </CardContent>
        </Card>

        {/* Email App Card */}
        <Card className="shadow-sm border-border/60 hover:border-border transition-colors">
          <CardHeader>
            <CardTitle className="flex items-center gap-2.5 text-lg">
              <Mail className="h-5 w-5 text-muted-foreground" />
              Email Search
            </CardTitle>
            <CardDescription className="text-sm">
              Find and import invoices directly from your inbox.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-4">
              <p className="text-sm text-muted-foreground">
                Enter a search term and we'll securely scan for related attachments.
              </p>
              <div className="flex flex-col gap-3">
                <Input
                  value={emailQuery}
                  onChange={(e) => setEmailQuery(e.target.value)}
                  placeholder="e.g., 'October AWS invoices'"
                  className="bg-background"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && emailQuery.trim() && !emailSyncing) handleEmailSync();
                  }}
                />
                <Button 
                  onClick={handleEmailSync} 
                  disabled={emailSyncing || !emailQuery.trim()} 
                  className="w-full font-medium text-white"
                >
                  {emailSyncing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Mail className="h-4 w-4 mr-2" />}
                  Locate in Email
                </Button>
              </div>
            </div>
            <StatusMessage result={emailSyncResult} />
          </CardContent>
        </Card>

        {/* Google Drive Card */}
        <Card className="shadow-sm border-border/60 hover:border-border transition-colors">
          <CardHeader>
            <CardTitle className="flex items-center gap-2.5 text-lg">
              <Cloud className="h-5 w-5 text-muted-foreground" />
              Google Drive
            </CardTitle>
            <CardDescription className="text-sm">
              Import audit materials from your cloud storage.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-4">
              <p className="text-sm text-muted-foreground">
                Describe the folder or documents you're looking for to import them.
              </p>
              <div className="flex flex-col gap-3">
                <Input
                  value={driveQuery}
                  onChange={(e) => setDriveQuery(e.target.value)}
                  placeholder="e.g., 'Q3 Legal forms'"
                  className="bg-background"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && driveQuery.trim() && !driveSyncing) handleDriveSync();
                  }}
                />
                <Button 
                  onClick={handleDriveSync} 
                  disabled={driveSyncing || !driveQuery.trim()} 
                  className="w-full font-medium text-white"
                >
                  {driveSyncing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Cloud className="h-4 w-4 mr-2" />}
                  Import from Drive
                </Button>
              </div>
            </div>
            <StatusMessage result={driveSyncResult} />
          </CardContent>
        </Card>

      </div>
    </div>
  );
}
