import { create } from "zustand";
import { AuditResult } from "@/services/api";

interface SessionState {
  sessionId: string | null;
  setSessionId: (id: string | null) => void;
  isAuditing: boolean;
  setIsAuditing: (isAuditing: boolean) => void;
  auditInvoices: string[];
  setAuditInvoices: (invoices: string[]) => void;
  auditResults: AuditResult[];
  setAuditResults: (results: AuditResult[]) => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  sessionId: null,
  setSessionId: (id) => set({ sessionId: id }),
  isAuditing: false,
  setIsAuditing: (isAuditing) => set({ isAuditing }),
  auditInvoices: [],
  setAuditInvoices: (invoices) => set({ auditInvoices: invoices }),
  auditResults: [],
  setAuditResults: (results) => set({ auditResults: results }),
}));
