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
 * ⚠️ Order is MOUNT ORDER with one correction. React runs a child's effects
 * before its parent's, so a parent and child modal mounted in ONE commit
 * register child-first — and within one commit React also places a portal's
 * children in post-order, so they land in `body` child-first: neither
 * registration order nor DOM order can be trusted there. Every entry carries
 * the keys of the shells enclosing it (`ModalAncestryContext`); an entry that
 * turns out to be an ANCESTOR of one already registered is inserted just
 * below that descendant. Everything else is appended, so an app-level alert
 * raised over "modal → nested confirm" lands on top of both — which is what
 * AlertModal's old `z-[120]` existed for. (Ordering by nesting depth instead
 * would bury that alert under the confirm.) z-index is 50 + stack position,
 * so paint order follows the stack, not the DOM.
 *
 * Entries are read through a ref at keypress time, so a modal whose
 * `onClose` or `closeDisabled` changed after mount never has a stale
 * closure called.
 */
import {
  createContext,
  useContext,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useSyncExternalStore,
  type RefObject,
} from 'react';

export interface ModalStackEntry {
  onClose: () => void;
  closeDisabled: boolean;
}

interface Registered {
  key: string;
  ancestors: readonly string[];
  entry: RefObject<ModalStackEntry>;
}

/** Keys of the <Modal>s enclosing the current subtree, outermost first. The shell provides its `childAncestry`. */
export const ModalAncestryContext = createContext<readonly string[]>([]);

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

export function register(key: string, ancestors: readonly string[], entry: RefObject<ModalStackEntry>): void {
  // Mount order — unless a descendant is already here (a same-commit mount
  // registers child-first): then this one goes just below it.
  const descendant = stack.findIndex((r) => r.ancestors.includes(key));
  const index = descendant === -1 ? stack.length : descendant;
  const wasEmpty = stack.length === 0;
  stack = [...stack.slice(0, index), { key, ancestors, entry }, ...stack.slice(index)];
  if (wasEmpty) window.addEventListener('keydown', onKeyDown);
  notify();
}

export function unregister(key: string): void {
  stack = stack.filter((r) => r.key !== key);
  if (stack.length === 0) window.removeEventListener('keydown', onKeyDown);
  notify();
}

/** 0 = bottom; −1 when the key is not registered. */
export function positionOf(key: string): number {
  return stack.findIndex((r) => r.key === key);
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

export interface ModalStackPlacement {
  /** This modal's index in the stack, bottom = 0. Before the registering effect has run it is the nesting depth — a fair guess for one frame. */
  position: number;
  /** What this modal's children must receive as `ModalAncestryContext`. Stable across renders. */
  childAncestry: readonly string[];
}

/**
 * Attach the calling modal to the stack for its lifetime and report where it
 * sits. The key is the component's `useId`; the ancestry is whatever
 * `ModalAncestryContext` says encloses it.
 */
export function useModalStackEntry(entry: ModalStackEntry): ModalStackPlacement {
  const key = useId();
  const ancestors = useContext(ModalAncestryContext);
  const latest = useRef<ModalStackEntry>(entry);
  useLayoutEffect(() => {
    latest.current = entry;
  });
  useEffect(() => {
    register(key, ancestors, latest);
    return () => unregister(key);
  }, [key, ancestors]);
  const registered = useSyncExternalStore(subscribe, () => positionOf(key), () => -1);
  const position = registered === -1 ? ancestors.length : registered;
  const childAncestry = useMemo(() => [...ancestors, key], [ancestors, key]);
  return { position, childAncestry };
}

export function _resetForTests(): void {
  stack = [];
  window.removeEventListener('keydown', onKeyDown);
  notify();
}

export function _stackDepthForTests(): number {
  return stack.length;
}
