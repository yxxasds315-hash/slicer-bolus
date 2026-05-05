import { useCallback, useEffect, useRef, useState } from 'react';
import type { LogEntry } from '../types';

export function useSSELog(status: string) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const sourceRef = useRef<EventSource | null>(null);
  useEffect(() => {
    if (status !== 'running') { if (sourceRef.current) { sourceRef.current.close(); sourceRef.current = null; } return; }
    const es = new EventSource('/api/logs/stream');
    sourceRef.current = es;
    es.onmessage = (event) => { try { setLogs((prev) => [...prev, JSON.parse(event.data)]); } catch { } };
    es.onerror = () => { setLogs((prev) => [...prev, { timestamp: new Date().toLocaleTimeString(), level: 'error', message: '日志流连接断开' }]); es.close(); };
    return () => es.close();
  }, [status]);
  const clearLogs = useCallback(() => setLogs([]), []);
  return { logs, clearLogs };
}
