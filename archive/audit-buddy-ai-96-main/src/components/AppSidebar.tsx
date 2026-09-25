import {
  LayoutDashboard, FileText, Users, Package, Warehouse,
  ClipboardList, FolderOpen, BarChart3, Settings, Shield,
  MessageSquare, Search as SearchIcon, Upload, Database, ShoppingCart
} from "lucide-react";
import { NavLink } from "@/components/NavLink";
import { useLocation } from "react-router-dom";
import {
  Sidebar, SidebarContent, SidebarGroup, SidebarGroupContent,
  SidebarGroupLabel, SidebarMenu, SidebarMenuButton, SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { useLanguage } from "@/lib/language";

const mainItems = [
  { title: "Dashboard", url: "/", icon: LayoutDashboard },
  { title: "AI Chat", url: "/chat", icon: MessageSquare },
  { title: "Run Audit", url: "/audit", icon: SearchIcon },
  { title: "Supplier Requests", url: "/supplier-requests", icon: FileText },
  { title: "Invoices", url: "/invoices", icon: FileText },
  { title: "Suppliers", url: "/suppliers", icon: Users },
  { title: "Products", url: "/products", icon: Package },
  { title: "Place Order", url: "/place-order", icon: ShoppingCart },
  { title: "Inventory", url: "/inventory", icon: Warehouse },
];

const systemItems = [
  { title: "Documents", url: "/documents", icon: FolderOpen },
  { title: "Upload & Sync", url: "/upload", icon: Upload },
  { title: "Audit Logs", url: "/audit-logs", icon: ClipboardList, adminOnly: true },
  { title: "DB Explorer", url: "/db-explorer", icon: Database, adminOnly: true },
  { title: "Reports", url: "/reports", icon: BarChart3, adminOnly: true },
  { title: "Settings", url: "/settings", icon: Settings, adminOnly: true },
];

export function AppSidebar() {
  const { t } = useLanguage();
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  
  const userRole = localStorage.getItem("userRole");
  const isSupplier = userRole === "supplier";
  const isAdmin = userRole === "admin";

  const renderItems = (items: any[]) =>
    items
      .filter((item) => !item.adminOnly || isAdmin)
      .map((item) => (
        <SidebarMenuItem key={item.title}>
        <SidebarMenuButton asChild>
          <NavLink
            to={item.url}
            end={item.url === "/"}
            className="flex items-center gap-3 px-3 py-2 rounded-md text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors"
            activeClassName="bg-sidebar-accent text-sidebar-primary font-medium"
          >
            <item.icon className="h-4 w-4 shrink-0" />
            {!collapsed && <span className="text-sm">{t(item.title)}</span>}
          </NavLink>
        </SidebarMenuButton>
      </SidebarMenuItem>
    ));

  if (isSupplier) {
    const supplierItems = [
      { title: "Supplier Portal", url: "/supplier-portal", icon: LayoutDashboard }
    ];
    return (
      <Sidebar collapsible="icon" className="border-r border-sidebar-border">
        <SidebarContent>
          <div className="p-4 flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center shrink-0">
              <Shield className="h-4 w-4 text-primary-foreground" />
            </div>
            {!collapsed && (
              <div>
                <h1 className="text-sm font-semibold text-sidebar-accent-foreground">ADIT</h1>
                <p className="text-xs text-sidebar-muted">{t("Supplier Portal")}</p>
              </div>
            )}
          </div>

          <SidebarGroup>
            <SidebarGroupLabel className="text-sidebar-muted text-xs uppercase tracking-wider px-3">{t("Supplier Space")}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>{renderItems(supplierItems)}</SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
      </Sidebar>
    );
  }

  return (
    <Sidebar collapsible="icon" className="border-r border-sidebar-border">
      <SidebarContent>
        <div className="p-4 flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center shrink-0">
            <Shield className="h-4 w-4 text-primary-foreground" />
          </div>
          {!collapsed && (
            <div>
              <h1 className="text-sm font-semibold text-sidebar-accent-foreground">ADIT6</h1>
              <p className="text-xs text-sidebar-muted">{t("Financial Audit Agent")}</p>
            </div>
          )}
        </div>

        <SidebarGroup>
          <SidebarGroupLabel className="text-sidebar-muted text-xs uppercase tracking-wider px-3">{t("Main")}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>{renderItems(mainItems)}</SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel className="text-sidebar-muted text-xs uppercase tracking-wider px-3">{t("System")}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>{renderItems(systemItems)}</SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}
