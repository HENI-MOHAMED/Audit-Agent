import { useState, useRef, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Send, Bot, User, Loader2 } from "lucide-react";
import { createChatWebSocket } from "@/services/api";
import { useSessionStore } from "@/stores/sessionStore";
import { ThinkingModeSelector } from "@/components/ThinkingModeSelector";
import { ThinkingWindow, ToolEvent } from "@/components/ThinkingWindow";
import { AgentOrb, AgentState } from "@/components/AgentOrb";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function ChatPage() {
  const { sessionId, setSessionId } = useSessionStore();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState("fast");
  const [loading, setLoading] = useState(false);
  
  // Streaming state
  const [activeTools, setActiveTools] = useState<ToolEvent[]>([]);
  const [activeAgents, setActiveAgents] = useState<AgentState[]>([]);
  
  const bottomRef = useRef<HTMLDivElement>(null);
  const loadingRef = useRef<boolean>(false);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, activeTools, activeAgents]);

  const handleSend = () => {
    if (!input.trim() || loadingRef.current) return;
    const userMsg = input.trim();
    setInput("");
    
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setLoading(true);
    loadingRef.current = true;
    
    setActiveTools([]);
    setActiveAgents([]);

    createChatWebSocket(
      userMsg,
      sessionId ?? undefined,
      mode,
      (event) => {
        if (event.type === "session_id") {
          setSessionId(event.session_id);
        }
        else if (event.type === "message") {
          setMessages((prev) => [...prev, { role: "assistant", content: event.content }]);
          setLoading(false);
          loadingRef.current = false;
        } 
        else if (event.type === "tool_call") {
          setActiveTools(prev => [...prev, { 
            id: Math.random().toString(), 
            name: event.name, 
            args: event.args, 
            status: "running" 
          }]);
        }
        else if (event.type === "tool_result") {
          setActiveTools(prev => {
            const newTools = [...prev];
            const tIdx = newTools.map(t => t.name).lastIndexOf(event.name);
            if (tIdx >= 0) {
              newTools[tIdx] = { ...newTools[tIdx], result: event.preview, status: "done" };
            }
            return newTools;
          });
        }
        else if (event.type === "agent_start") {
          setActiveAgents(prev => [...prev, {
            id: Math.random().toString(),
            name: event.agent,
            status: "running",
            tools: []
          }]);
        }
        else if (event.type === "agent_tool_call") {
          setActiveAgents(prev => {
            const newAgents = [...prev];
            const aIdx = newAgents.map(a => a.name).lastIndexOf(event.agent);
            if (aIdx >= 0) {
              newAgents[aIdx].tools.push({
                name: event.name,
                args: event.args,
                status: "running"
              });
            }
            return newAgents;
          });
        }
        else if (event.type === "agent_tool_result") {
          setActiveAgents(prev => {
            const newAgents = [...prev];
            const aIdx = newAgents.map(a => a.name).lastIndexOf(event.agent);
            if (aIdx >= 0) {
               const agent = newAgents[aIdx];
               const tIdx = agent.tools.map(t => t.name).lastIndexOf(event.name);
               if (tIdx >= 0) {
                 agent.tools[tIdx].status = "done";
                 agent.tools[tIdx].result = event.preview;
               }
            }
            return newAgents;
          });
        }
        else if (event.type === "agent_done") {
          setActiveAgents(prev => {
            const newAgents = [...prev];
            const aIdx = newAgents.map(a => a.name).lastIndexOf(event.agent);
            if (aIdx >= 0) {
               newAgents[aIdx].status = "done";
               newAgents[aIdx].summary = event.summary;
            }
            return newAgents;
          });
        }
        else if (event.type === "error") {
          setMessages((prev) => [...prev, { role: "assistant", content: `Error: ${event.message}` }]);
          setLoading(false);
          loadingRef.current = false;
        }
      },
      () => {
        if (loadingRef.current) {
           setLoading(false);
           loadingRef.current = false;
        }
      },
      (err) => {
        console.error("WebSocket error", err);
        setMessages((prev) => [...prev, { role: "assistant", content: `Connection error occurred.` }]);
        setLoading(false);
        loadingRef.current = false;
      }
    );
  };

  return (
    <div className="flex flex-col h-[calc(100vh-5rem)] w-full max-w-5xl mx-auto">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">AI Chat</h2>
          <p className="text-muted-foreground text-sm">
            Ask questions about your financial data
            {sessionId && (
              <span className="ml-2 text-xs font-mono bg-secondary px-2 py-0.5 rounded">
                Session: {sessionId.slice(0, 8)}…
              </span>
            )}
          </p>
        </div>
        <ThinkingModeSelector mode={mode} setMode={setMode} disabled={loading} />
      </div>

      <Card className="flex-1 flex flex-col overflow-hidden">
        <CardContent className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm h-full">
              <div className="text-center space-y-2">
                <Bot className="h-10 w-10 mx-auto opacity-30" />
                <p>Start a conversation with the AI Audit Agent</p>
              </div>
            </div>
          )}
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {msg.role === "assistant" && (
                <div className="h-7 w-7 rounded-full bg-primary/10 flex items-center justify-center shrink-0 mt-1">
                  <Bot className="h-4 w-4 text-primary" />
                </div>
              )}
              <div
                className={`max-w-[80%] rounded-xl px-4 py-2.5 text-sm whitespace-pre-wrap ${
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary text-secondary-foreground"
                }`}
              >
                {msg.content}
              </div>
              {msg.role === "user" && (
                <div className="h-7 w-7 rounded-full bg-primary flex items-center justify-center shrink-0 mt-1">
                  <User className="h-4 w-4 text-primary-foreground" />
                </div>
              )}
            </div>
          ))}
          {activeTools.length > 0 && <ThinkingWindow toolEvents={activeTools} />}
          {activeAgents.length > 0 && activeAgents.map(a => <AgentOrb key={a.id} agent={a} />)}
          {loading && activeTools.length === 0 && activeAgents.length === 0 && (
            <div className="flex gap-3 animate-in fade-in duration-300">
              <div className="h-7 w-7 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                <Loader2 className="h-4 w-4 text-primary animate-spin" />
              </div>
              <div className="bg-secondary rounded-xl px-4 py-2.5 text-sm text-muted-foreground shadow-sm">
                Thinking…
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </CardContent>

        <div className="p-4 border-t border-border">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="flex gap-2"
          >
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about invoices, suppliers, risks…"
              className="flex-1 h-10"
              disabled={loading}
            />
            <Button type="submit" size="icon" className="h-10 w-10" disabled={loading || !input.trim()}>
              <Send className="h-4 w-4" />
            </Button>
          </form>
        </div>
      </Card>
    </div>
  );
}
