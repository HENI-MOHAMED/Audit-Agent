import { useState } from "react";
import { useSuppliers, useProducts } from "@/services/queries";
import { createPurchaseOrder } from "@/services/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ShoppingCart, Plus, Trash2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { PurchaseOrderPayload, PurchaseOrderLineItemPayload } from "@/types";

export default function PlaceOrder() {
  const { data: suppliers, isLoading: suppliersLoading } = useSuppliers();
  const { data: products, isLoading: productsLoading } = useProducts();
  const { toast } = useToast();

  const [contactId, setContactId] = useState<string>("");
  const [orderDate, setOrderDate] = useState<string>(new Date().toISOString().substring(0, 10));
  const [dueDate, setDueDate] = useState<string>("");
  const [lines, setLines] = useState<PurchaseOrderLineItemPayload[]>([
    { product_id: 0, quantity: 1, unit_price: 0 }
  ]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const addLine = () => {
    setLines([...lines, { product_id: 0, quantity: 1, unit_price: 0 }]);
  };

  const updateLine = (index: number, field: keyof PurchaseOrderLineItemPayload, value: any) => {
    const newLines = [...lines];
    newLines[index] = { ...newLines[index], [field]: value };
    // Auto populate unit_price if product is selected
    if (field === "product_id" && products) {
      const prod = products.find((p: any) => p.id === Number(value));
      if (prod && prod.cost) {
        newLines[index].unit_price = prod.cost;
      }
    }
    setLines(newLines);
  };

  const removeLine = (index: number) => {
    setLines(lines.filter((_, i) => i !== index));
  };

  const totalAmount = lines.reduce((acc, line) => acc + (line.quantity * line.unit_price), 0);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!contactId) {
      toast({ title: "Error", description: "Please select a supplier.", variant: "destructive" });
      return;
    }
    if (lines.length === 0 || lines.some(l => !l.product_id || l.quantity <= 0)) {
      toast({ title: "Error", description: "Please add valid products with quantity > 0.", variant: "destructive" });
      return;
    }

    setIsSubmitting(true);
    try {
      const payload: PurchaseOrderPayload = {
        contact_id: Number(contactId),
        order_date: orderDate,
        due_date: dueDate || undefined,
        total_amount: totalAmount,
        status: "draft",
        lines: lines.map(l => ({ ...l, subtotal: l.quantity * l.unit_price }))
      };

      const res = await createPurchaseOrder(payload);
      if (res && res.ok) {
        toast({ title: "Order Placed", description: `Purchase Order ${res.order_number || res.id} created successfully.` });
        // Reset form
        setContactId("");
        setDueDate("");
        setLines([{ product_id: 0, quantity: 1, unit_price: 0 }]);
      } else {
        toast({ title: "Error", description: res?.error || "Failed to place order.", variant: "destructive" });
      }
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-3">
        <div className="p-2 bg-primary/10 rounded-lg">
          <ShoppingCart className="w-6 h-6 text-primary" />
        </div>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Place Order</h1>
          <p className="text-muted-foreground">Create a new purchase order for a supplier.</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Order Details</CardTitle>
            <CardDescription>Select a supplier and dates.</CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="space-y-2">
              <Label htmlFor="supplier">Supplier</Label>
              <select
                id="supplier"
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background disabled:cursor-not-allowed disabled:opacity-50"
                value={contactId}
                onChange={(e) => setContactId(e.target.value)}
                disabled={suppliersLoading}
              >
                <option value="">Select a supplier...</option>
                {suppliers?.map((s: any) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="order_date">Order Date</Label>
              <Input
                id="order_date"
                type="date"
                value={orderDate}
                onChange={(e) => setOrderDate(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="due_date">Due Date (Optional)</Label>
              <Input
                id="due_date"
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Order Lines</CardTitle>
              <CardDescription>Add products to the order.</CardDescription>
            </div>
            <Button type="button" variant="outline" size="sm" onClick={addLine}>
              <Plus className="w-4 h-4 mr-2" /> Add Product
            </Button>
          </CardHeader>
          <CardContent className="space-y-4">
            {lines.map((line, index) => (
              <div key={index} className="flex flex-col md:flex-row items-end md:items-center gap-4 border p-4 rounded-lg relative">
                <div className="flex-1 w-full space-y-2">
                  <Label>Product</Label>
                  <select
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background disabled:cursor-not-allowed disabled:opacity-50"
                    value={line.product_id || ""}
                    onChange={(e) => updateLine(index, "product_id", Number(e.target.value))}
                    disabled={productsLoading}
                  >
                    <option value="">Select product...</option>
                    {products?.map((p: any) => (
                      <option key={p.id} value={p.id}>{p.name} {p.cost ? `($${p.cost})` : ""}</option>
                    ))}
                  </select>
                </div>
                <div className="w-full md:w-32 space-y-2">
                  <Label>Quantity</Label>
                  <Input
                    type="number"
                    min="1"
                    step="any"
                    value={line.quantity}
                    onChange={(e) => updateLine(index, "quantity", Number(e.target.value))}
                  />
                </div>
                <div className="w-full md:w-32 space-y-2">
                  <Label>Unit Price</Label>
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    value={line.unit_price}
                    onChange={(e) => updateLine(index, "unit_price", Number(e.target.value))}
                  />
                </div>
                <div className="w-full md:w-32 space-y-2">
                  <Label>Subtotal</Label>
                  <Input
                    type="text"
                    disabled
                    value={`$${(line.quantity * line.unit_price).toFixed(2)}`}
                    className="bg-muted"
                  />
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="text-red-500 hover:text-red-700 md:self-end"
                  onClick={() => removeLine(index)}
                  disabled={lines.length === 1}
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            ))}
            
            <div className="flex justify-end pt-4 border-t">
              <div className="text-xl font-bold">
                Total: ${totalAmount.toFixed(2)}
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end">
          <Button type="submit" disabled={isSubmitting} size="lg">
            {isSubmitting ? "Placing Order..." : "Place Order"}
          </Button>
        </div>
      </form>
    </div>
  );
}
