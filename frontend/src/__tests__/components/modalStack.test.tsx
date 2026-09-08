/**
 * The modal stack owns the ONE Escape listener in the app. Esc reaches the
 * topmost registered modal only — a ConfirmModal over PrintModal closes
 * alone, the form behind it survives.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, cleanup, fireEvent, act, screen } from '@testing-library/react';
import type { RefObject } from 'react';
import {
  register,
  unregister,
  isAnyModalOpen,
  useIsAnyModalOpen,
  useModalStackEntry,
  ModalDepthContext,
  _resetForTests,
  _stackDepthForTests,
  type ModalStackEntry,
} from '../../components/modalStack';

function entry(onClose = vi.fn(), closeDisabled = false): RefObject<ModalStackEntry> {
  return { current: { onClose, closeDisabled } };
}

describe('modalStack', () => {
  beforeEach(() => _resetForTests());
  afterEach(() => {
    cleanup();
    _resetForTests();
  });

  it('Escape reaches only the topmost entry, then the next one once the top is gone', () => {
    const outer = vi.fn();
    const inner = vi.fn();
    const a = register(entry(outer), 0);
    const b = register(entry(inner), 0);

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(inner).toHaveBeenCalledTimes(1);
    expect(outer).not.toHaveBeenCalled();

    unregister(b);
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(outer).toHaveBeenCalledTimes(1);
    unregister(a);
  });

  it('a closeDisabled top swallows Escape without touching the one below', () => {
    const below = vi.fn();
    const top = vi.fn();
    register(entry(below), 0);
    register(entry(top, true), 0);

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(top).not.toHaveBeenCalled();
    expect(below).not.toHaveBeenCalled();
  });

  it('an Escape dispatched on document reaches the stack too', () => {
    const onClose = vi.fn();
    register(entry(onClose), 0);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('other keys are ignored', () => {
    const onClose = vi.fn();
    register(entry(onClose), 0);
    fireEvent.keyDown(window, { key: 'Enter' });
    expect(onClose).not.toHaveBeenCalled();
  });

  it('the window listener is attached with the first entry and detached with the last', () => {
    const add = vi.spyOn(window, 'addEventListener');
    const remove = vi.spyOn(window, 'removeEventListener');
    const keydownCalls = (spy: typeof add) => spy.mock.calls.filter((c) => c[0] === 'keydown');

    const a = register(entry(), 0);
    const b = register(entry(), 0);
    expect(keydownCalls(add)).toHaveLength(1);

    unregister(a);
    expect(keydownCalls(remove)).toHaveLength(0);
    unregister(b);
    expect(keydownCalls(remove)).toHaveLength(1);

    add.mockRestore();
    remove.mockRestore();
  });

  it('a deeper (nested) entry is on top even when it registered first', () => {
    // React runs a child's effects before its parent's, so a child modal
    // mounted in the same commit registers first. Depth, not order, decides.
    const onParentClose = vi.fn();
    const onChildClose = vi.fn();

    register(entry(onChildClose), 1);
    register(entry(onParentClose), 0);

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onChildClose).toHaveBeenCalledTimes(1);
    expect(onParentClose).not.toHaveBeenCalled();
  });

  it('isAnyModalOpen and useIsAnyModalOpen follow the stack', () => {
    function Probe() {
      const open = useIsAnyModalOpen();
      return <span data-testid="probe">{open ? 'open' : 'closed'}</span>;
    }
    render(<Probe />);
    expect(isAnyModalOpen()).toBe(false);
    expect(screen.getByTestId('probe')).toHaveTextContent('closed');

    let id = 0;
    act(() => {
      id = register(entry(), 0);
    });
    expect(isAnyModalOpen()).toBe(true);
    expect(screen.getByTestId('probe')).toHaveTextContent('open');

    act(() => unregister(id));
    expect(screen.getByTestId('probe')).toHaveTextContent('closed');
  });

  function Host({ onClose, disabled = false }: { onClose: () => void; disabled?: boolean }) {
    useModalStackEntry({ onClose, closeDisabled: disabled });
    return <div />;
  }

  it('useModalStackEntry registers on mount, reads the latest props, unregisters on unmount', () => {
    const first = vi.fn();
    const second = vi.fn();
    const { rerender, unmount } = render(<Host onClose={first} disabled={false} />);
    expect(_stackDepthForTests()).toBe(1);

    rerender(<Host onClose={first} disabled />);
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(first).not.toHaveBeenCalled();

    rerender(<Host onClose={second} disabled={false} />);
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1);

    unmount();
    expect(_stackDepthForTests()).toBe(0);
  });

  it('useModalStackEntry takes its depth from ModalDepthContext', () => {
    const nested = vi.fn();
    const top = vi.fn();
    // The nested one mounts FIRST (and at depth 1); the top-level one mounts
    // second at depth 0 — Esc must still reach the nested one.
    render(
      <ModalDepthContext.Provider value={1}>
        <Host onClose={nested} />
      </ModalDepthContext.Provider>,
    );
    render(<Host onClose={top} />);

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(nested).toHaveBeenCalledTimes(1);
    expect(top).not.toHaveBeenCalled();
  });
});
