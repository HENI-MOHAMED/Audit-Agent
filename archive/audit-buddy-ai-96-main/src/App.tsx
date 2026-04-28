import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes, Navigate, Outlet } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { DashboardLayout } from "@/layouts/DashboardLayout";
import Dashboard from "@/pages/Dashboard";
import Invoices from "@/pages/Invoices";
import Suppliers from "@/pages/Suppliers";
import Products from "@/pages/Products";
import Inventory from "@/pages/Inventory";
import AuditLogs from "@/pages/AuditLogs";
import Documents from "@/pages/Documents";
import Reports from "@/pages/Reports";
import Settings from "@/pages/Settings";
import Upload from "@/pages/Upload";
import DBExplorer from "@/pages/DBExplorer";
import NotFound from "@/pages/NotFound";
import LogIn from "@/pages/LogIn";
import SupplierRequests from "@/pages/SupplierRequests";

import SupplierPortal from "@/pages/SupplierPortal";

const queryClient = new QueryClient();

const ProtectedRoute = () => {
  const userRole = localStorage.getItem("userRole");
  if (!userRole) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
};

const RoleProtectedRoute = ({ allowedRoles }: { allowedRoles: string[] }) => {
  const userRole = localStorage.getItem("userRole") || "";
  if (!userRole) return <Navigate to="/login" replace />;
  if (!allowedRoles.includes(userRole)) {
    if (userRole === "supplier") return <Navigate to="/supplier-portal" replace />;
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
};

const HomeRedirect = () => {
  const userRole = localStorage.getItem("userRole");
  if (userRole === "supplier") {
    return <Navigate to="/supplier-portal" replace />;
  }
  return <Dashboard />;
};

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LogIn />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<DashboardLayout />}>
              <Route path="/" element={<HomeRedirect />} />
              
              {/* Supplier Routes */}
              <Route element={<RoleProtectedRoute allowedRoles={["supplier"]} />}>
                <Route path="/supplier-portal" element={<SupplierPortal />} />
              </Route>

              {/* Admin/Employee Routes */}
              <Route element={<RoleProtectedRoute allowedRoles={["admin", "employee", "customer"]} />}>
                {/* Kept empty because their content is rendered persistently in DashboardLayout */}
                <Route path="/chat" element={<></>} />
                <Route path="/audit" element={<></>} />
                <Route path="/invoices" element={<Invoices />} />
                <Route path="/supplier-requests" element={<SupplierRequests />} />
                <Route path="/suppliers" element={<Suppliers />} />
                <Route path="/products" element={<Products />} />
                <Route path="/inventory" element={<Inventory />} />
                <Route path="/audit-logs" element={<AuditLogs />} />
                <Route path="/documents" element={<Documents />} />
                <Route path="/upload" element={<Upload />} />
                <Route path="/db-explorer" element={<DBExplorer />} />
                <Route path="/reports" element={<Reports />} />
                <Route path="/settings" element={<Settings />} />
              </Route>
              <Route path="/dashboard" element={<Navigate to="/" replace />} />
            </Route>
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
