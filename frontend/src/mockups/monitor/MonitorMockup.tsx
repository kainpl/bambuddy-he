import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertTriangle, ArrowDownWideNarrow, CalendarClock, Check,
  CheckCircle2, ChevronRight, Clock3, ExternalLink, Flame, Grid2X2,
  Layers, LayoutGrid, ListOrdered, MapPin, Maximize2, Minimize2,
  Pause, Play, Printer, Search, Thermometer, Upload,
  Wifi, WifiOff, Wrench, XCircle, Zap, type LucideIcon,
} from 'lucide-react';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { CardSizeSwitch } from '../../components/CardSizeSwitch';
import { Modal } from '../../components/Modal';
import { monitorAsset } from './assets';
import { needsAttention, orderedSamples, printerTones, queueTones, samples, type Page, type SamplePrinter, type Sort, type Tone } from './fixtures';

type View = 'overview' | 'fleet' | 'locations';
const locations = ['workshopA', 'workshopB', 'workshopC'] as const;
const stateIcons: Record<string, LucideIcon> = {
  error: AlertTriangle, paused: Pause, finished: CheckCircle2, plate: CheckCircle2,
  running: Printer, active: Play, preparing: Layers, heating: Flame,
  swapping: Layers, idle: Check, ready: Check, maintenance: Wrench,
  offline: WifiOff, cancelled: XCircle, drying: Thermometer, filament: AlertTriangle,
  stagger: Zap, uploading: Upload, scheduled: CalendarClock, empty: Layers,
  issues: AlertTriangle, unknown: Clock3,
};

function useMonitorText() {
  const { t } = useTranslation();
  return (key: string) => t(`monitor.${key}`);
}

function duration(minutes: number, min: string, hour: string) {
  return minutes < 60 ? `${minutes} ${min}` : `${Math.floor(minutes / 60)} ${hour} ${minutes % 60 ? `${minutes % 60} ${min}` : ''}`.trim();
}

