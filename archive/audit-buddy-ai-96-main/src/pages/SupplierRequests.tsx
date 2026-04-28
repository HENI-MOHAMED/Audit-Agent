import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { 
  getPendingSuppliers, confirmSupplierRequest, 
  getPendingProducts, confirmProductRequest, 
  getPendingInvoices, confirmInvoiceRequest,
} from "@/services/api";
import { useSuppliers, useProducts } from "@/services/queries";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { toast } from "sonner";
import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ArrowRight, CheckCircle, Database } from "lucide-react";

export default function SupplierRequests() {
  const queryClient = useQueryClient();

  const { data: pendingSuppliers, isLoading: loadSupp } = useQuery({
    queryKey: ['pendingSuppliers'], queryFn: getPendingSuppliers
  });
  const { data: pendingProducts, isLoading: loadProd } = useQuery({
    queryKey: ['pendingProducts'], queryFn: getPendingProducts
  });
  const { data: pendingInvoices, isLoading: loadInv } = useQuery({
    queryKey: ['pendingInvoices'], queryFn: getPendingInvoices
  });

  const { data: suppliers } = useSuppliers();
  const { data: products } = useProducts();

  const mutSupp = useMutation({
    mutationFn: confirmSupplierRequest,
    onSuccess: () => {
      toast.success("Supplier confirmed");
      queryClient.invalidateQueries({ queryKey: ['pendingSuppliers'] });
      queryClient.invalidateQueries({ queryKey: ['suppliers'] });
    }
  });

  const mutProd = useMutation({
    mutationFn: confirmProductRequest,
    onSuccess: () => {
      toast.success("Product confirmed");
      queryClient.invalidateQueries({ queryKey: ['pendingProducts'] });
      queryClient.invalidateQueries({ queryKey: ['products'] });
    }
  });

  const mutInv = useMutation({
    mutationFn: ({ id, suppId, maps }: { id: number, suppId: number, maps: Record<string, number> }) => 
      confirmInvoiceRequest(id, suppId, maps),
    onSuccess: () => {
      toast.success("Invoice confirmed and mapped");
      queryClient.invalidateQueries({ queryKey: ['pendingInvoices'] });
      setConfirmingInvoice(null);
    }
  });

  // Invoice mapping dialog state
  const [confirmingInvoice, setConfirmingInvoice] = useState<any>(null);
  const [selectedSupplierId, setSelectedSupplierId] = useState<string>("");
  const [lineMappings, setLineMappings] = useState<Record<string, string>>({});

  const handleOpenMapDialog = (inv: any) => {
    setConfirmingInvoice(inv);
    
    // Auto-match supplier if exact name match
    const matchedSupp = suppliers?.find((s: any) => s.name?.toLowerCase() === inv.supplier_name?.toLowerCase());
    setSelectedSupplierId(matchedSupp ? String(matchedSupp.id) : "");

    // Auto-match products
    const initMappings: Record<string, string> = {};
    inv.lines?.forEach((line: any) => {
      const matchProd = products?.find((p: any) => 
        p.name?.toLowerCase() === line.description?.toLowerCase() ||
        p.description?.toLowerCase() === line.description?.toLowerCase()
      );
      if (matchProd) {
        initMappings[String(line.id)] = String(matchProd.id);
      }
    });
    setLineMappings(initMappings);
  };

  const handleConfirmMappedInvoice = () => {
    if (!selectedSupplierId) return toast.error("Please assign a supplier");
    
    const casts: Record<string, number> = {};
    for(const k of Object.keys(lineMappings)){
      if(lineMappings[k]) {
        casts[k] = Number(lineMappings[k]);
      }
    }
    
    mutInv.mutate({ id: confirmingInvoice.id, suppId: Number(selectedSupplierId), maps: casts });
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Pending Requests</h1>
          <p className="text-muted-foreground mt-2">Approve incoming data into permanent database records.</p>
        </div>
      </div>

      <Tabs defaultValue="invoices" className="space-y-6">
        <TabsList>
          <TabsTrigger value="invoices">Pending Invoices ({pendingInvoices?.length || 0})</TabsTrigger>
          <TabsTrigger value="suppliers">New Suppliers ({pendingSuppliers?.length || 0})</TabsTrigger>
          <TabsTrigger value="products">New Products ({pendingProducts?.length || 0})</TabsTrigger>
        </TabsList>

        <TabsContent value="invoices">
          <div className="border rounded-lg bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Invoice #</TableHead>
                  <TableHead>Supplier Text</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Lines</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pendingInvoices?.length === 0 && (
                  <TableRow><TableCell colSpan={5} className="text-center py-8">No pending invoices</TableCell></TableRow>
                )}
                {pendingInvoices?.map((inv: any) => (
                  <TableRow key={inv.id}>
                    <TableCell className="font-medium">{inv.invoice_number}</TableCell>
                    <TableCell>{inv.supplier_name}</TableCell>
                    <TableCell>{inv.amount} {inv.currency}</TableCell>
                    <TableCell>{inv.lines?.length || 0} items</TableCell>
                    <TableCell className="text-right">
                      <Button size="sm" onClick={() => handleOpenMapDialog(inv)}>
                        Map & Confirm <ArrowRight className="ml-2 w-4 h-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        <TabsContent value="suppliers">
          <div className="border rounded-lg bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Tax Number</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Extracted From</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pendingSuppliers?.length === 0 && (
                  <TableRow><TableCell colSpan={5} className="text-center py-8">No pending suppliers</TableCell></TableRow>
                )}
                {pendingSuppliers?.map((supp: any) => (
                  <TableRow key={supp.id}>
                    <TableCell className="font-medium">{supp.name}</TableCell>
                    <TableCell>{supp.tax_number}</TableCell>
                    <TableCell>{supp.email}</TableCell>
                    <TableCell>{new Date(supp.created_at).toLocaleDateString()}</TableCell>
                    <TableCell className="text-right">
                      <Button size="sm" onClick={() => mutSupp.mutate(supp.id)}>
                        <CheckCircle className="mr-2 w-4 h-4" /> Approve Contact
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        <TabsContent value="products">
          <div className="border rounded-lg bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Price Text</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pendingProducts?.length === 0 && (
                  <TableRow><TableCell colSpan={4} className="text-center py-8">No pending products</TableCell></TableRow>
                )}
                {pendingProducts?.map((prod: any) => (
                  <TableRow key={prod.id}>
                    <TableCell className="font-medium">{prod.name}</TableCell>
                    <TableCell>{prod.description}</TableCell>
                    <TableCell>{prod.price}</TableCell>
                    <TableCell className="text-right">
                      <Button size="sm" onClick={() => mutProd.mutate(prod.id)}>
                        <CheckCircle className="mr-2 w-4 h-4" /> Approve Product
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </TabsContent>
      </Tabs>

      {/* Database Mapping Dialog */}
      <Dialog open={!!confirmingInvoice} onOpenChange={(o) => !o && setConfirmingInvoice(null)}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Database className="w-5 h-5 text-primary" /> Map Pending Invoice
            </DialogTitle>
          </DialogHeader>
          
          {confirmingInvoice && (
            <div className="space-y-6 py-4">
              <div>
                <p className="text-sm font-semibold mb-2">Assign Contact for: <span className="text-primary">{confirmingInvoice.supplier_name}</span></p>
                <Select value={selectedSupplierId} onValueChange={setSelectedSupplierId}>
                  <SelectTrigger><SelectValue placeholder="Select existing supplier" /></SelectTrigger>
                  <SelectContent>
                    {suppliers?.map((s: any) => (
                      <SelectItem key={s.id} value={String(s.id)}>{s.name} ({s.tax_number || 'No Tax ID'})</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-3 mt-4">
                <p className="text-sm font-semibold">Map Line Items to Permanent Products</p>
                {confirmingInvoice.lines?.map((line: any, idx: number) => (
                  <div key={line.id} className="p-3 border rounded-md bg-muted/30">
                    <p className="text-xs font-medium mb-2">Item {idx+1}: {line.description} (Qty: {line.quantity})</p>
                    <Select 
                      value={lineMappings[line.id] || ""}
                      onValueChange={(val) => setLineMappings(prev => ({...prev, [line.id]: val}))}
                    >
                      <SelectTrigger><SelectValue placeholder="Assign to Product..." /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="SKIP">-- Do not map (leave null) --</SelectItem>
                        {products?.map((p: any) => (
                          <SelectItem key={p.id} value={String(p.id)}>{p.name} - ${p.price}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                ))}
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmingInvoice(null)}>Cancel</Button>
            <Button onClick={handleConfirmMappedInvoice} disabled={mutInv.isPending}>
              {mutInv.isPending ? "Processing..." : "Confirm into Database"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

    </div>
  );
}
