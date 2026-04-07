import { useDocuments } from "@/services/queries";
import { TableSkeleton } from "@/components/Skeletons";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { FileText } from "lucide-react";

export default function DocumentsPage() {
  const { data: documents, isLoading } = useDocuments();

  return (
    <div className="space-y-6">
      <div><h2 className="text-2xl font-semibold">Documents</h2><p className="text-muted-foreground text-sm">Uploaded financial document attachments</p></div>
      <Card>
        <CardContent className="p-0">
          {isLoading ? <div className="p-6"><TableSkeleton /></div> : documents.length > 0 ? (
            <Table>
              <TableHeader><TableRow>
                <TableHead>File Name</TableHead><TableHead>Linked Invoice</TableHead>
                <TableHead>File Path</TableHead><TableHead>Uploaded</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {documents.map((doc) => (
                  <TableRow key={doc.id}>
                    <TableCell className="text-sm font-medium flex items-center gap-2">
                      <FileText className="h-4 w-4 text-muted-foreground" />
                      {doc.file_name ?? "N/A"}
                    </TableCell>
                    <TableCell className="text-sm font-mono text-muted-foreground">{doc.invoice_number ?? `Invoice #${doc.invoice_id ?? "N/A"}`}</TableCell>
                    <TableCell className="text-sm text-muted-foreground max-w-xs truncate">{doc.file_path ?? "N/A"}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{doc.uploaded_at ?? "N/A"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="p-8 text-center text-muted-foreground text-sm">No documents found. Upload documents via the Upload page.</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
