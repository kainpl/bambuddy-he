import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Clock, Calendar, ChevronRight, Loader2, CircleCheck, RotateCcw, PackageX } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api } from '../api/client';
import type { DefectsWriteBody } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import { formatRelativeTime } from '../utils/date';
import { invalidateQueueViews, invalidateOrderViews } from '../utils/queryInvalidation';
import { DefectsFields } from './DefectsFields';

interface PrinterQueueWidgetProps {
  printerId: number;
  printerModel?: string | null;
  printerState?: string | null;
  awaitingPlateClear?: boolean;
  // Whether Repeat has a finished row to re-arm — the backend's
  // `repeat_available`. Absent (older backend) means "don't hide it".
  repeatAvailable?: boolean;
  requirePlateClear?: boolean;
}

export function PrinterQueueWidget({ printerId, printerState, awaitingPlateClear, repeatAvailable, requirePlateClear = true }: PrinterQueueWidgetProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const { hasPermission } = useAuth();
  const { data: queue } = useQuery({
    queryKey: ['queue', printerId, 'pending'],
    queryFn: () => api.getQueue(printerId, 'pending'),
    refetchInterval: 30000,
  });

  // The print the gate is about, with its part rows — fetched only while the
  // block is on screen, and the counters live here so both answers can carry them.
  const [defectsOpen, setDefectsOpen] = useState(false);
  const [defectValues, setDefectValues] = useState<Record<number, number>>({});
  const [defectFlat, setDefectFlat] = useState(0);
  const [defectsTouched, setDefectsTouched] = useState(false);
  const gateArmed = requirePlateClear && (printerState === 'FINISH' || printerState === 'FAILED') && !!awaitingPlateClear;
  const { data: waiting } = useQuery({
    queryKey: ['waiting-print', printerId],
    queryFn: () => api.getWaitingPrint(printerId),
    enabled: gateArmed,
    retry: false,
  });
  useEffect(() => {
    if (waiting && !defectsTouched) {
      setDefectValues(Object.fromEntries(waiting.parts.map((p) => [p.id, p.defective])));
      setDefectFlat(waiting.defective_count);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [waiting]);
  const defectsBody = (): { defects: DefectsWriteBody } | undefined => {
    if (!defectsTouched || !waiting) return undefined;
    return waiting.parts.length > 0
      ? { defects: { parts: waiting.parts.map((p) => ({ id: p.id, defective: defectValues[p.id] ?? 0 })) } }
      : { defects: { defective_count: defectFlat } };
  };
  const afterAnswer = () => {
    invalidateQueueViews(queryClient);
    queryClient.invalidateQueries({ queryKey: ['printerStatus', printerId] });
    queryClient.invalidateQueries({ queryKey: ['waiting-print', printerId] });
    // The shelf may have moved with the defects.
    invalidateOrderViews(queryClient);
    setDefectsTouched(false);
    setDefectsOpen(false);
  };

  // The other answer to a full plate — see services/plate_hold on the backend.
  const repeatPrintMutation = useMutation({
    mutationFn: () => api.repeatPrint(printerId, defectsBody()),
    onSuccess: () => {
      afterAnswer();
      showToast(t('queue.repeatPrintSuccess'), 'success');
    },
    onError: (error: Error) => showToast(error.message, 'error'),
  });

  const clearPlateMutation = useMutation({
    mutationFn: () => api.clearPlate(printerId, defectsBody()),
    onSuccess: () => {
      afterAnswer();
      showToast(t('queue.clearPlateSuccess'), 'success');
    },
    onError: (err: Error) => {
      showToast(err.message, 'error');
    },
  });

  // Reset mutation state when printer starts a new print cycle so the button
  // is clickable again when the next print finishes (fixes upstream #912)
  useEffect(() => {
    if (printerState !== 'FINISH' && printerState !== 'FAILED') {
      clearPlateMutation.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [printerState]);

  // Split into auto-dispatchable vs staged (manual_start) items
  const autoDispatchQueue = queue?.filter(item => !item.manual_start) ?? [];
  const totalPending = queue?.length || 0;

  if (totalPending === 0) {
    return null;
  }

  const nextAutoItem = autoDispatchQueue[0];
  const nextItem = queue?.[0];
  // Only prompt "Clear Plate & Start Next" when there are auto-dispatchable items
  const needsClearPlate = requirePlateClear && (printerState === 'FINISH' || printerState === 'FAILED') && !!awaitingPlateClear && autoDispatchQueue.length > 0;

  if (needsClearPlate) {
    const displayItem = nextAutoItem || nextItem;
    // The touched total wins over the server's count the moment the operator
    // types — same semantics as the toggle label the brief specifies.
    const shownDefects = waiting
      ? defectsTouched
        ? Object.values(defectValues).reduce((a, n) => a + n, 0) || defectFlat
        : waiting.defective_count
      : 0;
    return (
      <div className="mb-3 p-3 bg-bambu-dark rounded-lg border border-yellow-400/30">
        <div className="flex items-center gap-3 mb-2">
          <Calendar className="w-5 h-5 text-yellow-600 dark:text-yellow-400 flex-shrink-0" />
          <div className="min-w-0 flex-1">
            <p className="text-xs text-bambu-gray">{t('queue.nextInQueue')}</p>
            <p className="text-sm text-white truncate">
              {displayItem?.archive_name || displayItem?.library_file_name || `File #${displayItem?.archive_id || displayItem?.library_file_id}`}
            </p>
          </div>
          {totalPending > 1 && (
            <span className="text-xs px-1.5 py-0.5 bg-yellow-100 dark:bg-yellow-400/20 text-yellow-700 dark:text-yellow-400 rounded flex-shrink-0">
              +{totalPending - 1}
            </span>
          )}
        </div>
        {waiting && waiting.status === 'completed' && waiting.quantity > 0 && (
          <div className="mb-2">
            <button
              type="button"
              onClick={() => setDefectsOpen((open) => !open)}
              data-testid="plate-defects-toggle"
              className="text-xs text-bambu-gray hover:text-white inline-flex items-center gap-1"
            >
              <PackageX className="w-3.5 h-3.5" />
              {shownDefects > 0
                ? t('queue.defects.toggleWithCount', { count: shownDefects })
                : t('queue.defects.toggle')}
            </button>
            {defectsOpen && (
              <div className="mt-2" data-testid="plate-defects-fields">
                <DefectsFields
                  parts={waiting.parts}
                  values={defectValues}
                  onChange={(id, next) => {
                    setDefectValues((prev) => ({ ...prev, [id]: next }));
                    setDefectsTouched(true);
                  }}
                  quantity={waiting.quantity}
                  flat={defectFlat}
                  onFlatChange={(next) => {
                    setDefectFlat(next);
                    setDefectsTouched(true);
                  }}
                />
              </div>
            )}
          </div>
        )}
        {clearPlateMutation.isSuccess ? (
          <div className="w-full py-2 px-3 rounded-lg bg-bambu-green/10 border border-bambu-green/20 text-bambu-green text-sm flex items-center justify-center gap-2">
            <CircleCheck className="w-4 h-4" />
            {t('queue.plateReady')}
          </div>
        ) : (
          <div className="flex gap-2">
            {repeatAvailable !== false && (
              <button
                onClick={() => repeatPrintMutation.mutate()}
                disabled={repeatPrintMutation.isPending || !hasPermission('printers:clear_plate')}
                className="flex-1 py-2 px-3 rounded-lg bg-bambu-green/20 border border-bambu-green/40 text-bambu-green hover:bg-bambu-green/30 transition-colors text-sm font-medium flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {repeatPrintMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <RotateCcw className="w-4 h-4" />
                )}
                {t('queue.repeatPrint')}
              </button>
            )}
            <button
              onClick={() => clearPlateMutation.mutate()}
              disabled={clearPlateMutation.isPending || !hasPermission('printers:clear_plate')}
              className="flex-1 py-2 px-3 rounded-lg bg-bambu-green/20 border border-bambu-green/40 text-bambu-green hover:bg-bambu-green/30 transition-colors text-sm font-medium flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {clearPlateMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <CircleCheck className="w-4 h-4" />
              )}
              {t('queue.clearPlateShort')}
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <Link
      to="/queue"
      className="block mb-3 p-3 bg-bambu-dark rounded-lg hover:bg-bambu-dark-tertiary transition-colors"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <Calendar className="w-5 h-5 text-yellow-600 dark:text-yellow-400 flex-shrink-0" />
          <div className="min-w-0 flex-1">
            <p className="text-xs text-bambu-gray">{t('queue.nextInQueue')}</p>
            <p className="text-sm text-white truncate">
              {nextItem?.archive_name || nextItem?.library_file_name || `File #${nextItem?.archive_id || nextItem?.library_file_id}`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-xs text-bambu-gray flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {nextItem?.scheduled_time ? formatRelativeTime(nextItem.scheduled_time, 'system', t) : t('time.waiting')}
          </span>
          {totalPending > 1 && (
            <span className="text-xs px-1.5 py-0.5 bg-yellow-100 dark:bg-yellow-400/20 text-yellow-700 dark:text-yellow-400 rounded">
              +{totalPending - 1}
            </span>
          )}
          <ChevronRight className="w-4 h-4 text-bambu-gray" />
        </div>
      </div>
    </Link>
  );
}
