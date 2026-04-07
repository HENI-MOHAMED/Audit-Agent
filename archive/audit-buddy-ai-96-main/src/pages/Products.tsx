import { useProducts } from "@/services/queries";
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
import { createProduct, updateProduct, deleteProduct } from "@/services/api";
import { useToast } from "@/hooks/use-toast";

export default function ProductsPage() {
  const { data: products, isLoading, refetch } = useProducts();
  const [open, setOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  
  const { toast } = useToast();

  const [formData, setFormData] = useState({
    name: "",
    description: "",
    price: "",
    cost: "",
    type: ""
  });
  const [editData, setEditData] = useState<any>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name) return;
    
    setIsSubmitting(true);
    try {
      const res = await createProduct({
        ...formData,
        price: parseFloat(formData.price) || 0,
        cost: parseFloat(formData.cost) || 0,
        source_system: "manual"
      });
      
      if (res.ok) {
        toast({ title: "Product added successfully!" });
        setOpen(false);
        setFormData({ name: "", description: "", price: "", cost: "", type: "" });
        refetch();
      } else {
        toast({ title: "Error adding product", description: res.error, variant: "destructive" });
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
      const res = await updateProduct(editData.id, {
        name: editData.name,
        description: editData.description,
        price: parseFloat(editData.price?.toString()) || 0,
        cost: parseFloat(editData.cost?.toString()) || 0,
        type: editData.type
      });
      
      if (res.ok) {
        toast({ title: "Product updated successfully!" });
        setEditOpen(false);
        setEditData(null);
        refetch();
      } else {
        toast({ title: "Error updating product", description: res.error, variant: "destructive" });
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
      const res = await deleteProduct(deleteId);
      if (res.ok) {
        toast({ title: "Product deleted successfully!" });
        setDeleteId(null);
        refetch();
      } else {
        toast({ title: "Error deleting product", description: res.error, variant: "destructive" });
      }
    } catch (e: any) {
      toast({ title: "Error", description: e.message, variant: "destructive" });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-semibold">Products</h2>
          <p className="text-muted-foreground text-sm">Product catalog from the audit database</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="gap-2">
              <Plus className="h-4 w-4" />
              Add Product
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add New Product</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Product Name *</Label>
                <Input 
                  id="name" 
                  value={formData.name}
                  onChange={(e) => setFormData(p => ({ ...p, name: e.target.value }))}
                  required 
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Input 
                  id="description" 
                  value={formData.description}
                  onChange={(e) => setFormData(p => ({ ...p, description: e.target.value }))}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="price">Price</Label>
                  <Input 
                    id="price" 
                    type="number"
                    step="0.01"
                    value={formData.price}
                    onChange={(e) => setFormData(p => ({ ...p, price: e.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="cost">Cost</Label>
                  <Input 
                    id="cost" 
                    type="number"
                    step="0.01"
                    value={formData.cost}
                    onChange={(e) => setFormData(p => ({ ...p, cost: e.target.value }))}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="type">Type</Label>
                <Input 
                  id="type" 
                  value={formData.type}
                  onChange={(e) => setFormData(p => ({ ...p, type: e.target.value }))}
                />
              </div>
              <DialogFooter>
                <DialogClose asChild>
                  <Button variant="outline" type="button">Cancel</Button>
                </DialogClose>
                <Button type="submit" disabled={isSubmitting || !formData.name}>
                  {isSubmitting ? "Adding..." : "Add Product"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
      <Card>
        <CardContent className="p-0">
          {isLoading ? <div className="p-6"><TableSkeleton /></div> : products.length > 0 ? (
            <Table>
              <TableHeader><TableRow>
                <TableHead>Name</TableHead><TableHead>Description</TableHead><TableHead>Type</TableHead>
                <TableHead className="text-right">Price</TableHead><TableHead className="text-right">Cost</TableHead>
                <TableHead>Source</TableHead>
                <TableHead className="w-[100px] text-right">Actions</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {products.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-medium text-sm">{p.name ?? "N/A"}</TableCell>
                    <TableCell className="text-sm text-muted-foreground max-w-xs truncate">{p.description ?? "N/A"}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="capitalize">{p.type ?? "N/A"}</Badge>
                    </TableCell>
                    <TableCell className="text-right text-sm">{(p.price ?? 0).toLocaleString()}</TableCell>
                    <TableCell className="text-right text-sm text-muted-foreground">{(p.cost ?? 0).toLocaleString()}</TableCell>
                    <TableCell className="text-sm text-muted-foreground capitalize">{p.source_system ?? "N/A"}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          className="h-8 w-8 text-muted-foreground hover:text-primary"
                          onClick={() => {
                            setEditData(p);
                            setEditOpen(true);
                          }}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          className="h-8 w-8 text-muted-foreground hover:text-destructive"
                          onClick={() => setDeleteId(p.id)}
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
            <div className="p-8 text-center text-muted-foreground text-sm">No products found. Sync the local DB first.</div>
          )}
        </CardContent>
      </Card>

      {/* Edit Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Product</DialogTitle>
          </DialogHeader>
          {editData && (
            <form onSubmit={handleEditSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="edit-name">Product Name *</Label>
                <Input 
                  id="edit-name" 
                  value={editData.name || ""}
                  onChange={(e) => setEditData({ ...editData, name: e.target.value })}
                  required 
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-description">Description</Label>
                <Input 
                  id="edit-description" 
                  value={editData.description || ""}
                  onChange={(e) => setEditData({ ...editData, description: e.target.value })}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="edit-price">Price</Label>
                  <Input 
                    id="edit-price" 
                    type="number"
                    step="0.01"
                    value={editData.price || 0}
                    onChange={(e) => setEditData({ ...editData, price: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="edit-cost">Cost</Label>
                  <Input 
                    id="edit-cost" 
                    type="number"
                    step="0.01"
                    value={editData.cost || 0}
                    onChange={(e) => setEditData({ ...editData, cost: e.target.value })}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-type">Type</Label>
                <Input 
                  id="edit-type" 
                  value={editData.type || ""}
                  onChange={(e) => setEditData({ ...editData, type: e.target.value })}
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
            <DialogTitle>Delete Product</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">Are you sure you want to delete this product? This action cannot be undone.</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteId(null)}>Cancel</Button>
            <Button variant="destructive" onClick={handleDelete}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
