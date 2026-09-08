/**
 * The modal shell. A modal closes through its X, its own buttons, or Esc —
 * never through a click outside. The `lightbox` variant is the one exception.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { screen, fireEvent, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '../utils';
import { Modal, MODAL_SIZE_CLASS, type ModalSize } from '../../components/Modal';
import { _resetForTests } from '../../components/modalStack';

describe('Modal', () => {
  afterEach(() => {
    cleanup();
    _resetForTests();
  });

  it('renders the title and the body inside a labelled dialog', () => {
    render(
      <Modal onClose={vi.fn()} title="Hello">
        <p>body</p>
      </Modal>,
    );
    const dialog = screen.getByRole('dialog', { name: 'Hello' });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(screen.getByText('body')).toBeInTheDocument();
  });

  it('the header X calls onClose', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<Modal onClose={onClose} title="T">x</Modal>);
    await user.click(screen.getByRole('button', { name: 'Close' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('Escape calls onClose', () => {
    const onClose = vi.fn();
    render(<Modal onClose={onClose} title="T">x</Modal>);
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('a click on the backdrop does NOT call onClose', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<Modal onClose={onClose} title="T">x</Modal>);
    const overlay = screen.getByRole('dialog').parentElement as HTMLElement;
    await user.click(overlay);
    expect(onClose).not.toHaveBeenCalled();
  });

  it('closeDisabled blocks both the X and Escape', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<Modal onClose={onClose} title="T" closeDisabled>x</Modal>);
    const x = screen.getByRole('button', { name: 'Close' });
    expect(x).toBeDisabled();
    await user.click(x);
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).not.toHaveBeenCalled();
  });

  it('hideClose renders no X', () => {
    render(<Modal onClose={vi.fn()} title="T" hideClose>x</Modal>);
    expect(screen.queryByRole('button', { name: 'Close' })).toBeNull();
  });

  it('without a title the X still renders — nothing is Esc-only', () => {
    render(<Modal onClose={vi.fn()}>x</Modal>);
    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument();
  });

  it('a custom header is labelled through labelledBy', () => {
    render(
      <Modal onClose={vi.fn()} header={<h2 id="custom-h">Custom</h2>} labelledBy="custom-h">
        x
      </Modal>,
    );
    expect(screen.getByRole('dialog', { name: 'Custom' })).toBeInTheDocument();
  });

  it('renders the footer slot', () => {
    render(
      <Modal onClose={vi.fn()} title="T" footer={<button>Save</button>}>
        x
      </Modal>,
    );
    expect(screen.getByRole('button', { name: 'Save' })).toBeInTheDocument();
  });

  it.each(Object.entries(MODAL_SIZE_CLASS))('size %s puts "%s" on the panel', (size, classes) => {
    render(
      <Modal onClose={vi.fn()} title="T" size={size as ModalSize}>
        x
      </Modal>,
    );
    const panel = screen.getByRole('dialog');
    for (const c of classes.split(' ')) expect(panel).toHaveClass(c);
    if (size === 'full') expect(panel).not.toHaveClass('max-h-[90vh]');
    else expect(panel).toHaveClass('max-h-[90vh]');
    cleanup();
    _resetForTests();
  });

  it('index.css declares --container-8xl, without which max-w-8xl does not exist in Tailwind 4', () => {
    const css = readFileSync(join(process.cwd(), 'src/index.css'), 'utf8');
    expect(css).toMatch(/--container-8xl:\s*88rem/);
  });

  it('lightbox: a click on the ground closes, a click on the content does not, and there is no X', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <Modal variant="lightbox" onClose={onClose} ariaLabel="Preview">
        <img alt="big" src="x.png" />
      </Modal>,
    );
    const ground = screen.getByRole('dialog', { name: 'Preview' });
    expect(screen.queryByRole('button', { name: 'Close' })).toBeNull();

    await user.click(screen.getByRole('img', { name: 'big' }));
    expect(onClose).not.toHaveBeenCalled();

    await user.click(ground);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('focus moves into the dialog on mount and returns to the opener on unmount', () => {
    const opener = document.createElement('button');
    document.body.appendChild(opener);
    opener.focus();
    const { unmount } = render(<Modal onClose={vi.fn()} title="T">x</Modal>);
    expect(document.activeElement).toBe(screen.getByRole('dialog'));
    unmount();
    expect(document.activeElement).toBe(opener);
    opener.remove();
  });

  it('two nested modals: Escape closes the inner first, then the outer', () => {
    const outer = vi.fn();
    const inner = vi.fn();
    const { rerender } = render(
      <Modal onClose={outer} title="Outer">
        <Modal onClose={inner} title="Inner">
          i
        </Modal>
      </Modal>,
    );
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(inner).toHaveBeenCalledTimes(1);
    expect(outer).not.toHaveBeenCalled();

    rerender(<Modal onClose={outer} title="Outer">o</Modal>);
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(outer).toHaveBeenCalledTimes(1);
  });

  it('a nested modal paints above its parent: z-index is 50 + stack position', () => {
    render(
      <Modal onClose={vi.fn()} title="Outer">
        <Modal onClose={vi.fn()} title="Inner">
          i
        </Modal>
      </Modal>,
    );
    const overlayOf = (name: string) => screen.getByRole('dialog', { name }).parentElement as HTMLElement;
    expect(overlayOf('Outer').style.zIndex).toBe('50');
    expect(overlayOf('Inner').style.zIndex).toBe('51');
  });

  it('panelStyle lands on the panel as inline style', () => {
    render(
      <Modal onClose={vi.fn()} title="T" panelStyle={{ width: 866, maxWidth: 'calc(100vw - 2rem)' }}>
        x
      </Modal>,
    );
    const panel = screen.getByRole('dialog');
    expect(panel.style.width).toBe('866px');
    expect(panel.style.maxWidth).toBe('calc(100vw - 2rem)');
  });

  it('a click inside the modal does not reach a React ancestor onClick through the portal', async () => {
    const user = userEvent.setup();
    const ancestor = vi.fn();
    render(
      <div onClick={ancestor}>
        <Modal onClose={vi.fn()} title="T">
          <button>inner</button>
        </Modal>
      </div>,
    );
    await user.click(screen.getByRole('button', { name: 'inner' }));
    expect(ancestor).not.toHaveBeenCalled();
  });
});
