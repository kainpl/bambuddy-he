import { useCallback, useEffect, useState } from 'react';
import { api, ApiError, type FarmForecast } from '../../api/client';
import type { MonitorSnapshot, MonitorView } from './types';

async function kioskRead<T>(endpoint: 'snapshot' | 'forecast', token: string, signal: AbortSignal, view?: MonitorView): Promise<T> {
  const response = await fetch(`/api/v1/monitor/kiosk/${endpoint}${view ? `?view=${view}` : ''}`, {
    headers: { Authorization: `Bearer ${token}` }, signal, credentials: 'omit', cache: 'no-store', referrerPolicy: 'no-referrer',
  });
  // Never include a server message, URL or token in a kiosk error/cache key.
  if (!response.ok) throw new ApiError('Monitor request failed', response.status);
  return response.json();
}

export interface MonitorResource<T> { data?: T; error: unknown; updatedAt: number; loading: boolean; terminal: boolean }
const empty = { error: null, updatedAt: 0, loading: true, terminal: false };
export function terminalError(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 401 || error.status === 403);
}

// The monitor keeps its small projection locally, never in PrinterStatus's
// full-object cache. Exactly one in-flight request per feed; all timers and
// listeners belong to this window and are disposed with it.
export function useMonitorResource<T>(read: (signal: AbortSignal) => Promise<T>, period: number, enabled: boolean, authenticated: boolean) {
  const [reload, setReload] = useState(0);
  const [state, setState] = useState<MonitorResource<T> & { read?: typeof read }>({ ...empty });
  useEffect(() => {
    if (!enabled) return;
    let disposed = false, busy = false, stopped = false, failures = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;
    const run = async () => {
      if (disposed || busy || stopped) return;
      clearTimeout(timer);
      busy = true;
      controller = new AbortController();
      const timeout = setTimeout(() => controller?.abort(), 10000);
      try {
        const data = await read(controller.signal);
        if (!disposed) {
          failures = 0;
          setState({ data, read, error: null, updatedAt: Date.now(), loading: false, terminal: false });
        }
      } catch (error) {
        if (!disposed) {
          failures++;
          stopped = terminalError(error);
          setState(old => ({ ...(stopped || old.read !== read ? empty : old), read,
            error, loading: false, terminal: stopped }));
          if (stopped) window.dispatchEvent(new CustomEvent('bamdude:monitor-invalidated', { detail: error }));
        }
      } finally {
        clearTimeout(timeout);
        busy = false;
        if (!disposed && !stopped) timer = setTimeout(run, Math.min(30000, period * 2 ** Math.min(failures, 3)));
      }
    };
    const resume = () => { if (document.visibilityState !== 'hidden') void run(); };
    const stop = (error: unknown) => {
      stopped = true; disposed = true;
      clearTimeout(timer); controller?.abort();
      setState({ ...empty, read, loading: false, terminal: true, error });
    };
    const invalidate = () => { if (authenticated) stop(new ApiError('Signed out', 401)); };
    const monitorInvalidated = (event: Event) => stop((event as CustomEvent).detail);
    const storage = (e: StorageEvent) => { if (e.key === 'auth_token' && e.newValue === null) invalidate(); };
    document.addEventListener('visibilitychange', resume);
    window.addEventListener('online', resume);
    window.addEventListener('bamdude:auth-invalidated', invalidate);
    window.addEventListener('bamdude:monitor-invalidated', monitorInvalidated);
    window.addEventListener('storage', storage);
    void run();
    return () => {
      disposed = true; clearTimeout(timer); controller?.abort();
      document.removeEventListener('visibilitychange', resume);
      window.removeEventListener('online', resume);
      window.removeEventListener('bamdude:auth-invalidated', invalidate);
      window.removeEventListener('bamdude:monitor-invalidated', monitorInvalidated);
      window.removeEventListener('storage', storage);
    };
  }, [read, period, enabled, authenticated, reload]);
  const resource = state.read === read && enabled ? state : { ...empty };
  return { ...resource, retry: () => setReload(n => n + 1) };
}

export function useMonitorSnapshot(view: MonitorView, token: string | null) {
  const read = useCallback((signal: AbortSignal) => token !== null ? kioskRead<MonitorSnapshot>('snapshot', token, signal, view) :
    api.getMonitorSnapshot(view, signal), [view, token]);
  return useMonitorResource(read, 5000, true, token === null);
}

export function useMonitorForecast(token: string | null, enabled: boolean) {
  const read = useCallback((signal: AbortSignal) => token !== null ? kioskRead<FarmForecast>('forecast', token, signal) :
    api.getMonitorForecast(signal), [token]);
  return useMonitorResource(read, 30000, enabled, token === null);
}
