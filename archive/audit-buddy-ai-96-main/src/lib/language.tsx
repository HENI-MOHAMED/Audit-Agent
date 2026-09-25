import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type Language = "en" | "fr";

const translations: Record<string, string> = {
  "Dashboard": "Tableau de bord", "AI Chat": "Chat IA", "Run Audit": "Lancer un audit",
  "Supplier Requests": "Demandes fournisseurs", "Invoices": "Factures", "Suppliers": "Fournisseurs",
  "Products": "Produits", "Place Order": "Passer une commande", "Inventory": "Inventaire",
  "Documents": "Documents", "Upload & Sync": "Importer et synchroniser", "Audit Logs": "Journaux d'audit",
  "DB Explorer": "Explorateur de base de données", "Reports": "Rapports", "Settings": "Paramètres",
  "Main": "Principal", "System": "Système", "Supplier Portal": "Portail fournisseur",
  "Supplier Space": "Espace fournisseur", "Financial Audit Agent": "Agent d'audit financier",
  "Search invoices, suppliers...": "Rechercher des factures, fournisseurs...", "Notifications": "Notifications",
  "Mark all read": "Tout marquer comme lu", "Clear": "Effacer", "No notifications yet": "Aucune notification",
  "We'll let you know when something arrives.": "Nous vous informerons lorsqu'un nouvel élément arrivera.",
  "Mark as read": "Marquer comme lu", "Delete notification": "Supprimer la notification", "Sign Out": "Se déconnecter",
  "Settings saved": "Paramètres enregistrés", "Failed to save": "Échec de l'enregistrement",
  "New session created": "Nouvelle session créée", "Session ended": "Session terminée",
  "Configure the audit agent": "Configurer l'agent d'audit", "Language": "Langue", "App language": "Langue de l'application",
  "English": "Anglais", "French": "Français", "Backend Configuration": "Configuration du serveur",
  "Data Source": "Source de données", "Company Name": "Nom de l'entreprise", "API Keys": "Clés API",
  "Email Configuration": "Configuration de l'e-mail", "Database Configuration (Odoo)": "Configuration de la base de données (Odoo)",
  "Current Session": "Session actuelle", "No active session": "Aucune session active", "New Session": "Nouvelle session",
  "End Session": "Terminer la session", "Email alerts for critical findings": "Alertes e-mail pour les problèmes critiques",
  "Daily audit summary": "Résumé quotidien de l'audit", "New supplier alerts": "Alertes concernant les nouveaux fournisseurs",
  "Save Settings": "Enregistrer les paramètres", "Error": "Erreur", "Cancel": "Annuler", "Save": "Enregistrer",
  "Add": "Ajouter", "Edit": "Modifier", "Delete": "Supprimer", "Refresh": "Actualiser", "Loading...": "Chargement...",
  "No data": "Aucune donnée", "No results found": "Aucun résultat trouvé", "All": "Tous", "Critical": "Critique",
  "Warning": "Avertissement", "High": "Élevé", "Medium": "Moyen", "Low": "Faible",
  "AI Audit Overview": "Vue d'ensemble de l'audit IA", "AI Financial Audit Agent — System Overview": "Agent d'audit financier IA — Vue d'ensemble du système",
  "Total Invoices": "Total des factures", "Audit Findings": "Constats d'audit", "Profit Prediction": "Prévision des bénéfices",
  "Cash Flow Risk Deficit Probability": "Probabilité de déficit de trésorerie", "Predicted Future Findings by Risk": "Constats futurs prévus par risque",
  "Recent Audit Findings": "Constats d'audit récents", "No prediction data": "Aucune donnée de prévision", "No risk data": "Aucune donnée de risque",
  "No audit findings yet. Run an audit or sync the local DB first.": "Aucun constat d'audit pour le moment. Lancez un audit ou synchronisez d'abord la base locale.",
  "Monitor and analyze invoice data": "Surveillez et analysez les données des factures", "Invoice #": "N° de facture", "Amount": "Montant",
  "Date": "Date", "Type": "Type", "Tax": "Taxe", "Status": "Statut", "Supplier": "Fournisseur", "Total": "Total",
  "N/A": "N/D", "Line Items": "Lignes de facture", "Product / Description": "Produit / Description", "Qty": "Qté",
  "Price": "Prix", "Subtotal": "Sous-total", "No line items": "Aucune ligne de facture", "Audit Results": "Résultats de l'audit",
  "No audit results for this invoice": "Aucun résultat d'audit pour cette facture", "No invoices found. Sync the local DB first.": "Aucune facture trouvée. Synchronisez d'abord la base locale.",
  "No suppliers found. Sync the local DB first.": "Aucun fournisseur trouvé. Synchronisez d'abord la base locale.", "No products found. Sync the local DB first.": "Aucun produit trouvé. Synchronisez d'abord la base locale.",
  "No inventory movements found. Sync the local DB first.": "Aucun mouvement de stock trouvé. Synchronisez d'abord la base locale.",
  "No documents found. Upload documents via the Upload page.": "Aucun document trouvé. Importez des documents via la page Importer et synchroniser.",
  "No audit logs found. Run an audit first.": "Aucun journal d'audit trouvé. Lancez d'abord un audit.", "No tables found. Run DB Sync first.": "Aucune table trouvée. Lancez d'abord la synchronisation de la base.",
  "Add New Product": "Ajouter un produit", "Add New Buy Product": "Ajouter un produit acheté", "Edit Product": "Modifier le produit", "Delete Product": "Supprimer le produit",
  "Product Name": "Nom du produit", "Product Name *": "Nom du produit *", "Product ID *": "ID du produit *", "Product / Service Description": "Description du produit / service",
  "Default Price": "Prix par défaut", "Currency": "Devise", "Description": "Description", "Save Product": "Enregistrer le produit",
  "Add New Supplier": "Ajouter un fournisseur", "Edit Supplier": "Modifier le fournisseur", "Delete Supplier": "Supprimer le fournisseur",
  "Supplier Name *": "Nom du fournisseur *", "Supplier ID": "ID du fournisseur", "Address": "Adresse", "Phone": "Téléphone", "Email": "E-mail",
  "Register Vendor": "Enregistrer le fournisseur", "Supplier monitoring and analysis": "Suivi et analyse des fournisseurs", "Supplier Details": "Détails du fournisseur",
  "Inventory": "Inventaire", "Add Inventory Movement": "Ajouter un mouvement de stock", "Edit Inventory Movement": "Modifier le mouvement de stock", "Delete Movement": "Supprimer le mouvement",
  "Track inventory movements and reconciliation": "Suivez les mouvements et le rapprochement des stocks", "Change Type": "Type de changement", "Quantity": "Quantité", "Quantity *": "Quantité *",
  "Place Order": "Passer une commande", "Order Details": "Détails de la commande", "Order Lines": "Lignes de commande", "Order Date": "Date de commande",
  "Create a new purchase order for a supplier.": "Créer un nouveau bon de commande pour un fournisseur.", "Select a supplier...": "Sélectionnez un fournisseur...", "Select product...": "Sélectionnez un produit...",
  "Add products to the order.": "Ajouter des produits à la commande.", "Pending Requests": "Demandes en attente", "Pending Invoices": "Factures en attente",
  "Documents": "Documents", "Uploaded financial document attachments": "Pièces jointes de documents financiers importés", "Upload & Sync": "Importer et synchroniser",
  "Supports PDF, PNG, JPG (10MB Max)": "PDF, PNG, JPG acceptés (10 Mo maximum)", "or drag and drop here": "ou glissez-déposez ici", "Reading documents...": "Lecture des documents...",
  "Run Audit": "Lancer un audit", "Trigger AI-powered invoice audits": "Lancer des audits de factures avec l'IA", "Audit Logs": "Journaux d'audit", "System audit findings and alerts": "Constats et alertes d'audit du système",
  "Reports": "Rapports", "Financial Intelligence Report": "Rapport d'intelligence financière", "Generated by Audit Agent — AI Financial Intelligence Report": "Généré par l'agent d'audit — Rapport d'intelligence financière IA",
  "DB Explorer": "Explorateur de base de données", "Database Explorer": "Explorateur de base de données", "Browse the local audit SQLite database": "Parcourir la base SQLite locale d'audit",
  "Chat": "Chat", "Start a conversation with the AI Audit Agent": "Commencez une conversation avec l'agent d'audit IA", "AI Chat": "Chat IA",
  "Welcome back": "Bon retour", "Username": "Nom d'utilisateur", "Password": "Mot de passe", "Sign In": "Se connecter", "Log In": "Connexion",
  "Close": "Fermer", "Next": "Suivant", "Previous": "Précédent", "More": "Plus", "Action": "Action", "Actions": "Actions", "Details": "Détails",
  "Loading comprehensive analysis...": "Chargement de l'analyse complète...", "Task Complete": "Tâche terminée", "Potential OCR Flags Detected:": "Alertes OCR potentielles détectées :",
  "Draft": "Brouillon", "Pending": "En attente", "Posted": "Comptabilisée", "Paid": "Payée", "Cancelled": "Annulée", "Reversed": "Contrepassée",
  "In Progress": "En cours", "Approved": "Approuvée", "Completed": "Terminée", "Open": "Ouvert", "No issue": "Aucun problème",
};

