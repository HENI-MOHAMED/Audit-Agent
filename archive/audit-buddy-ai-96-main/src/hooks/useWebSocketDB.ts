import { useCallback, useEffect, useRef, useState } from "react";

type WSMessageOk = { ok: true; data: unknown; count?: number };
type WSMessageErr = { ok: false; error: string };
type WSMessage = WSMessageOk | WSMessageErr;

let sharedWs: WebSocket | null = null;
let refCount = 0;
let pendingCallbacks: Map<number, (msg: WSMessage) => void> = new Map();
let msgId = 0;

function getWs(): WebSocket {
  if (sharedWs && sharedWs.readyState <= WebSocket.OPEN) return sharedWs;

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/api/ws/db`;
  sharedWs = new WebSocket(wsUrl);

  sharedWs.onmessage = (event) => {
    const data = JSON.parse(event.data) as WSMessage;
    // Dispatch to the oldest pending callback (FIFO since WS is ordered)
    const entries = Array.from(pendingCallbacks.entries());
    if (entries.length > 0) {
      const [id, cb] = entries[0];
      pendingCallbacks.delete(id);
      cb(data);
    }
  };

  sharedWs.onerror = () => {
    pendingCallbacks.forEach((cb) => cb({ ok: false, error: "WebSocket error" }));
    pendingCallbacks.clear();
  };

  sharedWs.onclose = () => {
    sharedWs = null;
  };

  return sharedWs;
}

function sendMessage(payload: Record<string, unknown>): Promise<WSMessage> {
  return new Promise((resolve, reject) => {
    const ws = getWs();
    const id = ++msgId;

    const send = () => {
      pendingCallbacks.set(id, resolve);
      ws.send(JSON.stringify(payload));
    };

    if (ws.readyState === WebSocket.OPEN) {
      send();
    } else {
      ws.addEventListener("open", send, { once: true });
      ws.addEventListener("error", () => reject(new Error("WS connect failed")), { once: true });
    }
  });
}

export function executeSql(sql: string) {
  return sendMessage({ action: "query", sql });
}

export function useDbTables() {
  const [tables, setTables] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await sendMessage({ action: "tables" });
        if (res.ok) setTables(res.data as string[]);
        else setError((res as WSMessageErr).error);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refCount++;
    refresh();
    return () => {
      refCount--;
      if (refCount === 0 && sharedWs) {
        sharedWs.close();
        sharedWs = null;
      }
    };
  }, [refresh]);

  return { tables, loading, error, refresh };
}

export function useDbSchema(table: string) {
  const [schema, setSchema] = useState<{ name: string; type: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!table) return;
    refCount++;
    setLoading(true);
    sendMessage({ action: "schema", table })
      .then((res) => {
        if (res.ok) setSchema((res.data as any[]).map((c) => ({ name: c.name, type: c.type })));
        else setError((res as WSMessageErr).error);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    return () => { refCount--; };
  }, [table]);

  return { schema, loading, error };
}

export function useDbQuery<T = Record<string, unknown>>(sql: string, enabled = true) {
  const [data, setData] = useState<T[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [count, setCount] = useState(0);

  const execute = useCallback(async () => {
    if (!sql || !enabled) return;
    setLoading(true);
    setError(null);
    try {
      const res = await sendMessage({ action: "query", sql });
      if (res.ok) {
        setData(res.data as T[]);
        setCount(res.count ?? (res.data as T[]).length);
      } else {
        setError((res as WSMessageErr).error);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [sql, enabled]);

  useEffect(() => {
    refCount++;
    execute();
    return () => { refCount--; };
  }, [execute]);

  return { data, loading, error, count, refetch: execute };
}
