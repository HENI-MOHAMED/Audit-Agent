import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, Save, Eye, EyeOff } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getConfig, updateConfig } from "@/services/api";
import { useState, useEffect } from "react";
import { useToast } from "@/hooks/use-toast";
import { useSessionStore } from "@/stores/sessionStore";
import { exitConversation, createSession } from "@/services/api";
import { useLanguage } from "@/lib/language";

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const { sessionId, setSessionId } = useSessionStore();
  const { language, setLanguage } = useLanguage();

  const { data: config, isLoading } = useQuery({
    queryKey: ["config"],
    queryFn: getConfig,
  });

  const [dbSource, setDbSource] = useState("");
  const [companyName, setCompanyName] = useState("");

  // API Keys
  const [openaiApiKey, setOpenaiApiKey] = useState("");
  const [deepseekApiKey, setDeepseekApiKey] = useState("");

  // Email Configuration
  const [emailAddress, setEmailAddress] = useState("");
  const [emailAppPassword, setEmailAppPassword] = useState("");

  // Database Configuration
  const [odooDbHost, setOdooDbHost] = useState("");
  const [odooDbPort, setOdooDbPort] = useState("");
  const [odooDbName, setOdooDbName] = useState("");
  const [odooDbUser, setOdooDbUser] = useState("");
  const [odooDbPassword, setOdooDbPassword] = useState("");

  // Password visibility toggles
  const [showOpenaiKey, setShowOpenaiKey] = useState(false);
  const [showDeepseekKey, setShowDeepseekKey] = useState(false);
  const [showEmailPassword, setShowEmailPassword] = useState(false);
  const [showDbPassword, setShowDbPassword] = useState(false);

  useEffect(() => {
    if (config) {
      setDbSource(config.db_source);
      setCompanyName(config.company_name);
      setOpenaiApiKey(config.openai_api_key || "");
      setDeepseekApiKey(config.deepseek_api_key || "");
      setEmailAddress(config.email_address || "");
      setEmailAppPassword(config.email_app_password || "");
      setOdooDbHost(config.odoo_db_host || "");
      setOdooDbPort(config.odoo_db_port || "");
      setOdooDbName(config.odoo_db_name || "");
      setOdooDbUser(config.odoo_db_user || "");
      setOdooDbPassword(config.odoo_db_password || "");
    }
  }, [config]);

  const mutation = useMutation({
    mutationFn: () => updateConfig({
      db_source: dbSource,
      company_name: companyName,
      openai_api_key: openaiApiKey,
      deepseek_api_key: deepseekApiKey,
      email_address: emailAddress,
      email_app_password: emailAppPassword,
      odoo_db_host: odooDbHost,
      odoo_db_port: odooDbPort,
      odoo_db_name: odooDbName,
      odoo_db_user: odooDbUser,
      odoo_db_password: odooDbPassword,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["config"] });
      toast({ title: "Settings saved" });
    },
    onError: (e: Error) => {
      toast({ title: "Failed to save", description: e.message, variant: "destructive" });
    },
  });

  const handleNewSession = async () => {
    try {
      if (sessionId) await exitConversation(sessionId);
      const res = await createSession();
      setSessionId(res.session_id);
      toast({ title: "New session created", description: `ID: ${res.session_id.slice(0, 8)}…` });
    } catch (e: any) {
      toast({ title: "Error", description: e.message, variant: "destructive" });
    }
  };

  const handleEndSession = async () => {
    if (!sessionId) return;
    try {
      await exitConversation(sessionId);
      setSessionId(null);
      toast({ title: "Session ended" });
    } catch (e: any) {
      toast({ title: "Error", description: e.message, variant: "destructive" });
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h2 className="text-2xl font-semibold">Settings</h2>
        <p className="text-muted-foreground text-sm">Configure the audit agent</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Language</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <Label className="text-sm">App language</Label>
            <Select value={language} onValueChange={setLanguage}>
              <SelectTrigger className="w-40 h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="en">English</SelectItem>
                <SelectItem value="fr">French</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Backend Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <>
              <div className="flex items-center justify-between">
                <Label className="text-sm">Data Source</Label>
                <Select value={dbSource} onValueChange={setDbSource}>
                  <SelectTrigger className="w-40 h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="odoo">Odoo</SelectItem>
                    <SelectItem value="sap">SAP</SelectItem>
                    <SelectItem value="quickbooks">QuickBooks</SelectItem>
                    <SelectItem value="manual">Manual</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center justify-between">
                <Label className="text-sm">Company Name</Label>
                <Input
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  className="w-48 h-9 text-sm"
                />
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">API Keys</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <>
              <div className="space-y-2">
                <Label className="text-sm">OpenAI API Key</Label>
                <div className="flex items-center gap-2">
                  <Input
                    type={showOpenaiKey ? "text" : "password"}
                    value={openaiApiKey}
                    onChange={(e) => setOpenaiApiKey(e.target.value)}
                    placeholder="sk-..."
                    className="flex-1 h-9 text-sm font-mono"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowOpenaiKey(!showOpenaiKey)}
                  >
                    {showOpenaiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </Button>
                </div>
              </div>
              <div className="space-y-2">
                <Label className="text-sm">DeepSeek API Key</Label>
                <div className="flex items-center gap-2">
                  <Input
                    type={showDeepseekKey ? "text" : "password"}
                    value={deepseekApiKey}
                    onChange={(e) => setDeepseekApiKey(e.target.value)}
                    placeholder="sk-..."
                    className="flex-1 h-9 text-sm font-mono"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowDeepseekKey(!showDeepseekKey)}
                  >
                    {showDeepseekKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Email Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <>
              <div className="space-y-2">
                <Label className="text-sm">Email_address that we are going to use for email and driver files retrieving</Label>
                <Input
                  type="email"
                  value={emailAddress}
                  onChange={(e) => setEmailAddress(e.target.value)}
                  placeholder="your@email.com"
                  className="h-9 text-sm"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-sm">Email App Password</Label>
                <div className="flex items-center gap-2">
                  <Input
                    type={showEmailPassword ? "text" : "password"}
                    value={emailAppPassword}
                    onChange={(e) => setEmailAppPassword(e.target.value)}
                    placeholder="App-specific password"
                    className="flex-1 h-9 text-sm font-mono"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowEmailPassword(!showEmailPassword)}
                  >
                    {showEmailPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  For Gmail, open Google Account &gt; Security &gt; 2-Step Verification &gt; App passwords, then create a password for this application.
                </p>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Database Configuration (Odoo)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-sm">Host</Label>
                  <Input
                    value={odooDbHost}
                    onChange={(e) => setOdooDbHost(e.target.value)}
                    placeholder="localhost"
                    className="h-9 text-sm"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-sm">Port</Label>
                  <Input
                    value={odooDbPort}
                    onChange={(e) => setOdooDbPort(e.target.value)}
                    placeholder="5432"
                    className="h-9 text-sm"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label className="text-sm">Database Name</Label>
                <Input
                  value={odooDbName}
                  onChange={(e) => setOdooDbName(e.target.value)}
                  placeholder="odoo"
                  className="h-9 text-sm"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-sm">Username</Label>
                  <Input
                    value={odooDbUser}
                    onChange={(e) => setOdooDbUser(e.target.value)}
                    placeholder="odoo"
                    className="h-9 text-sm"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-sm">Password</Label>
                  <div className="flex items-center gap-2">
                    <Input
                      type={showDbPassword ? "text" : "password"}
                      value={odooDbPassword}
                      onChange={(e) => setOdooDbPassword(e.target.value)}
                      placeholder="password"
                      className="flex-1 h-9 text-sm"
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowDbPassword(!showDbPassword)}
                    >
                      {showDbPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </Button>
                  </div>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Session</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <Label className="text-sm">Current Session</Label>
              <p className="text-xs text-muted-foreground font-mono mt-0.5">
                {sessionId ? sessionId.slice(0, 12) + "…" : "No active session"}
              </p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={handleNewSession}>
                New Session
              </Button>
              <Button variant="outline" size="sm" onClick={handleEndSession} disabled={!sessionId}>
                End Session
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Notifications</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <Label className="text-sm">Email alerts for critical findings</Label>
            <Switch defaultChecked />
          </div>
          <div className="flex items-center justify-between">
            <Label className="text-sm">Daily audit summary</Label>
            <Switch defaultChecked />
          </div>
          <div className="flex items-center justify-between">
            <Label className="text-sm">New supplier alerts</Label>
            <Switch />
          </div>
        </CardContent>
      </Card>

      <Button onClick={() => mutation.mutate()} disabled={mutation.isPending} className="gap-2">
        {mutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
        Save Settings
      </Button>
    </div>
  );
}
