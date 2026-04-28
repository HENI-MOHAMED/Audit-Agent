import React, { useState } from "react";
import { UploadCloud, CheckCircle2, FileText, Loader2, AlertCircle, Building2, Sparkles, Send, ShieldCheck, Download, Plus } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

// Simple mock for now
const mockSuppliers = [
  { id: "1", name: "Acme Corp" },
  { id: "2", name: "Global Supplies" },
];

const initialProducts = [
  { id: "PROD-1", name: "Consulting Services", description: "Monthly consulting fee", price: 1500, type: "buy" },
  { id: "PROD-2", name: "Office Supplies", description: "Stationery and paper", price: 200, type: "buy" },
];

const mockPOs = [
  { id: "PO-101", desc: "PO-101 (Laptops)" },
  { id: "PO-102", desc: "PO-102 (Office Chairs)" },
];

export default function SupplierPortal() {
  const [selectedSupplier, setSelectedSupplier] = useState<string>("");
  const [selectedPO, setSelectedPO] = useState<string>("");
  const [newSupplier, setNewSupplier] = useState({
    name: "",
    tax_number: "",
    email: "",
    phone: "",
    address: ""
  });
  
  const [file, setFile] = useState<File | null>(null);
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractedData, setExtractedData] = useState<any | null>(null);
  
  const [entryMode, setEntryMode] = useState<string>("auto");
  const [manualInvoice, setManualInvoice] = useState({
    invoice_number: "",
    creation_date: "",
    amount: "",
    currency: "",
    products: [] as any[]
  });
  
  const [isNewSupplierDialogOpen, setIsNewSupplierDialogOpen] = useState(false);

  const [mockProducts, setMockProducts] = useState(initialProducts);
  const [isNewProductDialogOpen, setIsNewProductDialogOpen] = useState(false);
  const [newProduct, setNewProduct] = useState({ name: "", description: "", price: "", type: "buy" });

  const { toast } = useToast();

  const handleAddNewProduct = async () => {
    if (!newProduct.name.trim()) {
      toast({ title: "Product name is required.", variant: "destructive" });
      return;
    }
    
    try {
      const response = await fetch("http://localhost:8000/api/new_products", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newProduct.name,
          description: newProduct.description,
          price: parseFloat(newProduct.price) || 0,
          type: newProduct.type
        })
      });

      if (!response.ok) throw new Error("Failed to add product");
      const result = await response.json();

      const createdProduct = {
        id: result.data.id.toString(),
        name: result.data.name,
        description: result.data.description,
        price: result.data.price,
        type: result.data.type
      };
      
      setMockProducts([...mockProducts, createdProduct]);
      setIsNewProductDialogOpen(false);
      setNewProduct({ name: "", description: "", price: "", type: "buy" });
      toast({ title: "Product added successfully!" });
    } catch (e) {
      toast({ title: "Error creating product on the backend", variant: "destructive" });
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleUploadAndExtract = async () => {
    if (!file) {
      toast({ title: "Please select a file first", variant: "destructive" });
      return;
    }

    setIsExtracting(true);
    setExtractedData(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      // We will point to the new endpoint we are about to build
      const response = await fetch("http://localhost:8000/api/invoice/extract", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Failed to extract data");
      }

      const data = await response.json();
      setExtractedData(data);
      toast({ title: "Invoice data extracted successfully!" });
      
      // Auto-select supplier if extracted and not set
      if (data.supplier_name && !selectedSupplier) {
         // Try to find matching supplier or we just show it in the UI
      }

    } catch (error) {
      console.error(error);
      toast({ title: "Failed to process the document", variant: "destructive" });
    } finally {
      setIsExtracting(false);
    }
  };

  const handleSend = async () => {
    if (!selectedSupplier && !extractedData?.supplier_name) {
      toast({ title: "Please select a supplier", variant: "destructive" });
      return;
    }

    const payloadData = entryMode === "auto" 
      ? extractedData 
      : { 
          supplier_name: selectedSupplier,
          ...manualInvoice 
        };
    
    try {
      const response = await fetch("http://localhost:8000/api/invoice/receive", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          entry_mode: entryMode,
          supplier_name: payloadData.supplier_name || selectedSupplier,
          invoice_number: payloadData.invoice_number,
          creation_date: payloadData.creation_date,
          amount: payloadData.amount,
          currency: payloadData.currency || "USD",
          products: payloadData.products || []
        })
      });

      if (!response.ok) throw new Error("Failed to submit invoice");
      
      const result = await response.json();
      if (result.status === "error") throw new Error(result.message);

      toast({ title: "Invoice submitted successfully!" });
      setFile(null);
      setExtractedData(null);
      setManualInvoice({ invoice_number: "", creation_date: "", amount: "", currency: "", products: [] });
    } catch (e: any) {
      console.error(e);
      toast({ title: e.message || "Error submitting invoice to the backend", variant: "destructive" });
    }
  };

  const handleAddSupplier = async () => {
    if (newSupplier.name.trim()) {
      try {
        const response = await fetch("http://localhost:8000/api/new_supplier", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(newSupplier)
        });

        if (!response.ok) throw new Error("Failed to add supplier");

        const result = await response.json();

        // Push to mock list using returned ID
        mockSuppliers.push({ id: result.data.id || Date.now().toString(), name: newSupplier.name });
        setSelectedSupplier(newSupplier.name);
        setIsNewSupplierDialogOpen(false);
        setNewSupplier({ name: "", tax_number: "", email: "", phone: "", address: "" });
        toast({ title: "Supplier added successfully!" });
      } catch (e) {
        toast({ title: "Error creating supplier on the backend", variant: "destructive" });
      }
    } else {
      toast({ title: "Supplier name is required.", variant: "destructive" });
    }
  };

  const handleNewSupplierChange = (field: string, value: string) => {
    setNewSupplier(prev => ({ ...prev, [field]: value }));
  };

  return (
    <div className="max-w-7xl mx-auto space-y-8 pb-12 w-full animation-fade-in">
      {/* Hero Banner Component */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-primary/10 via-primary/5 to-background border shadow-sm p-8 md:p-10 mb-8">
        <div className="absolute top-0 right-0 -translate-y-12 translate-x-1/4 opacity-5 pointer-events-none">
          <Building2 className="w-[400px] h-[400px]" />
        </div>
        <div className="relative z-10 flex flex-col gap-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary w-fit text-sm font-medium">
            <ShieldCheck className="w-4 h-4" />
            Secure Vendor Portal
          </div>
          <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight text-foreground">
            Invoice Submission <span className="text-primary text-transparent bg-clip-text bg-gradient-to-r from-primary to-blue-500">Center</span>
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl">
            Upload your invoices to securely associate them with purchase orders. Our AI will automatically extract details for faster processing and seamless payment approvals.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Details */}
        <Card className="lg:col-span-5 shadow-sm border-muted">
          <CardHeader className="bg-muted/30 pb-6 border-b mb-6">
            <div className="flex items-center gap-2 mb-1">
              <div className="flex items-center justify-center w-6 h-6 rounded-full bg-primary/20 text-primary font-bold text-xs">1</div>
              <CardTitle className="text-xl">Supplier Details</CardTitle>
            </div>
            <CardDescription className="ml-8 text-base">Select your business profile and assign an active Purchase Order to help us verify your invoice.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-3">
              <Label className="text-sm font-semibold">Vendor Identity</Label>
              <div className="flex gap-2">
                <Select value={selectedSupplier} onValueChange={setSelectedSupplier}>
                  <SelectTrigger className="w-full min-h-[3rem] text-base">
                    <SelectValue placeholder="Select authenticated vendor..." />
                  </SelectTrigger>
                  <SelectContent>
                    {mockSuppliers.map((s) => (
                      <SelectItem key={s.id} value={s.name}>{s.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                
                <Dialog open={isNewSupplierDialogOpen} onOpenChange={setIsNewSupplierDialogOpen}>
                  <DialogTrigger asChild>
                    <Button variant="outline" className="min-h-[3rem] px-4"><Plus className="w-4 h-4 mr-2" /> New</Button>
                  </DialogTrigger>
                  <DialogContent className="sm:max-w-lg">
                    <DialogHeader>
                      <DialogTitle className="text-2xl flex items-center gap-2">
                        <Building2 className="w-6 h-6 text-primary" />
                        Onboard New Supplier
                      </DialogTitle>
                      <DialogDescription>Enter the business entity details to create a new verified vendor profile.</DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                      <div className="space-y-2">
                        <Label>Business Name <span className="text-red-500">*</span></Label>
                        <Input 
                          value={newSupplier.name} 
                          onChange={(e) => handleNewSupplierChange('name', e.target.value)} 
                          placeholder="e.g. Globex Corporation" 
                          className="h-10"
                        />
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label>Tax Identification Number</Label>
                          <Input 
                            value={newSupplier.tax_number} 
                            onChange={(e) => handleNewSupplierChange('tax_number', e.target.value)} 
                            placeholder="e.g. TAX12345678"
                            className="h-10"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>Phone Contact</Label>
                          <Input 
                            value={newSupplier.phone} 
                            onChange={(e) => handleNewSupplierChange('phone', e.target.value)} 
                            placeholder="e.g. +1 555-1234"
                            className="h-10"
                          />
                        </div>
                      </div>
                      <div className="space-y-2">
                        <Label>Billing Email</Label>
                        <Input 
                          type="email"
                          value={newSupplier.email} 
                          onChange={(e) => handleNewSupplierChange('email', e.target.value)} 
                          placeholder="e.g. billing@globex.com"
                          className="h-10"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Headquarters Address</Label>
                        <Input 
                          value={newSupplier.address} 
                          onChange={(e) => handleNewSupplierChange('address', e.target.value)} 
                          placeholder="e.g. 123 Industrial Way, Suite A, Chicago, IL"
                          className="h-10"
                        />
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="ghost" onClick={() => setIsNewSupplierDialogOpen(false)}>Cancel</Button>
                      <Button onClick={handleAddSupplier} className="bg-primary hover:bg-primary/90">Register Vendor</Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </div>
            </div>

            <div className="space-y-3 pt-4 border-t border-muted/50">
              <Label className="text-sm font-semibold">Purchase Order Link <span className="text-muted-foreground font-normal ml-1">(Optional)</span></Label>
              <Select value={selectedPO} onValueChange={setSelectedPO}>
                <SelectTrigger className="min-h-[3rem] text-base">
                  <SelectValue placeholder="Search or select active PO..." />
                </SelectTrigger>
                <SelectContent>
                  {mockPOs.map((po) => (
                    <SelectItem key={po.id} value={po.id}>{po.desc}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {/* Right Column: Invoice Document */}
        <Card className="lg:col-span-7 shadow-sm border-muted">
          <CardHeader className="bg-muted/30 pb-6 border-b mb-6">
            <div className="flex items-center gap-2 mb-1">
              <div className="flex items-center justify-center w-6 h-6 rounded-full bg-primary/20 text-primary font-bold text-xs">2</div>
              <CardTitle className="text-xl">Invoice Source</CardTitle>
            </div>
            <CardDescription className="ml-8 text-base">Provide your invoice either by uploading a document for smart extraction or entering details manually.</CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="auto" value={entryMode} onValueChange={setEntryMode} className="w-full">
              <TabsList className="grid w-full grid-cols-2 mb-6 p-1 bg-muted rounded-lg">
                <TabsTrigger value="auto" className="rounded-md py-2 data-[state=active]:bg-background data-[state=active]:shadow-sm">
                  <Sparkles className="w-4 h-4 mr-2 text-primary" />
                  Auto-Extract
                </TabsTrigger>
                <TabsTrigger value="manual" className="rounded-md py-2 data-[state=active]:bg-background data-[state=active]:shadow-sm">
                  <FileText className="w-4 h-4 mr-2" />
                  Manual Entry
                </TabsTrigger>
              </TabsList>
              
              <TabsContent value="auto" className="space-y-6 animate-in slide-in-from-bottom-2">
                <div className="border-2 border-dashed border-muted-foreground/25 rounded-xl p-10 flex flex-col items-center justify-center space-y-4 bg-muted/20 transition-all hover:bg-muted/40 hover:border-primary/50 relative group">
                  <div className="p-4 bg-background rounded-full shadow-sm group-hover:scale-110 transition-transform duration-300">
                    <UploadCloud className="h-8 w-8 text-primary" />
                  </div>
                  <div className="text-center space-y-2">
                    <Label htmlFor="file-upload" className="text-lg font-semibold cursor-pointer hover:text-primary transition-colors">
                      Click to browse your files
                    </Label>
                    <p className="text-muted-foreground">or drag and drop here</p>
                    <p className="text-xs text-muted-foreground/70 font-medium uppercase tracking-wider">Supports PDF, PNG, JPG (10MB Max)</p>
                    <Input 
                      id="file-upload" 
                      type="file" 
                      className="absolute inset-0 w-full h-full opacity-0 cursor-pointer" 
                      accept=".pdf,image/*" 
                      onChange={handleFileChange}
                    />
                  </div>
                  {file && (
                    <div className="absolute bottom-4 flex items-center gap-3 text-sm bg-background/95 backdrop-blur px-4 py-2 rounded-lg border border-primary/20 shadow-sm w-[90%] justify-center z-10 animate-in fade-in zoom-in-95">
                      <FileText className="h-5 w-5 text-blue-500 shrink-0" />
                      <span className="truncate font-medium">{file.name}</span>
                      <span className="text-xs text-muted-foreground shrink-0">({(file.size / 1024 / 1024).toFixed(2)} MB)</span>
                    </div>
                  )}
                </div>

                <Button 
                  className="w-full h-12 text-base font-semibold shadow-sm" 
                  onClick={handleUploadAndExtract} 
                  disabled={!file || isExtracting}
                >
                  {isExtracting ? (
                    <>
                      <Loader2 className="mr-3 h-5 w-5 animate-spin" />
                      Extracting Information...
                    </>
                  ) : (
                    <>
                      <Sparkles className="mr-2 h-5 w-5" />
                      Run AI Extraction
                    </>
                  )}
                </Button>
              </TabsContent>

              <TabsContent value="manual" className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Invoice Number <span className="text-red-500">*</span></Label>
                    <Input 
                      value={manualInvoice.invoice_number} 
                      onChange={(e) => setManualInvoice({...manualInvoice, invoice_number: e.target.value})} 
                      placeholder="e.g. INV-2023-001" 
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Date <span className="text-red-500">*</span></Label>
                    <Input 
                      type="date"
                      value={manualInvoice.creation_date} 
                      onChange={(e) => setManualInvoice({...manualInvoice, creation_date: e.target.value})} 
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Total Amount <span className="text-red-500">*</span></Label>
                    <Input 
                      type="number" step="0.01"
                      value={manualInvoice.amount} 
                      onChange={(e) => setManualInvoice({...manualInvoice, amount: e.target.value})} 
                      placeholder="0.00" 
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Currency <span className="text-red-500">*</span></Label>
                    <Input 
                      value={manualInvoice.currency} 
                      onChange={(e) => setManualInvoice({...manualInvoice, currency: e.target.value})} 
                      placeholder="e.g. USD, EUR" 
                    />
                  </div>
                </div>

                {/* Line Items for Manual Input */}
                <div className="pt-4 space-y-4">
                  <div className="flex items-center justify-between border-b pb-2">
                    <Label className="text-base font-semibold">Line Items</Label>
                  </div>
                  
                  {manualInvoice.products.length === 0 ? (
                    <div className="text-center p-8 border-2 border-dashed rounded-xl bg-muted/20 text-muted-foreground flex flex-col items-center justify-center space-y-3">
                      <FileText className="w-8 h-8 text-muted-foreground/50" />
                      <p className="text-sm">No line items added yet.</p>
                      <Button 
                        variant="secondary" 
                        size="sm" 
                        onClick={() => setManualInvoice({
                          ...manualInvoice, 
                          products: [...manualInvoice.products, { product_id: "", description: "", quantity: "1", unit_price: "0.00", tax_id: "", subtotal: "0.00" }]
                        })}
                      >
                        <Plus className="w-4 h-4 mr-2" /> Add Your First Item
                      </Button>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {manualInvoice.products.map((product, index) => (
                        <div key={index} className="grid grid-cols-12 gap-4 items-start bg-card p-4 rounded-xl border shadow-sm relative group">
                          <Button 
                            variant="ghost" 
                            size="icon" 
                            className="absolute -right-3 -top-3 h-7 w-7 rounded-full bg-background border shadow-sm text-muted-foreground hover:text-red-500 hover:bg-red-50 opacity-0 group-hover:opacity-100 transition-opacity"
                            onClick={() => {
                              const newProducts = manualInvoice.products.filter((_, i) => i !== index);
                              setManualInvoice({...manualInvoice, products: newProducts});
                            }}
                          >
                            ✕
                          </Button>
                          
                          <div className="col-span-12 md:col-span-4 space-y-2">
                            <Label className="text-xs font-semibold text-muted-foreground uppercase">Product</Label>
                            <Select 
                              value={product.product_id}
                              onValueChange={(val) => {
                                const newProducts = [...manualInvoice.products];
                                newProducts[index].product_id = val;
                                const p = mockProducts.find(mp => mp.id === val);
                                if(p) {
                                  if(!newProducts[index].description) newProducts[index].description = p.name + (p.description ? " - " + p.description : "");
                                  if(!newProducts[index].unit_price || newProducts[index].unit_price === "0.00") newProducts[index].unit_price = p.price.toString();
                                }
                                setManualInvoice({...manualInvoice, products: newProducts});
                              }}
                            >
                              <SelectTrigger className="h-10">
                                <SelectValue placeholder="Select practically..." />
                              </SelectTrigger>
                              <SelectContent>
                                {mockProducts.map((mp) => (
                                  <SelectItem key={mp.id} value={mp.id}>{mp.name}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                            <Button 
                              variant="link" 
                              type="button"
                              className="text-xs h-6 px-0 text-primary w-fit"
                              onClick={() => setIsNewProductDialogOpen(true)}
                            >
                              + Create New Product
                            </Button>
                          </div>
                          
                          <div className="col-span-12 md:col-span-8 grid grid-cols-12 gap-3">
                            <div className="col-span-12 space-y-2">
                              <Label className="text-xs font-semibold text-muted-foreground uppercase">Description</Label>
                              <Input 
                                placeholder="Detailed item description"
                                value={product.description}
                                onChange={(e) => {
                                  const newProducts = [...manualInvoice.products];
                                  newProducts[index].description = e.target.value;
                                  setManualInvoice({...manualInvoice, products: newProducts});
                                }}
                                className="h-10"
                              />
                            </div>
                            
                            <div className="col-span-3 space-y-2">
                              <Label className="text-xs font-semibold text-muted-foreground uppercase">Qty</Label>
                              <Input 
                                type="number"
                                placeholder="1"
                                value={product.quantity}
                                onChange={(e) => {
                                  const newProducts = [...manualInvoice.products];
                                  newProducts[index].quantity = e.target.value;
                                  // Update subtotal
                                  const qty = parseFloat(e.target.value) || 0;
                                  const price = parseFloat(newProducts[index].unit_price) || 0;
                                  newProducts[index].subtotal = (qty * price).toFixed(2);
                                  setManualInvoice({...manualInvoice, products: newProducts});
                                }}
                                className="h-10"
                              />
                            </div>
                            
                            <div className="col-span-4 space-y-2">
                              <Label className="text-xs font-semibold text-muted-foreground uppercase">Unit Price</Label>
                              <Input 
                                type="number"
                                step="0.01"
                                placeholder="0.00"
                                value={product.unit_price}
                                onChange={(e) => {
                                  const newProducts = [...manualInvoice.products];
                                  newProducts[index].unit_price = e.target.value;
                                  // Update subtotal
                                  const qty = parseFloat(newProducts[index].quantity) || 0;
                                  const price = parseFloat(e.target.value) || 0;
                                  newProducts[index].subtotal = (qty * price).toFixed(2);
                                  setManualInvoice({...manualInvoice, products: newProducts});
                                }}
                                className="h-10"
                              />
                            </div>
                            
                            <div className="col-span-2 space-y-2">
                              <Label className="text-xs font-semibold text-muted-foreground uppercase">Tax %</Label>
                              <Input 
                                placeholder="0"
                                value={product.tax_id}
                                onChange={(e) => {
                                  const newProducts = [...manualInvoice.products];
                                  newProducts[index].tax_id = e.target.value;
                                  setManualInvoice({...manualInvoice, products: newProducts});
                                }}
                                className="h-10"
                              />
                            </div>
                            
                            <div className="col-span-3 space-y-2">
                              <Label className="text-xs font-semibold text-muted-foreground uppercase">Amount</Label>
                              <Input 
                                type="number"
                                step="0.01"
                                placeholder="0.00"
                                value={product.subtotal}
                                onChange={(e) => {
                                  const newProducts = [...manualInvoice.products];
                                  newProducts[index].subtotal = e.target.value;
                                  setManualInvoice({...manualInvoice, products: newProducts});
                                }}
                                className="h-10 font-medium bg-muted/30"
                              />
                            </div>
                          </div>
                        </div>
                      ))}
                      
                      <Button 
                        variant="outline" 
                        className="w-full border-dashed" 
                        onClick={() => setManualInvoice({
                          ...manualInvoice, 
                          products: [...manualInvoice.products, { product_id: "", description: "", quantity: "1", unit_price: "0.00", tax_id: "", subtotal: "0.00" }]
                        })}
                      >
                        <Plus className="w-4 h-4 mr-2" /> Add Another Item
                      </Button>
                    </div>
                  )}
                </div>
                
                <div className="pt-2">
                  <Label>Attach Document (Optional)</Label>
                  <div className="mt-1 flex items-center gap-2">
                    <Input 
                      type="file" 
                      accept=".pdf,image/*" 
                      onChange={handleFileChange}
                      className="text-sm"
                    />
                  </div>
                </div>

                <Button 
                  className="w-full mt-4" 
                  variant="secondary"
                  onClick={() => {
                    if(!manualInvoice.invoice_number || !manualInvoice.amount) {
                      toast.error("Please fill out required invoice fields");
                      return;
                    }
                    toast.success("Manual data saved. Click Send Invoice To System to submit.");
                    setExtractedData(null); // Clear extracted data if using manual
                  }}
                >
                  Save Manual Entry
                </Button>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>

      {(extractedData || entryMode === 'manual') && (
        <Card className={entryMode === 'manual' ? "border-primary shadow-md overflow-hidden animate-in fade-in slide-in-from-bottom-4" : "bg-primary-[0.02] border-primary/30 shadow-md overflow-hidden animate-in fade-in slide-in-from-bottom-4"}>
          <div className="absolute top-0 inset-x-0 h-1 bg-gradient-to-r from-primary to-blue-500"></div>
          <CardHeader className="bg-background/50 border-b pb-6">
            <CardTitle className="flex items-center gap-3 text-2xl">
              <div className="p-2 bg-primary/10 rounded-full">
                <CheckCircle2 className="h-6 w-6 text-primary" />
              </div>
              {entryMode === 'auto' ? "Extraction Results" : "Ready to Send"}
            </CardTitle>
            <CardDescription className="text-base ml-11">
              {entryMode === 'auto' 
                ? "Verify the automatically extracted data before sending. This data was interpreted by our AI." 
                : "Submit the manually provided invoice details to the system securely."}
            </CardDescription>
          </CardHeader>
          
          {entryMode === 'auto' && extractedData && (
            <CardContent className="pt-8">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-8 bg-muted/20 p-6 rounded-xl border border-muted/50">
                <div className="space-y-1.5">
                  <Label className="text-xs text-muted-foreground uppercase font-bold tracking-wider">Supplier Match</Label>
                  <div className="font-semibold text-lg">{extractedData.supplier_name || "N/A"}</div>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs text-muted-foreground uppercase font-bold tracking-wider">Invoice Number</Label>
                  <div className="font-semibold text-lg">{extractedData.invoice_number || "N/A"}</div>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs text-muted-foreground uppercase font-bold tracking-wider">Creation Date</Label>
                  <div className="font-semibold text-lg">{extractedData.creation_date || "N/A"}</div>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs text-primary uppercase font-bold tracking-wider">Total Amount</Label>
                  <div className="font-bold font-mono text-2xl text-foreground">{extractedData.amount || "N/A"}</div>
                </div>
              </div>

              {extractedData.products && extractedData.products.length > 0 && (
                <div className="mt-8">
                  <Label className="text-sm font-semibold uppercase mb-3 flex items-center gap-2">
                    <FileText className="w-4 h-4 text-muted-foreground" />
                    Line Items Discovered ({extractedData.products.length})
                  </Label>
                  <div className="rounded-xl border border-muted-foreground/20 bg-background overflow-hidden relative shadow-sm max-h-[300px] overflow-y-auto">
                      <table className="w-full text-sm">
                        <thead className="bg-muted/50 text-muted-foreground sticky top-0 border-b z-10">
                          <tr>
                            <th className="px-4 py-3 text-left font-semibold uppercase text-xs tracking-wider">Product / Service Description</th>
                            <th className="px-4 py-3 text-right font-semibold uppercase text-xs tracking-wider">Qty</th>
                            <th className="px-4 py-3 text-right font-semibold uppercase text-xs tracking-wider">Unit Price</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y">
                          {extractedData.products.map((item: any, i: number) => (
                            <tr key={i} className="hover:bg-muted/20 transition-colors">
                              <td className="px-4 py-3 font-medium text-foreground/90">{item.product_name}</td>
                              <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">{item.quantity}</td>
                              <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">{item.price}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                  </div>
                </div>
              )}
              
              {extractedData.fraud_alerts && extractedData.fraud_alerts.length > 0 && (
                <div className="mt-6 p-4 bg-red-50 text-red-900 border border-red-200 rounded-xl flex gap-3 shadow-sm">
                   <AlertCircle className="h-6 w-6 shrink-0 text-red-600 mt-0.5" />
                   <div>
                     <span className="font-bold text-lg block mb-1">Potential OCR Flags Detected:</span>
                     <ul className="list-disc pl-5 mt-2 space-y-1 text-sm font-medium">
                       {extractedData.fraud_alerts.map((alert: string, i: number) => (
                         <li key={i}>{alert}</li>
                       ))}
                     </ul>
                   </div>
                </div>
              )}
            </CardContent>
          )}

          <CardFooter className="bg-muted/30 justify-between items-center py-6 px-8 border-t border-muted/50">
            <span className="text-sm text-muted-foreground flex items-center gap-2">
              <ShieldCheck className="w-4 h-4" />
              By transmitting this invoice, you securely certify it is accurate and valid.
            </span>
            <Button size="lg" className="h-12 px-8 text-base shadow-sm font-semibold group" onClick={handleSend}>
              Transmit Invoice
              <Send className="ml-2 w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </Button>
          </CardFooter>
        </Card>
      )}

      {/* New Product Dialog */}
      <Dialog open={isNewProductDialogOpen} onOpenChange={setIsNewProductDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Add New Buy Product</DialogTitle>
            <DialogDescription>Add a new product or service to the database catalog.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Product Name <span className="text-red-500">*</span></Label>
              <Input 
                value={newProduct.name} 
                onChange={(e) => setNewProduct({ ...newProduct, name: e.target.value })} 
                placeholder="e.g. Server Hosting" 
              />
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Input 
                value={newProduct.description} 
                onChange={(e) => setNewProduct({ ...newProduct, description: e.target.value })} 
                placeholder="e.g. Monthly cloud hosting" 
              />
            </div>
            <div className="space-y-2">
              <Label>Default Price</Label>
              <Input 
                type="number" 
                step="0.01" 
                value={newProduct.price} 
                onChange={(e) => setNewProduct({ ...newProduct, price: e.target.value })} 
                placeholder="0.00" 
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setIsNewProductDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleAddNewProduct} className="bg-primary hover:bg-primary/90">Save Product</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}