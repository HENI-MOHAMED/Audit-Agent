import { useSuppliers } from "@/services/queries";
import { TableSkeleton } from "@/components/Skeletons";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Plus, Pencil, Trash2 } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogClose } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { useState } from "react";
import { createContact, updateContact, deleteContact } from "@/services/api";
import { useToast } from "@/hooks/use-toast";

export default function SuppliersPage() {
  const { data: suppliers, isLoading, refetch } = useSuppliers();
  const [open, setOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  
  const { toast } = useToast();

  const [formData, setFormData] = useState({
    name: "",
    tax_number: "",
    email: "",
    phone: "",
    address: ""
  });
  const [editData, setEditData] = useState<any>(null);
  
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name) return;
    
    setIsSubmitting(true);
    try {
      const res = await createContact({
        ...formData,
        type: "supplier",
        source_system: "manual"
      });
      
      if (res.ok) {
        toast({ title: "Supplier added successfully!" });
        setOpen(false);
        setFormData({ name: "", tax_number: "", email: "", phone: "", address: "" });
        refetch();
      } else {
        toast({ title: "Error adding supplier", description: res.error, variant: "destructive" });
      }
    } catch (e: any) {
      toast({ title: "Error", description: e.message, variant: "destructive" });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editData || !editData.name) return;
    
    setIsSubmitting(true);
    try {
      const res = await updateContact(editData.id, {
        name: editData.name,
        tax_number: editData.tax_number,
        email: editData.email,
        phone: editData.phone,
        address: editData.address
      });
      
      if (res.ok) {
        toast({ title: "Supplier updated successfully!" });
        setEditOpen(false);
        setEditData(null);
        refetch();
      } else {
        toast({ title: "Error updating supplier", description: res.error, variant: "destructive" });
      }
    } catch (e: any) {
      toast({ title: "Error", description: e.message, variant: "destructive" });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    setIsDeleting(true);
    try {
      const res = await deleteContact(deleteId);
      if (res.ok) {
        toast({ title: "Supplier deleted successfully!" });
        setDeleteId(null);
        refetch();
      } else {
        toast({ title: "Error deleting supplier", description: res.error, variant: "destructive" });
      }
    } catch (e: any) {
      toast({ title: "Error", description: e.message, variant: "destructive" });
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-semibold">Suppliers</h2>
          <p className="text-muted-foreground text-sm">Supplier monitoring and analysis</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="gap-2">
              <Plus className="h-4 w-4" />
              Add Supplier
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add New Supplier</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Supplier Name *</Label>
                <Input 
                  id="name" 
                  value={formData.name}
                  onChange={(e) => setFormData(p => ({ ...p, name: e.target.value }))}
                  required 
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="tax_number">Tax Number</Label>
                <Input 
                  id="tax_number" 
                  value={formData.tax_number}
                  onChange={(e) => setFormData(p => ({ ...p, tax_number: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input 
                  id="email" 
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData(p => ({ ...p, email: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="phone">Phone</Label>
                <Input 
                  id="phone" 
                  value={formData.phone}
                  onChange={(e) => setFormData(p => ({ ...p, phone: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="address">Address</Label>
                <Input 
                  id="address" 
                  value={formData.address}
                  onChange={(e) => setFormData(p => ({ ...p, address: e.target.value }))}
                />
              </div>
              <DialogFooter>
                <DialogClose asChild>
                  <Button variant="outline" type="button">Cancel</Button>
                </DialogClose>
                <Button type="submit" disabled={isSubmitting || !formData.name}>
                  {isSubmitting ? "Adding..." : "Add Supplier"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
      <Card>
        <CardContent className="p-0">
          {isLoading ? <div className="p-6"><TableSkeleton rows={5} cols={6} /></div> : suppliers.length > 0 ? (
            <Table>
              <TableHeader><TableRow>
                <TableHead>Name</TableHead><TableHead>Tax Number</TableHead><TableHead>Email</TableHead>
                <TableHead>Phone</TableHead><TableHead className="text-right">Invoices</TableHead><TableHead>Source</TableHead>
                <TableHead className="w-[100px] text-right">Actions</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {suppliers.map((s) => (
                  <TableRow key={s.id}>
                    <TableCell className="font-medium text-sm">{s.name ?? "N/A"}</TableCell>
                    <TableCell className="text-sm text-muted-foreground font-mono">{s.tax_number ?? "N/A"}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{s.email ?? "N/A"}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{s.phone ?? "N/A"}</TableCell>
                    <TableCell className="text-right text-sm">{s.total_invoices}</TableCell>
                    <TableCell className="text-sm text-muted-foreground capitalize">{s.source_system ?? "N/A"}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          className="h-8 w-8 text-muted-foreground hover:text-primary"
                          onClick={() => {
                            setEditData(s);
                            setEditOpen(true);
                          }}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          className="h-8 w-8 text-muted-foreground hover:text-destructive"
                          onClick={() => setDeleteId(s.id)}
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
            <div className="p-8 text-center text-muted-foreground text-sm">No suppliers found. Sync the local DB first.</div>
          )}
        </CardContent>
      </Card>

      {/* Edit Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Supplier</DialogTitle>
          </DialogHeader>
          {editData && (
            <form onSubmit={handleEditSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="edit-name">Supplier Name *</Label>
                <Input 
                  id="edit-name" 
                  value={editData.name || ""}
                  onChange={(e) => setEditData({ ...editData, name: e.target.value })}
                  required 
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-tax">Tax Number</Label>
                <Input 
                  id="edit-tax" 
                  value={editData.tax_number || ""}
                  onChange={(e) => setEditData({ ...editData, tax_number: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-email">Email</Label>
                <Input 
                  id="edit-email" 
                  type="email"
                  value={editData.email || ""}
                  onChange={(e) => setEditData({ ...editData, email: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-phone">Phone</Label>
                <Input 
                  id="edit-phone" 
                  value={editData.phone || ""}
                  onChange={(e) => setEditData({ ...editData, phone: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-address">Address</Label>
                <Input 
                  id="edit-address" 
                  value={editData.address || ""}
                  onChange={(e) => setEditData({ ...editData, address: e.target.value })}
                />
              </div>
              <DialogFooter>
                <Button variant="outline" type="button" onClick={() => setEditOpen(false)}>Cancel</Button>
                <Button type="submit" disabled={isSubmitting || !editData.name}>
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
            <DialogTitle>Delete Supplier</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">Are you sure you want to delete this supplier? This action cannot be undone.</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteId(null)}>Cancel</Button>
            <Button variant="destructive" onClick={handleDelete} disabled={isDeleting}>
              {isDeleting ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
