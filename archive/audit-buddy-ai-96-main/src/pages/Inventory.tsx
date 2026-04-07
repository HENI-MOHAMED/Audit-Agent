import { useInventory } from "@/services/queries";
import { TableSkeleton } from "@/components/Skeletons";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Plus, Pencil, Trash2 } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogClose } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { useState } from "react";
import { createInventoryLog, updateInventoryLog, deleteInventoryLog } from "@/services/api";
import { useToast } from "@/hooks/use-toast";

const changeTypeStyles: Record<string, string> = {
  stock_in: "bg-risk-low/10 text-risk-low border-risk-low/20",
  stock_out: "bg-primary/10 text-primary border-primary/20",
  adjustment: "bg-risk-medium/10 text-risk-medium border-risk-medium/20",
  return: "bg-risk-medium/10 text-risk-medium border-risk-medium/20",
  transfer: "bg-primary/10 text-primary border-primary/20",
  damage: "bg-risk-high/10 text-risk-high border-risk-high/20",
};

export default function InventoryPage() {
  const { data: movements, isLoading, refetch } = useInventory();
  const [open, setOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const { toast } = useToast();

  const [formData, setFormData] = useState({
    product_id: "",
    supplier_id: "",
    change_type: "",
    change_quantity: ""
  });
  const [editData, setEditData] = useState<any>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.product_id || !formData.change_quantity) return;
    
    setIsSubmitting(true);
    try {
      const res = await createInventoryLog({
        ...formData,
        product_id: parseInt(formData.product_id) || null,
        supplier_id: formData.supplier_id ? parseInt(formData.supplier_id) : null,
        change_quantity: parseFloat(formData.change_quantity) || 0,
        source_system: "manual",
        timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19)
      });
      
      if (res.ok) {
        toast({ title: "Inventory log added successfully!" });
        setOpen(false);
        setFormData({ product_id: "", supplier_id: "", change_type: "", change_quantity: "" });
        refetch();
      } else {
        toast({ title: "Error adding log", description: res.error, variant: "destructive" });
      }
    } catch (e: any) {
      toast({ title: "Error", description: e.message, variant: "destructive" });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editData) return;
    
    setIsSubmitting(true);
    try {
      const res = await updateInventoryLog(editData.id, {
        product_id: parseInt(editData.product_id) || null,
        supplier_id: editData.supplier_id ? parseInt(editData.supplier_id) : null,
        change_type: editData.change_type,
        change_quantity: parseFloat(editData.change_quantity) || 0
      });
      
      if (res.ok) {
        toast({ title: "Inventory log updated successfully!" });
        setEditOpen(false);
        setEditData(null);
        refetch();
      } else {
        toast({ title: "Error updating log", description: res.error, variant: "destructive" });
      }
    } catch (e: any) {
      toast({ title: "Error", description: e.message, variant: "destructive" });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      const res = await deleteInventoryLog(deleteId);
      if (res.ok) {
        toast({ title: "Inventory log deleted successfully!" });
        setDeleteId(null);
        refetch();
      } else {
        toast({ title: "Error deleting log", description: res.error, variant: "destructive" });
      }
    } catch (e: any) {
      toast({ title: "Error", description: e.message, variant: "destructive" });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-semibold">Inventory</h2>
          <p className="text-muted-foreground text-sm">Track inventory movements and reconciliation</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="gap-2">
              <Plus className="h-4 w-4" />
              Add Movement
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add Inventory Movement</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="product_id">Product ID *</Label>
                <Input 
                  id="product_id" 
                  type="number"
                  value={formData.product_id}
                  onChange={(e) => setFormData(p => ({ ...p, product_id: e.target.value }))}
                  required 
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="supplier_id">Supplier ID</Label>
                <Input 
                  id="supplier_id" 
                  type="number"
                  value={formData.supplier_id}
                  onChange={(e) => setFormData(p => ({ ...p, supplier_id: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="change_type">Change Type</Label>
                <Input 
                  id="change_type" 
                  placeholder="stock_in, stock_out, adjustment..."
                  value={formData.change_type}
                  onChange={(e) => setFormData(p => ({ ...p, change_type: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="change_quantity">Quantity *</Label>
                <Input 
                  id="change_quantity" 
                  type="number"
                  step="0.01"
                  value={formData.change_quantity}
                  onChange={(e) => setFormData(p => ({ ...p, change_quantity: e.target.value }))}
                  required
                />
              </div>
              <DialogFooter>
                <DialogClose asChild>
                  <Button variant="outline" type="button">Cancel</Button>
                </DialogClose>
                <Button type="submit" disabled={isSubmitting || !formData.product_id || !formData.change_quantity}>
                  {isSubmitting ? "Adding..." : "Add Movement"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
      <Card>
        <CardContent className="p-0">
          {isLoading ? <div className="p-6"><TableSkeleton /></div> : movements.length > 0 ? (
            <Table>
              <TableHeader><TableRow>
                <TableHead>Product</TableHead><TableHead>Supplier</TableHead><TableHead>Type</TableHead>
                <TableHead className="text-right">Quantity</TableHead><TableHead>Timestamp</TableHead><TableHead>Source</TableHead>
                <TableHead className="w-[100px] text-right">Actions</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {movements.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell className="font-medium text-sm">{m.product_name ?? "N/A"}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{m.supplier_name ?? "N/A"}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className={changeTypeStyles[(m.change_type ?? "").toLowerCase()] ?? "bg-muted text-muted-foreground border-border"}>
                        {(m.change_type ?? "N/A").replace(/_/g, " ")}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right text-sm font-mono">
                      {(m.change_quantity ?? 0) > 0 ? `+${m.change_quantity}` : m.change_quantity}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">{m.timestamp ?? "N/A"}</TableCell>
                    <TableCell className="text-sm text-muted-foreground capitalize">{m.source_system ?? "N/A"}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          className="h-8 w-8 text-muted-foreground hover:text-primary"
                          onClick={() => {
                            setEditData(m);
                            setEditOpen(true);
                          }}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          className="h-8 w-8 text-muted-foreground hover:text-destructive"
                          onClick={() => setDeleteId(m.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="p-8 text-center text-muted-foreground text-sm">No inventory movements found. Sync the local DB first.</div>
          )}
        </CardContent>
      </Card>

      {/* Edit Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Inventory Movement</DialogTitle>
          </DialogHeader>
          {editData && (
            <form onSubmit={handleEditSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="edit-product_id">Product ID *</Label>
                <Input 
                  id="edit-product_id" 
                  type="number"
                  value={editData.product_id || ""}
                  onChange={(e) => setEditData({ ...editData, product_id: e.target.value })}
                  required 
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-supplier_id">Supplier ID</Label>
                <Input 
                  id="edit-supplier_id" 
                  type="number"
                  value={editData.supplier_id || ""}
                  onChange={(e) => setEditData({ ...editData, supplier_id: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-change_type">Change Type</Label>
                <Input 
                  id="edit-change_type" 
                  value={editData.change_type || ""}
                  onChange={(e) => setEditData({ ...editData, change_type: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-change_quantity">Quantity *</Label>
                <Input 
                  id="edit-change_quantity" 
                  type="number"
                  step="0.01"
                  value={editData.change_quantity || 0}
                  onChange={(e) => setEditData({ ...editData, change_quantity: e.target.value })}
                  required
                />
              </div>
              <DialogFooter>
                <Button variant="outline" type="button" onClick={() => setEditOpen(false)}>Cancel</Button>
                <Button type="submit" disabled={isSubmitting || !editData.product_id || !editData.change_quantity}>
                  {isSubmitting ? "Saving..." : "Save Changes"}
                </Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteId !== null} onOpenChange={(open) => !open && setDeleteId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Movement</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">Are you sure you want to delete this inventory log? This action cannot be undone.</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteId(null)}>Cancel</Button>
            <Button variant="destructive" onClick={handleDelete}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
