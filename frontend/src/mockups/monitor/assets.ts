declare global {
  interface Window {
    __BAMDUDE_MONITOR_ASSETS__?: Record<string, string>;
  }
}

/** The portable export supplies data URLs; Vite uses the existing public assets. */
export function monitorAsset(path: string): string {
  return window.__BAMDUDE_MONITOR_ASSETS__?.[path] ?? path;
}