type LanguageContextValue = { language: Language; setLanguage: (language: Language) => void; t: (value: string) => string };
const LanguageContext = createContext<LanguageContextValue | null>(null);

const originalText = new WeakMap<Text, string>();
const originalAttributes = new WeakMap<HTMLElement, Record<string, string>>();

function translateTree(root: Node, language: Language) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const textNodes: Text[] = [];
  let node: Node | null;
  while ((node = walker.nextNode())) textNodes.push(node as Text);
  textNodes.forEach((textNode) => {
    const source = originalText.get(textNode) ?? textNode.nodeValue ?? "";
    originalText.set(textNode, source);
    const value = source.trim();
    const translated = language === "fr" ? translations[value] : value;
    if (!value || !translated) return;
    textNode.nodeValue = source.replace(value, translated);
  });
  root.querySelectorAll<HTMLElement>("[placeholder], [title], [aria-label]").forEach((element) => {
    const attributes = originalAttributes.get(element) ?? {};
    ["placeholder", "title", "aria-label"].forEach((attribute) => {
      const value = element.getAttribute(attribute);
      if (value && attributes[attribute] === undefined) attributes[attribute] = value;
    });
    originalAttributes.set(element, attributes);
    ["placeholder", "title", "aria-label"].forEach((attribute) => {
      const value = attributes[attribute];
      if (value) {
        const translated = language === "fr" ? translations[value] || value : value;
        if (element.getAttribute(attribute) !== translated) element.setAttribute(attribute, translated);
      }
    });
  });
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>(() => localStorage.getItem("language") === "fr" ? "fr" : "en");
  const value = useMemo(() => ({ language, setLanguage, t: (text: string) => language === "fr" ? translations[text] || text : text }), [language]);

  useEffect(() => {
    localStorage.setItem("language", language);
    document.documentElement.lang = language;
    translateTree(document.body, language);
    if (language === "fr") {
      const observer = new MutationObserver(() => translateTree(document.body, language));
      observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["placeholder", "title", "aria-label"] });
      return () => observer.disconnect();
    }
  }, [language]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) throw new Error("useLanguage must be used inside LanguageProvider");
  return context;
}