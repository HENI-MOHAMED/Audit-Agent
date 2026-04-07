import { Bell, Search, Moon, Sun, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { useState } from "react";
import { useSessionStore } from "@/stores/sessionStore";
import { Badge } from "@/components/ui/badge";
import { useNavigate } from "react-router-dom";

export function AppHeader() {
  const [darkMode, setDarkMode] = useState(false);
  const { sessionId } = useSessionStore();
  const navigate = useNavigate();

  const toggleDark = () => {
    setDarkMode(!darkMode);
    document.documentElement.classList.toggle("dark");
  };

  const handleSignOut = () => {
    localStorage.removeItem("userRole");
    navigate("/login");
  };

  return (
    <header className="h-14 border-b border-border bg-card/50 backdrop-blur-sm flex items-center justify-between px-4 sticky top-0 z-10">
      <div className="flex items-center gap-3">
        <SidebarTrigger />
        <div className="relative hidden sm:block">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search invoices, suppliers..."
            className="pl-9 w-64 h-9 bg-secondary border-none text-sm"
          />
        </div>
      </div>
      <div className="flex items-center gap-2">
        {sessionId && (
          <Badge variant="outline" className="text-xs font-mono hidden md:inline-flex">
            Session: {sessionId.slice(0, 8)}…
          </Badge>
        )}
        <Button variant="ghost" size="icon" className="h-9 w-9" onClick={toggleDark}>
          {darkMode ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
        <Button variant="ghost" size="icon" className="h-9 w-9 relative">
          <Bell className="h-4 w-4" />
          <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-destructive" />
        </Button>
        <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center text-sm font-medium text-primary ml-1">
          JD
        </div>
        <Button variant="ghost" size="icon" className="h-9 w-9 ml-2" onClick={handleSignOut} title="Sign Out">
          <LogOut className="h-4 w-4 text-red-500" />
        </Button>
      </div>
    </header>
  );
}
