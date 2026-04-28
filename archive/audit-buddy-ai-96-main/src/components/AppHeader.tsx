import { Bell, Search, Moon, Sun, LogOut, Check, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { useState } from "react";
import { useSessionStore } from "@/stores/sessionStore";
import { useNotificationStore } from "@/stores/notificationStore";
import { Badge } from "@/components/ui/badge";
import { useNavigate } from "react-router-dom";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";

export function AppHeader() {
  const [darkMode, setDarkMode] = useState(false);
  const { sessionId } = useSessionStore();
  const { notifications, markAsRead, markAllAsRead, removeNotification, clearAll } = useNotificationStore();
  const navigate = useNavigate();

  const unreadCount = notifications.filter(n => !n.read).length;

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
        
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="ghost" size="icon" className="h-9 w-9 relative">
              <Bell className="h-4 w-4" />
              {unreadCount > 0 && (
                <span className="absolute top-1.5 right-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-[9px] font-medium text-destructive-foreground">
                  {unreadCount > 99 ? '99+' : unreadCount}
                </span>
              )}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-80 p-0" align="end">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <h4 className="font-semibold text-sm">Notifications</h4>
              {notifications.length > 0 && (
                <div className="flex items-center gap-2">
                  <Button variant="ghost" size="sm" className="h-auto p-1 text-xs" onClick={markAllAsRead}>
                    <Check className="h-3 w-3 mr-1" /> Mark all read
                  </Button>
                  <Button variant="ghost" size="sm" className="h-auto p-1 text-xs text-destructive hover:text-destructive" onClick={clearAll}>
                    <Trash2 className="h-3 w-3 mr-1" /> Clear
                  </Button>
                </div>
              )}
            </div>
            <ScrollArea className="h-96">
              {notifications.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 px-4 text-center text-muted-foreground">
                  <Bell className="h-8 w-8 mb-3 opacity-20" />
                  <p className="text-sm font-medium">No notifications yet</p>
                  <p className="text-xs mt-1">We'll let you know when something arrives.</p>
                </div>
              ) : (
                <div className="flex flex-col divide-y divide-border">
                  {notifications.map((notification) => (
                    <div 
                      key={notification.id} 
                      className={`group relative flex flex-col gap-1 p-4 transition-colors hover:bg-muted/50 ${!notification.read ? "bg-muted/30" : ""}`}
                    >
                      {!notification.read && (
                        <div className="absolute left-2 top-5 h-1.5 w-1.5 rounded-full bg-blue-500" />
                      )}
                      
                      <div className="flex items-start justify-between pl-4 gap-2">
                        <div className="flex-1 space-y-1">
                          <p className="text-sm font-medium leading-none">
                            {notification.title}
                          </p>
                          {notification.description && (
                            <p className="text-xs text-muted-foreground line-clamp-2">
                              {notification.description}
                            </p>
                          )}
                          <p className="text-[10px] text-muted-foreground pt-1">
                            {new Date(notification.date).toLocaleString()}
                          </p>
                        </div>
                        <div className="flex opacity-0 group-hover:opacity-100 transition-opacity sm:opacity-100">
                          {!notification.read && (
                            <Button 
                              variant="ghost" 
                              size="icon" 
                              className="h-6 w-6 text-muted-foreground hover:text-primary" 
                              onClick={() => markAsRead(notification.id)}
                              title="Mark as read"
                            >
                              <Check className="h-3.5 w-3.5" />
                            </Button>
                          )}
                          <Button 
                            variant="ghost" 
                            size="icon" 
                            className="h-6 w-6 text-muted-foreground hover:text-destructive" 
                            onClick={() => removeNotification(notification.id)}
                            title="Delete notification"
                          >
                            <X className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </PopoverContent>
        </Popover>

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
