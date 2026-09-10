import { compareCurrentJobEta, compareFreeAt, type EtaStatus } from '../../utils/etaSort';

export type PrinterState = 'error' | 'paused' | 'finished' | 'running' | 'preparing' | 'heating' | 'swapping' | 'idle' | 'maintenance' | 'offline' | 'cancelled' | 'drying';
export type QueueState = 'error' | 'paused' | 'plate' | 'active' | 'scheduled' | 'filament' | 'stagger' | 'uploading' | 'drying' | 'empty' | 'ready' | 'offline' | 'issues' | 'unknown' | 'maintenance' | 'swapping';
export type Tone = 'green' | 'red' | 'amber' | 'blue' | 'gray' | 'muted';
export type Page = 'printers' | 'queues';
export type Sort = 'attention' | 'eta' | 'freeAt' | 'name';

export interface SamplePrinter {
  id: number;
  name: string;
  model: string;
  image: string;
  location: 'workshopA' | 'workshopB' | 'workshopC';
  printer: PrinterState;
  queue: QueueState;
  printerReason: string;
  queueReason: string;
  remaining: number | null;
  queueMinutes: number | null;
  progress: number;
  pending: number;
  job: string;
  material: string;
  filament: string;
}

export const printerTones: Record<PrinterState, Tone> = {
  error: 'red', paused: 'amber', finished: 'blue', running: 'green',
  preparing: 'green', heating: 'green', swapping: 'blue', idle: 'gray',
  maintenance: 'muted', offline: 'muted', cancelled: 'amber', drying: 'blue',
};
export const queueTones: Record<QueueState, Tone> = {
  error: 'red', paused: 'amber', plate: 'blue', active: 'green', scheduled: 'blue',
  filament: 'amber', stagger: 'blue', uploading: 'green', drying: 'blue',
  empty: 'gray', ready: 'green', offline: 'muted', issues: 'amber', unknown: 'blue',
  maintenance: 'muted', swapping: 'blue',
};

type Scenario = [PrinterState, QueueState, string, string, number | null, number | null, number, number];
const scenarios: Scenario[] = [
  ['error', 'error', 'ams', 'ams', null, null, 42, 4],
  ['paused', 'filament', 'runout', 'filament', null, null, 63, 3],
  ['finished', 'plate', 'plate', 'plate', 0, null, 100, 6],
  ['running', 'active', 'printing', 'printing', 5, 95, 96, 3],
  ['running', 'paused', 'printing', 'queuedPause', 7, null, 93, 5],
  ['running', 'active', 'printing', 'printing', 14, 224, 87, 7],
  ['heating', 'active', 'heating', 'heating', null, null, 0, 2],
  ['preparing', 'active', 'preparing', 'preparing', null, null, 0, 4],
  ['swapping', 'swapping', 'swap', 'swap', null, null, 0, 8],
  ['idle', 'scheduled', 'empty', 'scheduled', null, 188, 0, 2],
  ['drying', 'drying', 'dry', 'dry', null, null, 0, 3],
  ['running', 'unknown', 'printing', 'unknown', 45, null, 71, 2],
  ['idle', 'empty', 'empty', 'empty', null, 0, 0, 0],
  ['cancelled', 'issues', 'cancelled', 'failed', null, null, 34, 1],
  ['maintenance', 'maintenance', 'maintenance', 'maintenance', null, null, 0, 0],
  ['offline', 'offline', 'offline', 'offline', null, null, 0, 2],
  ['idle', 'stagger', 'empty', 'stagger', null, null, 0, 2],
  ['idle', 'uploading', 'empty', 'upload', null, null, 0, 4],
  ['idle', 'ready', 'empty', 'ready', null, 80, 0, 2],
  ['running', 'empty', 'printing', 'empty', 28, 28, 66, 0],
];
const models = [['P1S', 'p1s'], ['X1 Carbon', 'x1c'], ['A1', 'a1'], ['H2D', 'h2d'], ['P2S', 'p2s'], ['A1 mini', 'a1mini']];
const jobs = ['bracket', 'housing', 'mount', 'tray', 'clip', 'cover'];

export const samples: SamplePrinter[] = Array.from({ length: 50 }, (_, i) => {
  // Keep every exceptional state once, then fill the farm with ordinary running printers.
  const scenario: Scenario = i < scenarios.length ? scenarios[i] : ['running', 'active', 'printing', 'printing', 18 + (i - 20) * 9, 100 + (i - 20) * 23, 86 - (i % 12) * 5, 1 + i % 7];
  const [printer, queue, printerReason, queueReason, remaining, queueMinutes, progress, pending] = scenario;
  const [model, image] = models[i % models.length];
  const location = i < 6 || (i >= 20 && i < 31) ? 'workshopA' : i < 12 || (i >= 31 && i < 42) ? 'workshopB' : 'workshopC';
  return {
    id: i + 1, name: `${location === 'workshopA' ? 'A' : location === 'workshopB' ? 'B' : 'C'}-${String(i + 1).padStart(2, '0')}`,
    model, image, location,
    printer, queue, printerReason, queueReason, remaining, queueMinutes, progress, pending,
    job: jobs[i % jobs.length], material: i % 3 === 0 ? 'PETG' : 'PLA',
    filament: ['#dae1e8', '#db754b', '#242b35', '#6d9cbe'][i % 4],
  };
});

export function needsAttention(p: SamplePrinter, page: Page): boolean {
  return page === 'printers'
    ? ['error', 'paused', 'finished', 'cancelled'].includes(p.printer)
    : ['error', 'paused', 'plate', 'filament', 'issues'].includes(p.queue);
}

function etaStatus(p: SamplePrinter): EtaStatus {
  return { connected: p.printer !== 'offline', state: p.printer === 'running' ? 'RUNNING' : 'IDLE', remaining_time: p.remaining };
}

export function orderedSamples(items: SamplePrinter[], page: Page, sort: Sort): SamplePrinter[] {
  return [...items].sort((a, b) => {
    const byName = a.name.localeCompare(b.name, undefined, { numeric: true });
    if (sort === 'name') return byName;
    if (sort === 'eta') return compareCurrentJobEta(etaStatus(a), etaStatus(b)) || byName;
    if (sort === 'freeAt') {
      const row = (p: SamplePrinter) => ({ free_seconds: (p.queueMinutes ?? 0) * 60, unknown_prints: p.queueMinutes === null ? p.pending : 0 });
      return compareFreeAt(row(a), row(b), etaStatus(a), etaStatus(b)) || byName;
    }
    const tier = (p: SamplePrinter) => {
      if ((page === 'printers' ? p.printer : p.queue) === 'error') return 0;
      if ((page === 'printers' ? p.printer === 'finished' : p.queue === 'plate')) return 2;
      if (needsAttention(p, page)) return 1;
      if (p.printer === 'offline' || p.printer === 'maintenance') return 6;
      if (p.printer === 'running') return 3;
      if (p.pending > 0 || p.printer !== 'idle') return 4;
      return 5;
    };
    return tier(a) - tier(b) || (a.remaining ?? Infinity) - (b.remaining ?? Infinity) || byName;
  });
}
