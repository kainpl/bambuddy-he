import { formatDateTime } from './date';
import type { DateFormat, TimeFormat } from './date';

/** `h:mm` for a machine-hours figure; null → '—'. */
export function hoursMinutes(seconds: number | null | undefined): string {
  if (seconds == null) return '—';
  const minutes = Math.max(0, Math.round(seconds / 60));
  return `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, '0')}`;
}

/** «вт 14:30» — weekday + time in the user's time format; the full date goes in a title. */
export function etaShort(iso: string | null | undefined, timeFormat: TimeFormat = 'system'): string {
  if (!iso) return '';
  return formatDateTime(iso, timeFormat, 'system', { weekday: 'short', hour: '2-digit', minute: '2-digit' });
}

export function etaFull(iso: string | null | undefined, timeFormat: TimeFormat = 'system', dateFormat: DateFormat = 'system'): string {
  return iso ? formatDateTime(iso, timeFormat, dateFormat) : '';
}
