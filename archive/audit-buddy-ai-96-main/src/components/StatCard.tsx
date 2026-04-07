import { LucideIcon } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

interface StatCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend?: string;
  variant?: "default" | "danger" | "warning" | "success";
}

const variantStyles = {
  default: "text-primary bg-primary/10",
  danger: "text-risk-high bg-risk-high/10",
  warning: "text-risk-medium bg-risk-medium/10",
  success: "text-risk-low bg-risk-low/10",
};

export function StatCard({ title, value, icon: Icon, trend, variant = "default" }: StatCardProps) {
  return (
    <Card className="animate-fade-in">
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{title}</p>
            <p className="text-2xl font-semibold mt-1 text-card-foreground">{value.toLocaleString()}</p>
            {trend && <p className="text-xs text-muted-foreground mt-1">{trend}</p>}
          </div>
          <div className={`h-10 w-10 rounded-lg flex items-center justify-center ${variantStyles[variant]}`}>
            <Icon className="h-5 w-5" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
