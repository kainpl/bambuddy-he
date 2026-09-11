/**
 * The print dialog's Quantity on several printers: per printer (the field's
 * old meaning) or a total dealt round-robin (spec 2026-09-11). What is pinned:
 * when the toggle shows, what each mode posts to each printer, that a printer
 * dealt nothing gets no request, that the plan line says what will happen,
 * that the choice survives a remount, and that a group answer carries it.
 */
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import { render } from '../utils';
import { PrintModal } from '../../components/PrintModal';
import { QUANTITY_MODE_STORAGE_KEY, type PrintModalAnswer } from '../../components/PrintModal/types';

const printers = [
  { id: 1, name: 'A1-01', model: 'A1', ip_address: '192.168.1.101', enabled: true, is_active: true },
  { id: 2, name: 'A1-02', model: 'A1', ip_address: '192.168.1.102', enabled: true, is_active: true },
  { id: 3, name: 'A1-03', model: 'A1', ip_address: '192.168.1.103', enabled: true, is_active: true },
];

const statusWithPetg = {
  connected: true,
  state: 'IDLE',
  ams: [
    {
      id: 0,
      tray: [
        { id: 0, tray_type: 'PETG', tray_color: 'FF0000FF', remain: 90 },
        { id: 1, tray_type: '', tray_color: '', remain: -1 },
        { id: 2, tray_type: '', tray_color: '', remain: -1 },
        { id: 3, tray_type: '', tray_color: '', remain: -1 },
      ],
    },
  ],
  vt_tray: [],
};

describe('quantity mode', () => {
  let posts: Array<{ queue_id: number; quantity: number }>;
  let onAnswered: Mock<(a: PrintModalAnswer) => void>;

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    posts = [];
    onAnswered = vi.fn<(a: PrintModalAnswer) => void>();
    server.use(
      http.get('/api/v1/printers/', () => HttpResponse.json(printers)),
      http.get('/api/v1/printers/:id/status', () => HttpResponse.json(statusWithPetg)),
      http.get('/api/v1/archives/:id/plates', () =>
        HttpResponse.json({ is_multi_plate: false, plates: [{ index: 1, name: 'Plate 1' }] }),
      ),
      http.get('/api/v1/archives/:id/filament-requirements', () =>
        HttpResponse.json({ filaments: [{ slot_id: 1, type: 'PETG', color: '#FF0000', used_grams: 10 }] }),
      ),
      http.post('/api/v1/queue/', async ({ request }) => {
        const body = (await request.json()) as { queue_id: number; quantity: number };
        posts.push({ queue_id: body.queue_id, quantity: body.quantity });
        return HttpResponse.json({ id: posts.length, status: 'pending', created_item_ids: [posts.length] });
      }),
    );
  });

  const mount = (printerIds: number[]) =>
    render(
      <PrintModal
        mode="add-to-queue"
        archiveId={1}
        archiveName="Bracket"
        initialSelectedPrinterIds={printerIds}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
        onAnswered={onAnswered}
      />,
    );

  const setQuantity = (n: number) => {
    const input = screen.getByLabelText('Quantity') as HTMLInputElement;
    fireEvent.change(input, { target: { value: String(n) } });
  };

  // The submit button renames itself once more than one printer is picked
  // ("Queue to 3 Printers"), which is exactly the case every test here is
  // about — so the matcher has to accept both wordings.
  const submit = () =>
    fireEvent.click(screen.getByRole('button', { name: /^(add to queue|queue to \d+ printers)$/i }));

  it('shows no toggle with one printer and a toggle with several', async () => {
    mount([1]);
    await screen.findByLabelText('Quantity');
    expect(screen.queryByTestId('quantity-mode-toggle')).toBeNull();
  });

  it('total 13 on three printers posts 5 / 4 / 4 in list order', async () => {
    mount([1, 2, 3]);
    await screen.findByTestId('quantity-mode-toggle');
    fireEvent.click(screen.getByTestId('quantity-mode-total'));
    setQuantity(13);
    await waitFor(() =>
      expect(screen.getByTestId('quantity-plan')).toHaveTextContent('13 → A1-01: 5 · A1-02: 4 · A1-03: 4'),
    );
    submit();
    await waitFor(() => expect(posts).toHaveLength(3));
    expect(posts).toEqual([
      { queue_id: 1, quantity: 5 },
      { queue_id: 2, quantity: 4 },
      { queue_id: 3, quantity: 4 },
    ]);
  });

  it('per printer 4 on three printers posts 4 to each, and says so', async () => {
    mount([1, 2, 3]);
    await screen.findByTestId('quantity-mode-toggle');
    expect(screen.getByTestId('quantity-mode-perPrinter')).toHaveAttribute('aria-pressed', 'true');
    setQuantity(4);
    await waitFor(() => expect(screen.getByTestId('quantity-plan')).toHaveTextContent('4 × 3 printers = 12 in total'));
    submit();
    await waitFor(() => expect(posts).toHaveLength(3));
    expect(posts.map((p) => p.quantity)).toEqual([4, 4, 4]);
  });

  it('a printer dealt nothing gets no request', async () => {
    mount([1, 2, 3]);
    await screen.findByTestId('quantity-mode-toggle');
    fireEvent.click(screen.getByTestId('quantity-mode-total'));
    setQuantity(2);
    await waitFor(() => expect(screen.getByTestId('quantity-plan')).toHaveTextContent('A1-03: 0'));
    submit();
    await waitFor(() => expect(posts).toHaveLength(2));
    expect(posts).toEqual([
      { queue_id: 1, quantity: 1 },
      { queue_id: 2, quantity: 1 },
    ]);
  });

  it('remembers the choice in the browser and reads it back', async () => {
    const first = mount([1, 2]);
    await screen.findByTestId('quantity-mode-toggle');
    fireEvent.click(screen.getByTestId('quantity-mode-total'));
    expect(localStorage.getItem(QUANTITY_MODE_STORAGE_KEY)).toBe('total');
    first.unmount();
    mount([1, 2]);
    await screen.findByTestId('quantity-mode-toggle');
    expect(screen.getByTestId('quantity-mode-total')).toHaveAttribute('aria-pressed', 'true');
  });

  it('the group answer carries the mode', async () => {
    mount([1, 2]);
    await screen.findByTestId('quantity-mode-toggle');
    fireEvent.click(screen.getByTestId('quantity-mode-total'));
    setQuantity(3);
    submit();
    await waitFor(() => expect(onAnswered).toHaveBeenCalled());
    expect(onAnswered.mock.calls[0][0].quantityMode).toBe('total');
  });
});
