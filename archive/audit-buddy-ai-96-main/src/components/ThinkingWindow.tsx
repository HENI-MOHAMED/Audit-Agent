import { Bot, ChevronDown, ChevronUp, Terminal } from "lucide-react";
import { useState, useRef, useEffect } from "react";

export interface ToolEvent {
  id: string;
  name: string;
  args: any;
  result?: string;
  status: "running" | "done" | "error";
}

interface ThinkingWindowProps {
  toolEvents: ToolEvent[];
}

export function ThinkingWindow({ toolEvents }: ThinkingWindowProps) {
  const [expanded, setExpanded] = useState(true);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (expanded) {
      endRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [toolEvents, expanded]);

  if (toolEvents.length === 0) return null;

  return (
    <div className="flex gap-3 mb-4 last:mb-0">
      <div className="h-7 w-7 rounded-full bg-primary/10 flex items-center justify-center shrink-0 mt-1">
        <Bot className="h-4 w-4 text-primary" />
      </div>
      <div className="w-full max-w-[80%] rounded-xl border border-border bg-card shadow-sm overflow-hidden animate-in fade-in slide-in-from-bottom-2 duration-300">
        <button 
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center justify-between px-3 py-2 bg-secondary/50 hover:bg-secondary transition-colors text-xs font-medium text-muted-foreground"
        >
          <div className="flex items-center gap-2">
            <Terminal className="h-4 w-4" />
            <span>AI Thinking Process ({toolEvents.length} action{toolEvents.length !== 1 ? 's' : ''})</span>
          </div>
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
        
        {expanded && (
          <div className="p-3 space-y-3 max-h-[300px] overflow-y-auto bg-black/5 dark:bg-black/20">
            {toolEvents.map((t) => (
              <div key={t.id} className="text-xs bg-background rounded-md border border-border p-2 animate-in fade-in zoom-in-95 duration-200 shadow-sm">
                <div className="flex items-center gap-2 font-mono text-[10px] text-primary mb-1">
                  {t.status === "running" ? (
                    <div className="h-2.5 w-2.5 rounded-full bg-yellow-500 animate-pulse" />
                  ) : t.status === "error" ? (
                    <div className="h-2.5 w-2.5 rounded-full bg-destructive" />
                  ) : (
                    <div className="h-2.5 w-2.5 rounded-full bg-green-500" />
                  )}
                  <span className="font-semibold">{t.name}()</span>
                </div>
                <div className="font-mono text-[10px] text-muted-foreground truncate opacity-70 mb-1">
                  Args: {JSON.stringify(t.args)}
                </div>
                {t.result && (
                  <div className="font-mono text-[10px] text-foreground border-t border-border/50 pt-1.5 mt-1.5 max-h-20 overflow-y-auto whitespace-pre-wrap">
                    {t.result}
                  </div>
                )}
              </div>
            ))}
            <div ref={endRef} />
          </div>
        )}
      </div>
    </div>
  );
}
