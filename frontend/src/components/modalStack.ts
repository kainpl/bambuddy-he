/**
 * The modal stack — the ONE place Escape is handled for modals.
 *
 * Every <Modal> registers here on mount and unregisters on unmount. One
 * `keydown` listener on `window` (attached with the first entry, detached
 * with the last) closes the TOPMOST entry only, so nested modals close one
 * per keypress, innermost first. Before this, 66 files each had their own
 * `window` listener and a ConfirmModal over PrintModal closed both at once.
 *
 * ⚠️ `window`, not `document`: an event dispatched on `window` never reaches a
 * `document` listener, while everything that reaches `document` bubbles on to
 * `window`. Tests dispatch on both.
 *
 * ⚠️ Order is NESTING DEPTH, not registration order and not DOM order. React
 * runs a child's effects before its parent's, so a parent and child modal
 * mounted in ONE commit register child-first — and within one commit React
 * also places a portal's children in post-order, so they land in `body`
 * child-first too. Depth (how many <Modal>s enclose this one, carried by
 * `ModalDepthContext`) is the one order that cannot invert: a deeper entry is
 * always above a shallower one; among equals, later registration is higher.
 *
 * Entries are read through a ref at keypress time, so a modal whose
 * `onClose` or `closeDisabled` changed after mount never has a stale
 * closure called.
 */
import {
  createContext,
  useContext,
  useEffect,
  useLayoutEffect,
  useRef,
  useSyncExternalStore,
  type RefObject,
} from 'react';

export interface ModalStackEntry {
  onClose: () => void;
  closeDisabled: boolean;
}

interface Registered {
  id: number;
  depth: number;
  entry: RefObject<ModalStackEntry>;
}

/** How many <Modal>s enclose the current subtree. The shell provides depth + 1 to its children. */
export const ModalDepthContext = createContext(0);

export function useModalDepth(): number {
  return useContext(ModalDepthContext);
}

let nextId = 1;
let stack: Registered[] = [];
const subscribers = new Set<() => void>();

function notify(): void {
  for (const fn of subscribers) fn();
}

function onKeyDown(e: KeyboardEvent): void {
  if (e.key !== 'Escape') return;
  const top = stack[stack.length - 1];
  if (!top) return;
  const entry = top.entry.current;
  if (entry.closeDisabled) return;
  e.preventDefault();
  e.stopPropagation();
  entry.onClose();
}

export function register(entry: RefObject<ModalStackEntry>, depth: number): number {
  const id = nextId++;
  // Insert below the first entry that is deeper than this one, so a nested
  // modal stays on top whatever order the two registered in.
  let index = stack.length;
  for (let i = 0; i < stack.length; i += 1) {
    if (stack[i].depth > depth) {
      index = i;
      break;
    }
  }
  const wasEmpty = stack.length === 0;
  stack = [...stack.slice(0, index), { id, depth, entry }, ...stack.slice(index)];
  if (wasEmpty) window.addEventListener('keydown', onKeyDown);
  notify();
  return id;
}

export function unregister(id: number): void {
  stack = stack.filter((r) => r.id !== id);
  if (stack.length === 0) window.removeEventListener('keydown', onKeyDown);
  notify();
}

export function isAnyModalOpen(): boolean {
  return stack.length > 0;
}

function subscribe(fn: () => void): () => void {
  subscribers.add(fn);
  return () => {
    subscribers.delete(fn);
  };
}

/** Re-renders when the first modal opens or the last one closes. */
export function useIsAnyModalOpen(): boolean {
  return useSyncExternalStore(subscribe, isAnyModalOpen, () => false);
}

/**
 * Attach the calling modal to the stack for its lifetime, at the nesting
 * depth `ModalDepthContext` reports for its position in the tree.
 */
export function useModalStackEntry(entry: ModalStackEntry): void {
  const depth = useModalDepth();
  const latest = useRef<ModalStackEntry>(entry);
  useLayoutEffect(() => {
    latest.current = entry;
  });
  useEffect(() => {
    const id = register(latest, depth);
    return () => unregister(id);
  }, [depth]);
}

export function _resetForTests(): void {
  stack = [];
  window.removeEventListener('keydown', onKeyDown);
  nextId = 1;
  notify();
}

export function _stackDepthForTests(): number {
  return stack.length;
}
