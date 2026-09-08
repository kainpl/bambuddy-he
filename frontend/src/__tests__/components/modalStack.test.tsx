/**
 * The modal stack owns the ONE Escape listener in the app. Esc reaches the
 * topmost registered modal only — a ConfirmModal over PrintModal closes
 * alone, the form behind it survives.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, cleanup, fireEvent, act, screen } from '@testing-library/react';
import type { ReactNode, RefObject } from 'react';
import {
  register,
  unregister,
  positionOf,
  isAnyModalOpen,
  useIsAnyModalOpen,
  useModalStackEntry,
  ModalAncestryContext,
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
    register('a', [], entry(outer));
    register('b', [], entry(inner));

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(inner).toHaveBeenCalledTimes(1);
    expect(outer).not.toHaveBeenCalled();

    unregister('b');
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(outer).toHaveBeenCalledTimes(1);
    unregister('a');
  });

  it('a closeDisabled top swallows Escape without touching the one below', () => {
    const below = vi.fn();
    const top = vi.fn();
    register('a', [], entry(below));
    register('b', [], entry(top, true));

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(top).not.toHaveBeenCalled();
    expect(below).not.toHaveBeenCalled();
  });

  it('an Escape dispatched on document reaches the stack too', () => {
    const onClose = vi.fn();
    register('a', [], entry(onClose));
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('other keys are ignored', () => {
    const onClose = vi.fn();
    register('a', [], entry(onClose));
    fireEvent.keyDown(window, { key: 'Enter' });
    expect(onClose).not.toHaveBeenCalled();
  });

  it('the window listener is attached with the first entry and detached with the last', () => {
    const add = vi.spyOn(window, 'addEventListener');
    const remove = vi.spyOn(window, 'removeEventListener');
    const keydownCalls = (spy: typeof add) => spy.mock.calls.filter((c) => c[0] === 'keydown');

    register('a', [], entry());
    register('b', [], entry());
    expect(keydownCalls(add)).toHaveLength(1);

    unregister('a');
    expect(keydownCalls(remove)).toHaveLength(0);
    unregister('b');
    expect(keydownCalls(remove)).toHaveLength(1);

    add.mockRestore();
    remove.mockRestore();
  });

  it('a parent that registers after its child (same-commit mount) goes just below it', () => {
    // React runs a child's effects before its parent's, so a child modal
    // mounted in the same commit registers first. Ancestry, not order, decides.
    const onParentClose = vi.fn();
    const onChildClose = vi.fn();

    register('child', ['parent'], entry(onChildClose));
    register('parent', [], entry(onParentClose));

    expect(positionOf('parent')).toBe(0);
    expect(positionOf('child')).toBe(1);
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onChildClose).toHaveBeenCalledTimes(1);
    expect(onParentClose).not.toHaveBeenCalled();
  });

  it('a later top-level entry sits above an earlier nested chain', () => {
    // An app-level alert raised while "modal → nested confirm" is open must
    // be on top of both — this is what AlertModal's old z-[120] was for.
    const onA = vi.fn();
    const onC = vi.fn();
    const onB = vi.fn();
    register('a', [], entry(onA));
    register('c', ['a'], entry(onC));
    register('b', [], entry(onB));

    expect([positionOf('a'), positionOf('c'), positionOf('b')]).toEqual([0, 1, 2]);
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onB).toHaveBeenCalledTimes(1);
    expect(onC).not.toHaveBeenCalled();
    expect(onA).not.toHaveBeenCalled();
  });

  it('positionOf is -1 for a key that is not registered', () => {
    expect(positionOf('nope')).toBe(-1);
  });

  it('isAnyModalOpen and useIsAnyModalOpen follow the stack', () => {
    function Probe() {
      const open = useIsAnyModalOpen();
      return <span data-testid="probe">{open ? 'open' : 'closed'}</span>;
    }
    render(<Probe />);
    expect(isAnyModalOpen()).toBe(false);
    expect(screen.getByTestId('probe')).toHaveTextContent('closed');

    act(() => register('a', [], entry()));
    expect(isAnyModalOpen()).toBe(true);
    expect(screen.getByTestId('probe')).toHaveTextContent('open');

    act(() => unregister('a'));
    expect(screen.getByTestId('probe')).toHaveTextContent('closed');
  });

  /** A stand-in for the shell: registers, shows its position, and passes its ancestry down. */
  function Host({
    label,
    onClose,
    disabled = false,
    children,
  }: {
    label: string;
    onClose: () => void;
    disabled?: boolean;
    children?: ReactNode;
  }) {
    const { position, childAncestry } = useModalStackEntry({ onClose, closeDisabled: disabled });
    return (
      <ModalAncestryContext.Provider value={childAncestry}>
        <span data-testid={label}>{position}</span>
        {children}
      </ModalAncestryContext.Provider>
    );
  }

  it('useModalStackEntry registers on mount, reads the latest props, unregisters on unmount', () => {
    const first = vi.fn();
    const second = vi.fn();
    const { rerender, unmount } = render(<Host label="h" onClose={first} disabled={false} />);
    expect(_stackDepthForTests()).toBe(1);
    expect(screen.getByTestId('h')).toHaveTextContent('0');

    rerender(<Host label="h" onClose={first} disabled />);
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(first).not.toHaveBeenCalled();

    rerender(<Host label="h" onClose={second} disabled={false} />);
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1);

    unmount();
    expect(_stackDepthForTests()).toBe(0);
  });

  it('a Host nested in a Host, mounted in one render, is above its parent and shows position 1', () => {
    const parent = vi.fn();
    const child = vi.fn();
    render(
      <Host label="p" onClose={parent}>
        <Host label="c" onClose={child} />
      </Host>,
    );
    expect(screen.getByTestId('p')).toHaveTextContent('0');
    expect(screen.getByTestId('c')).toHaveTextContent('1');

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(child).toHaveBeenCalledTimes(1);
    expect(parent).not.toHaveBeenCalled();
  });

  it('a Host mounted later, outside the chain, is on top of it and its position updates live', () => {
    const chainTop = vi.fn();
    const later = vi.fn();
    render(
      <Host label="p" onClose={vi.fn()}>
        <Host label="c" onClose={chainTop} />
      </Host>,
    );
    render(<Host label="later" onClose={later} />);
    expect(screen.getByTestId('later')).toHaveTextContent('2');

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(later).toHaveBeenCalledTimes(1);
    expect(chainTop).not.toHaveBeenCalled();
  });
});
