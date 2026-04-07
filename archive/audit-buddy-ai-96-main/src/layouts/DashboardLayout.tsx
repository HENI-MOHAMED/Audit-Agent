import { SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/AppSidebar";
import { AppHeader } from "@/components/AppHeader";
import { Outlet, useLocation } from "react-router-dom";
 import { useEffect } from "react";
import Chat from "@/pages/Chat";
import Audit from "@/pages/Audit";
import { useSessionStore } from "@/stores/sessionStore";
import { exitConversation } from "@/services/api";

export function DashboardLayout() {
  const location = useLocation();
  const isChat = location.pathname === "/chat";
  const isAudit = location.pathname === "/audit";
  
  const sessionId = useSessionStore((state) => state.sessionId);

  useEffect(() => {
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (sessionId) {
        exitConversation(sessionId).catch(console.error);
      }
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [sessionId]);

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full">
        <AppSidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <AppHeader />
          <main className="flex-1 p-6 overflow-auto relative flex flex-col">
            <div className={(!isChat && !isAudit) ? "flex-1 flex flex-col" : "hidden"}>
              <Outlet />
            </div>
            
            <div className={isChat ? "flex-1 flex flex-col" : "hidden"}>
              <Chat />
            </div>

            <div className={isAudit ? "flex-1 flex flex-col" : "hidden"}>
              <Audit />
            </div>
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
}
