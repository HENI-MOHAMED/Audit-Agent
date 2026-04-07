import { Brain, CheckCircle2, ChevronDown, ChevronUp, Loader2, Sparkles } from "lucide-react";
import { useState, useEffect, useRef } from "react";

export interface AgentState {
  id: string;
  name: string;
  status: "running" | "done" | "error";
  tools: any[];
  summary?: string;
}

interface AgentOrbProps {
  agent: AgentState;
}

export function AgentOrb({ agent }: AgentOrbProps) {
  const [expanded, setExpanded] = useState(true);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (expanded) {
      endRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [agent.tools, expanded, agent.summary]);

  // Give a distinct color/icon based on agent name
  let Icon = Brain;
  let colorClass = "text-purple-500 dark:text-purple-400";
  let bgClass = "bg-purple-100 dark:bg-purple-500/10";
  let borderClass = "border-purple-200 dark:border-purple-500/20";
  
  if (agent.name.toLowerCase().includes("retriever")) {
    Icon = Sparkles;
    colorClass = "text-blue-500 dark:text-blue-400";
    bgClass = "bg-blue-100 dark:bg-blue-500/10";
    borderClass = "border-blue-200 dark:border-blue-500/20";
  } else if (agent.name.toLowerCase().includes("calc")) {
    Icon = Brain;
    colorClass = "text-amber-500 dark:text-amber-400";
    bgClass = "bg-amber-100 dark:bg-amber-500/10";
    borderClass = "border-amber-200 dark:border-amber-500/20";
  } else if (agent.name.toLowerCase().includes("audit")) {
    Icon = CheckCircle2;
    colorClass = "text-emerald-500 dark:text-emerald-400";
    bgClass = "bg-emerald-100 dark:bg-emerald-500/10";
    borderClass = "border-emerald-200 dark:border-emerald-500/20";
  }

  // Gracefully fade away when done
  const containerClasses = `mb-6 w-full max-w-[85%] ml-auto mr-auto rounded-xl border ${borderClass} bg-card/80 backdrop-blur shadow-lg overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-500 ${agent.status === "done" ? 'opacity-80 scale-95 transition-all duration-1000' : 'scale-100 shadow-xl'}`;

  return (
    <div className={containerClasses}>
      <div 
        className={`flex items-center justify-between px-4 py-3 ${bgClass} cursor-pointer transition-colors hover:brightness-95`}
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <div className="relative flex h-8 w-8 items-center justify-center">
            {agent.status === "running" && (
              <span className={`absolute inline-flex h-full w-full animate-ping rounded-full ${bgClass} opacity-75`}></span>
            )}
            <div className={`relative flex h-8 w-8 items-center justify-center rounded-full ${bgClass} shadow-inner border border-white/20 dark:border-white/5`}>
              {agent.status === "running" ? (
                <Loader2 className={`h-4 w-4 ${colorClass} animate-spin`} />
              ) : (
                <Icon className={`h-4 w-4 ${colorClass}`} />
              )}
            </div>
          </div>
          <div>
            <h4 className={`text-sm font-semibold flex items-center gap-2 ${colorClass}`}>
              {agent.name}
              {agent.status === "running" ? (
                <span className="flex gap-0.5">
                  <span className="h-1 w-1 rounded-full bg-current animate-bounce" style={{ animationDelay: "0ms" }}></span>
                  <span className="h-1 w-1 rounded-full bg-current animate-bounce" style={{ animationDelay: "150ms" }}></span>
                  <span className="h-1 w-1 rounded-full bg-current animate-bounce" style={{ animationDelay: "300ms" }}></span>
                </span>
              ) : (
                <span className="text-xs text-muted-foreground font-normal ml-1 border rounded-md px-1 py-0.5 border-current/20">Task Complete</span>
              )}
            </h4>
            <p className="text-[10px] text-muted-foreground uppercase tracking-widest mt-0.5 font-medium">Helper Sub-agent</p>
          </div>
        </div>
        <button className="text-muted-foreground hover:text-foreground transition-colors p-1 bg-background/50 rounded-md shadow-sm">
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
      </div>

      {expanded && (
        <div className="p-4 space-y-3 max-h-[300px] overflow-y-auto bg-black/[0.02] dark:bg-white/[0.02]">
          {agent.tools.map((t, i) => (
            <div key={i} className="text-xs bg-background/80 rounded-lg border border-border/60 p-3 shadow-sm backdrop-blur-md animate-in fade-in slide-in-from-top-2 duration-300">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2 font-mono text-[11px] font-semibold text-foreground">
                  <span className={colorClass}>$</span> {t.name}
                </div>
                {t.status === "running" ? (
                  <span className="text-[10px] font-medium text-amber-500 animate-pulse flex items-center gap-1.5 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/20">
                    <Loader2 className="h-3 w-3 animate-spin" /> executing
                  </span>
                ) : (
                  <span className="text-[10px] font-medium text-emerald-500 flex items-center gap-1.5 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                    <CheckCircle2 className="h-3 w-3" /> done
                  </span>
                )}
              </div>
              <div className="font-mono text-[10px] text-muted-foreground opacity-90 break-all mb-2.5 bg-muted/50 p-1.5 rounded-md border border-border/50">
                {JSON.stringify(t.args)}
              </div>
              {t.result && (
                <div className="font-mono text-[10px] text-foreground/90 bg-black/5 dark:bg-black/40 rounded-md p-2 max-h-32 overflow-y-auto whitespace-pre-wrap border border-border/50 shadow-inner">
                  {t.result}
                </div>
              )}
            </div>
          ))}
          {agent.summary && (
            <div className={`text-xs rounded-lg border ${borderClass} p-3 mt-4 shadow-sm ${bgClass} animate-in fade-in zoom-in-95 duration-500`}>
              <div className="flex items-center gap-2 font-semibold mb-2">
                <Sparkles className="h-3.5 w-3.5" /> Final Summary
              </div>
              <div className="text-foreground/90 whitespace-pre-wrap leading-relaxed font-medium">
                {agent.summary}
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>
      )}
    </div>
  );
}
