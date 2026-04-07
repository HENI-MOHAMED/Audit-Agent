import { Zap, BrainCircuit, Microscope } from "lucide-react";
import { cn } from "@/lib/utils";

interface ThinkingModeSelectorProps {
  mode: string;
  setMode: (mode: string) => void;
  disabled?: boolean;
}

export function ThinkingModeSelector({ mode, setMode, disabled }: ThinkingModeSelectorProps) {
  return (
    <div className="flex h-10 items-center rounded-lg border border-border bg-muted/50 p-1 shadow-inner">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setMode("fast")}
        className={cn(
          "flex items-center justify-center gap-2 rounded-md px-3 py-1.5 text-xs font-semibold transition-all duration-300 disabled:opacity-50",
          mode === "fast"
            ? "bg-background text-foreground shadow-sm ring-1 ring-border/50"
            : "text-muted-foreground hover:bg-muted-foreground/10 hover:text-foreground"
        )}
      >
        <Zap className={cn("h-3.5 w-3.5", mode === "fast" && "text-yellow-500")} />
        Fast
      </button>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setMode("thinking")}
        className={cn(
          "flex items-center justify-center gap-2 rounded-md px-3 py-1.5 text-xs font-semibold transition-all duration-300 disabled:opacity-50",
          mode === "thinking"
            ? "bg-background text-foreground shadow-sm ring-1 ring-border/50"
            : "text-muted-foreground hover:bg-muted-foreground/10 hover:text-foreground"
        )}
      >
        <BrainCircuit className={cn("h-3.5 w-3.5", mode === "thinking" && "text-blue-500")} />
        Thinking
      </button>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setMode("deep_dive")}
        className={cn(
          "flex items-center justify-center gap-2 rounded-md px-3 py-1.5 text-xs font-semibold transition-all duration-300 disabled:opacity-50",
          mode === "deep_dive"
            ? "bg-background text-foreground shadow-sm ring-1 ring-border/50"
            : "text-muted-foreground hover:bg-muted-foreground/10 hover:text-foreground"
        )}
      >
        <Microscope className={cn("h-3.5 w-3.5", mode === "deep_dive" && "text-purple-500")} />
        Deep Dive
      </button>
    </div>
  );
}