// A fixed clock makes every variant a comparable snapshot, including detached windows.
function clockAt(minutes: number) {
  const total = 18 * 60 + 20 + minutes;
  return `${String(Math.floor(total / 60) % 24).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}

function Status({ state, prefix, tone }: { state: string; prefix: 'p' | 'q'; tone: Tone }) {
  const m = useMonitorText();
  const Icon = stateIcons[state] ?? Printer;
  return <span className={`monitor-status tone-${tone}`}><Icon size={13} aria-hidden="true" />{m(`${prefix}.${state}`)}</span>;
}

function MonitorTile({ printer: p, page, compact, stale, onOpen }: {
  printer: SamplePrinter; page: Page; compact: boolean; stale: boolean; onOpen: () => void;
}) {
  const m = useMonitorText();
  const state = page === 'printers' ? p.printer : p.queue;
  const tone = page === 'printers' ? printerTones[p.printer] : queueTones[p.queue];
  const Icon = stateIcons[state] ?? Printer;
  const running = p.printer === 'running';
  const showTime = page === 'printers' ? running && p.remaining !== null : p.queueMinutes !== null && p.queueMinutes > 0;
  const minutes = page === 'printers' ? p.remaining : p.queueMinutes;
  const explanation = page === 'printers' ? p.printerReason : p.queueReason;
  const hasJob = !['idle', 'maintenance', 'offline', 'drying'].includes(p.printer);

  return (
    <Card
      className={`monitor-tile tone-${tone} ${compact ? 'is-compact' : ''} ${stale ? 'is-stale' : ''}`}
      role="button" tabIndex={0} onClick={onOpen}
      aria-label={`${p.name} · ${p.model} · ${m(`${page === 'printers' ? 'p' : 'q'}.${state}`)}`}
      onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onOpen(); } }}
      data-printer={p.id} data-tone={tone}
    >
      <div className="monitor-tile-top">
        <div className="monitor-identity"><strong>{p.name}</strong><span>{p.model}</span></div>
        {compact ? <Icon className="monitor-state-icon" size={17} aria-hidden="true" /> : <img src={monitorAsset(`/img/printers/${p.image}.png`)} alt="" />}
      </div>
      <div className="monitor-tile-status"><Status state={state} prefix={page === 'printers' ? 'p' : 'q'} tone={tone} /></div>
      <div className={`monitor-headline ${!showTime ? 'is-message' : ''}`}>
        {showTime && minutes !== null ? <><span>
          {minutes >= 60 && <>{Math.floor(minutes / 60)} <em>{m('hour')}</em> </>}
          {(minutes % 60 > 0 || minutes < 60) && <>{minutes % 60} <em>{m('min')}</em></>}
        </span><small>{page === 'printers' ? m('remaining') : m('availableAt')}</small></> : <><span>{compact ? m(`${page === 'printers' ? 'p' : 'q'}.${state}`) : m(`reason.${explanation}`)}</span><small>{stale ? m('frozen') : '\u00a0'}</small></>}
      </div>
      <div className="monitor-jobline">
        {page === 'queues' ? <><Printer size={12} aria-hidden="true" /><span>{m(`p.${p.printer}`)}{running && p.remaining !== null ? ` · ${duration(p.remaining, m('min'), m('hour'))}` : ''}</span></> : <><span className="monitor-filament" style={{ backgroundColor: p.filament }} /><span>{hasJob ? `${m(`jobs.${p.job}`)} · ${p.material}` : m('noJob')}</span></>}
      </div>
      <div className="monitor-progress" role="progressbar" aria-label={`${m('job')} ${p.name}`} aria-valuenow={p.progress} aria-valuemin={0} aria-valuemax={100}>
        <span style={{ width: `${p.progress}%` }} />
      </div>
      <div className="monitor-tile-bottom">
        {page === 'printers' ? <><span>{hasJob ? `${p.progress}%` : '—'}</span><span>{running && p.remaining !== null ? `${m('finishAt')} ${clockAt(p.remaining)}` : m(`p.${p.printer}`)}</span></> : <><span><Layers size={12} aria-hidden="true" />{p.pending} {m('pending').toLowerCase()}</span><span>{p.queueMinutes !== null && p.queueMinutes > 0 ? clockAt(p.queueMinutes) : p.pending ? m('noEta') : '—'}</span></>}
      </div>
    </Card>
  );
}

function StateDetails({ printer: p, onClose }: { printer: SamplePrinter; onClose: () => void }) {
  const m = useMonitorText();
  const upcoming = Math.min(p.pending, 3);
  const hasJob = !['idle', 'offline', 'maintenance', 'drying'].includes(p.printer);
  return <Modal title={`${p.name} · ${p.model}`} icon={<Printer size={20} />} onClose={onClose} size="2xl"
    footer={<Button variant="secondary" onClick={onClose}>{m('close')}</Button>}>
    <div className="monitor-detail">
      <div className="monitor-detail-statuses">
        <div><small>{m('printerState')}</small><Status state={p.printer} prefix="p" tone={printerTones[p.printer]} /><p>{m(`reason.${p.printerReason}`)}</p></div>
        <div><small>{m('queueState')}</small><Status state={p.queue} prefix="q" tone={queueTones[p.queue]} /><p>{m(`reason.${p.queueReason}`)}</p></div>
      </div>
      {(p.queue === 'paused' || p.queue === 'plate') && <p className="monitor-detail-callout"><AlertTriangle size={17} />{m(p.queue === 'paused' ? 'queuePausedNote' : 'plateNote')}</p>}
      <div className="monitor-detail-job">
        <img src={monitorAsset(`/img/printers/${p.image}.png`)} alt={p.model} />
        <div><small>{m('job')}</small><strong>{hasJob ? `${m(`jobs.${p.job}`)} · ${p.material}` : m('noJob')}</strong>{hasJob && <span>{m('layers')}: {Math.round(p.progress * 3.2)} / 320</span>}
          {hasJob && <div className="monitor-progress"><span style={{ width: `${p.progress}%`, backgroundColor: 'var(--status-ok)' }} /></div>}
        </div>
        {hasJob && <b>{p.progress}%</b>}
      </div>
      <div className="monitor-next-title"><h3>{m('next')}</h3><span>{p.pending} {m('pending').toLowerCase()}</span></div>
      {upcoming ? Array.from({ length: upcoming }, (_, i) => <div className="monitor-next-row" key={i}>
        <span className="monitor-order">{i + 1}</span><Layers size={18} /><div><strong>{m(`jobs.${['housing', 'clip', 'bracket'][i]}`)} · {String(i + 1).padStart(2, '0')}</strong><small>{p.material} · {m('batch')} #{320 + p.id}</small></div>
        <span>{p.queueMinutes !== null ? duration(Math.max(1, Math.round((p.queueMinutes - (p.remaining ?? 0)) / p.pending)), m('min'), m('hour')) : m('noEta')}</span>
      </div>) : <p className="monitor-empty-queue">{m('noNext')}</p>}
      <p className="monitor-demo-note">{m('demoNote')}</p>
    </div>
  </Modal>;
}

export function MonitorMockup() {
  const { i18n } = useTranslation();
  const m = useMonitorText();
  const params = new URLSearchParams(location.search);
  const [page, setPage] = useState<Page>(() => params.get('page') === 'queues' ? 'queues' : 'printers');
  const [view, setView] = useState<View>(() => params.get('view') === 'fleet' ? 'fleet' : params.get('view') === 'locations' ? 'locations' : 'overview');
  const [sort, setSort] = useState<Sort>(() => (['attention', 'eta', 'freeAt', 'name'] as const).find(v => v === params.get('sort')) ?? 'attention');
  const [size, setSize] = useState(2);
  const [search, setSearch] = useState('');
  const [stale, setStale] = useState(false);
  const [solid, setSolid] = useState(() => params.get('color') === 'solid');
  const [selected, setSelected] = useState<SamplePrinter | null>(null);
  const [full, setFull] = useState(false);
  const [notice, setNotice] = useState('');
  const gridRef = useRef<HTMLDivElement>(null);
  const [columns, setColumns] = useState(10);
  const compact = view === 'fleet';
  const source = compact ? samples : samples.slice(0, 20);
  const filtered = source.filter(p => `${p.name} ${p.model} ${m(p.location)}`.toLowerCase().includes(search.toLowerCase()));
  const ordered = orderedSamples(filtered, page, sort);
  const stats = {
    all: source.length,
    printing: source.filter(p => p.printer === 'running').length,
    issues: source.filter(p => needsAttention(p, page)).length,
    ready: source.filter(p => p.printer === 'idle').length,
    waiting: source.reduce((sum, p) => sum + p.pending, 0),
  };

  useEffect(() => {
    const url = new URL(location.href);
    url.search = new URLSearchParams({ page, view, sort, lang: i18n.language, color: solid ? 'solid' : 'tinted' }).toString();
    history.replaceState(null, '', url);
    document.documentElement.lang = i18n.language;
    document.title = `BamDude · ${i18n.t('monitor.title')} · ${i18n.t(`monitor.${page}`)}`;
  }, [page, view, sort, i18n, i18n.language, solid]);

  useEffect(() => {
    const target = gridRef.current;
    if (!target) return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      let next = width >= 1600 ? 10 : width >= 1150 ? 8 : width >= 850 ? 6 : width >= 600 ? 4 : 2;
      if (width >= 1100 && compact) {
        const count = Math.max(1, ordered.length);
        const candidates = Array.from({ length: 7 }, (_, i) => i + 6).filter(n => {
          return (width - (n - 1) * 8) / n >= 118 && (height - (Math.ceil(count / n) - 1) * 8) / Math.ceil(count / n) >= 116;
        });
        if (candidates.length) next = candidates.reduce((best, n) => Math.abs(n - 10) < Math.abs(best - 10) ? n : best);
      }
      setColumns(next);
    });
    observer.observe(target);
    return () => observer.disconnect();
  }, [view, compact, ordered.length]);

  useEffect(() => {
    const update = () => setFull(Boolean(document.fullscreenElement));
    document.addEventListener('fullscreenchange', update);
    return () => document.removeEventListener('fullscreenchange', update);
  }, []);

  const fullscreen = async () => {
    try { if (document.fullscreenElement) await document.exitFullscreen(); else await document.documentElement.requestFullscreen(); }
    catch { setNotice(m('fullscreenUnavailable')); }
  };
  const popout = () => {
    const popup = window.open(location.href, '_blank', 'popup,width=1600,height=1000');
    if (popup) popup.opener = null;
    else setNotice(m('popoutBlocked'));
  };
  const renderTiles = (items: SamplePrinter[]) => items.map(p => <MonitorTile key={p.id} printer={p} page={page} compact={compact} stale={stale} onOpen={() => setSelected(p)} />);
  const gridStyle = { '--monitor-columns': columns, '--monitor-rows': Math.max(1, Math.ceil(ordered.length / columns)), '--monitor-min-width': `${[200, 265, 330, 430][size - 1]}px` } as CSSProperties;

  return <div className={`monitor-app ${compact ? 'monitor-fleet' : ''} ${solid ? 'monitor-solid' : ''}`}>
    <div className="monitor-preview-bar"><span><span className="monitor-preview-dot" />{m('demo')}</span><span>{m('screenshot')} 09.09.2026 · 18:20 <button onClick={() => void i18n.changeLanguage(i18n.language === 'uk' ? 'en' : 'uk')} aria-label={i18n.language === 'uk' ? 'English' : 'Українська'}>{i18n.language === 'uk' ? 'EN' : 'UK'}</button></span></div>
    <header className="monitor-header">
      <div className="monitor-brand"><img src={monitorAsset('/img/brand/mark-on-dark-64.png')} alt="BamDude" /><div><strong>BamDude</strong><span>{m('title')}</span></div></div>
      <nav className="monitor-page-tabs" aria-label={m('title')}>
        <button aria-current={page === 'printers' ? 'page' : undefined} onClick={() => setPage('printers')}><Printer size={17} />{m('printers')}</button>
        <button aria-current={page === 'queues' ? 'page' : undefined} onClick={() => setPage('queues')}><ListOrdered size={17} />{m('queues')}</button>
      </nav>
      <div className="monitor-window-actions">
        <button className={`monitor-connection ${stale ? 'is-offline' : ''}`} onClick={() => setStale(!stale)} title={m(stale ? 'restoreConnection' : 'simulateDisconnect')} aria-label={m(stale ? 'restoreConnection' : 'simulateDisconnect')}>
          {stale ? <WifiOff size={14} /> : <Wifi size={14} />}<span>{m(stale ? 'stale' : 'online')}</span>
        </button>
        <Button variant="outline" size="sm" onClick={popout} title={m('popout')} aria-label={m('popout')}><ExternalLink size={15} /><span>{m('popout')}</span></Button>
        <Button variant="outline" size="sm" onClick={() => void fullscreen()} title={m(full ? 'exitFullscreen' : 'fullscreen')} aria-label={m(full ? 'exitFullscreen' : 'fullscreen')}>{full ? <Minimize2 size={16} /> : <Maximize2 size={16} />}</Button>
      </div>
    </header>

    <main className="monitor-main">
      <div className="monitor-heading-row"><div><h1>{m(page)}</h1><span className="monitor-page-caption">{m(view === 'overview' ? 'previewCount' : view === 'fleet' ? 'fleetCount' : 'locationCount')}</span></div>
        <div className="monitor-stats" aria-label={m('screenshot')}>
          {(['all', 'printing', 'issues', page === 'queues' ? 'waiting' : 'ready'] as const).map(key => <span key={key} className={key === 'issues' ? 'monitor-stat-warning' : ''}><i className={`monitor-stat-dot stat-${key}`} /><b>{stats[key]}</b>{m(key)}</span>)}
        </div>
      </div>
      <div className="monitor-toolbar">
        <div className="monitor-view-tabs" role="group" aria-label={m('title')}>
          {([{ value: 'overview', icon: LayoutGrid }, { value: 'fleet', icon: Grid2X2 }, { value: 'locations', icon: MapPin }] as const).map(({ value, icon: Icon }) => <button key={value} aria-pressed={view === value} onClick={() => setView(value)}><Icon size={15} />{m(value)}</button>)}
        </div>
        <div className="monitor-toolbar-end">
          <div className="monitor-search"><Search size={15} /><input value={search} onChange={e => setSearch(e.target.value)} placeholder={m('search')} aria-label={m('search')} /></div>
          <label className="monitor-sort"><ArrowDownWideNarrow size={15} /><select value={sort} onChange={e => setSort(e.target.value as Sort)} aria-label={m('sort')} title={sort === 'attention' ? m('attentionHint') : m(sort)}>{(['attention', 'eta', 'freeAt', 'name'] as const).map(key => <option key={key} value={key}>{m(key)}</option>)}</select></label>
          {!compact && <CardSizeSwitch value={size} onChange={setSize} />}
          <button className="monitor-color-switch" aria-label={m('accent')} aria-pressed={solid} title={`${m('accent')}: ${m(solid ? 'solid' : 'tinted')}`} onClick={() => setSolid(!solid)}><span />{m(solid ? 'solid' : 'tinted')}</button>
        </div>
      </div>
      {(stale || notice) && <div className="monitor-stale-banner" role="status"><WifiOff size={16} /><strong>{notice || m('stale')}</strong><span>{!notice && m('staleDetail')}</span>{notice && <button onClick={() => setNotice('')}>{m('close')}</button>}</div>}
      <div ref={gridRef} className={`monitor-content ${compact ? 'is-fleet' : ''}`} style={gridStyle}>
        {!ordered.length ? <div className="monitor-no-results"><Search size={24} /><h2>{m('noResults')}</h2><Button variant="outline" onClick={() => setSearch('')}>{m('resetSearch')}</Button></div>
          : view === 'locations' ? locations.map(loc => {
            const items = ordered.filter(p => p.location === loc);
            return items.length ? <section key={loc} className="monitor-location"><h2><MapPin size={15} />{m(loc)}<span>{items.length}</span>{items.some(p => needsAttention(p, page)) && <small><AlertTriangle size={12} />{items.filter(p => needsAttention(p, page)).length} {m('issues').toLowerCase()}</small>}</h2><div className="monitor-grid">{renderTiles(items)}</div></section> : null;
          }) : <div className="monitor-grid">{renderTiles(ordered)}</div>}
      </div>
      <footer className="monitor-footer"><span><span className="monitor-footer-dot" />{page === 'queues' ? m('queueHint') : sort === 'attention' ? m('printerHint') : `${m('sort')}: ${m(sort)}`}</span><span>{ordered.length} / {source.length}<ChevronRight size={13} />{m('demoShort')}</span></footer>
    </main>
    {selected && <StateDetails printer={selected} onClose={() => setSelected(null)} />}
  </div>;
}
