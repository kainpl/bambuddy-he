/**
 * Every modal renders through `components/Modal.tsx`. A hand-rolled full-screen
 * overlay is how modals came to close on a click outside, each file copying the
 * last; this scan is what stops the next copy.
 *
 * Two rules, checked on every JSX opening tag in `src/**\/*.tsx`:
 * 1. `fixed inset-0` with a painted ground (any `bg-*` but `bg-transparent`,
 *    or `backdrop-blur`) is a modal → must be <Modal>.
 * 2. an `inset-0` overlay with a pointer handler is a click-outside → only a
 *    menu, popover, drawer, loading or viewer overlay may have one, and it says
 *    so on the line above: `// not-a-modal: menu` (or `{/* not-a-modal: menu *\/}`).
 *
 * `NOT_YET_MIGRATED` is the migration's allowlist. It shrinks to [] and is then
 * deleted; a file that no longer trips a rule but is still listed FAILS, so a
 * finished file cannot linger here.
 */
import { describe, it, expect } from 'vitest';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

const SRC = join(process.cwd(), 'src');
const SHELL = 'components/Modal.tsx';
const MARKER = /(\/\/|\{\/\*)\s*not-a-modal:\s*(menu|popover|drawer|loading|viewer)\b/;

/** Files still on hand-rolled overlays. Remove a file the moment it is migrated. */
const NOT_YET_MIGRATED: string[] = [
  'components/KeyboardShortcutsModal.tsx',
  'components/Layout.tsx',
  'pages/ArchivesPage.tsx',
  'pages/PrintersPage.tsx',
  'pages/SettingsPage.tsx',
  'pages/StatsPage.tsx',
];

function walk(dir: string, out: string[] = []): string[] {
  for (const d of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, d.name);
    if (d.isDirectory()) {
      if (d.name !== '__tests__') walk(p, out);
    } else if (d.name.endsWith('.tsx')) {
      out.push(p);
    }
  }
  return out;
}

interface Tag {
  line: number;
  text: string;
  lineBefore: string;
}

/** Every JSX opening tag, from `<Tag` to its own `>`, honouring braces and strings. */
function openingTags(src: string): Tag[] {
  const lines = src.split('\n');
  const tags: Tag[] = [];
  const re = /<([A-Za-z][\w.]*)\b/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(src))) {
    let i = m.index + m[0].length;
    let depth = 0;
    let str: string | null = null;
    while (i < src.length) {
      const c = src[i];
      if (str) {
        if (c === str && src[i - 1] !== '\\') str = null;
      } else if (c === '"' || c === "'" || c === '`') {
        str = c;
      } else if (c === '{') {
        depth += 1;
      } else if (c === '}') {
        depth -= 1;
      } else if (c === '>' && depth === 0) {
        break;
      }
      i += 1;
    }
    const text = src.slice(m.index, i + 1);
    if (text.length > 4000) continue;
    const line = src.slice(0, m.index).split('\n').length;
    tags.push({ line, text, lineBefore: lines[line - 2] ?? '' });
  }
  return tags;
}

function offenders(file: string, src: string): string[] {
  const out: string[] = [];
  for (const t of openingTags(src)) {
    // The shell's own tag: a header/children prop may carry a popover's click-catcher, which is that popover's to mark, not the shell's.
    if (/^<Modal\b/.test(t.text)) continue;
    if (!/className=/.test(t.text) || !/\binset-0\b/.test(t.text)) continue;
    if (MARKER.test(t.lineBefore)) continue;
    const fullScreen = /\bfixed\b/.test(t.text);
    // Any painted ground makes a full-screen overlay a modal — `bg-black/50`,
    // but also an opaque themed ground like the fullscreen camera's
    // `bg-bambu-dark-secondary`. A menu's click-catcher paints nothing.
    const ground = /\bbg-(?!transparent\b)|\bbackdrop-blur/.test(t.text);
    // A sibling backdrop is always the dimming kind.
    const dimming = /\bbg-black\b|\bbackdrop-blur/.test(t.text);
    const handler = /\bon(Click|MouseDown|PointerDown|TouchStart)=/.test(t.text);
    if (fullScreen && ground) {
      out.push(`${file}:${t.line} — hand-rolled modal overlay; render <Modal> from components/Modal.tsx`);
    } else if (handler && (fullScreen || (dimming && /\babsolute\b/.test(t.text)))) {
      out.push(
        `${file}:${t.line} — click-outside on an overlay; put "// not-a-modal: menu|popover|drawer|loading|viewer" on the line above, or use <Modal variant="lightbox">`,
      );
    }
  }
  return out;
}

describe('modal shell ownership', () => {
  const files = walk(SRC)
    .map((p) => relative(SRC, p).split(sep).join('/'))
    .filter((f) => f !== SHELL);
  const byFile = new Map(files.map((f) => [f, offenders(f, readFileSync(join(SRC, f), 'utf8'))]));

  it('every full-screen overlay outside the shell is a <Modal>, or is marked as not a modal', () => {
    const bad = files.filter((f) => !NOT_YET_MIGRATED.includes(f)).flatMap((f) => byFile.get(f) ?? []);
    expect(bad).toEqual([]);
  });

  it('NOT_YET_MIGRATED lists only files that still need migrating', () => {
    const stale = NOT_YET_MIGRATED.filter((f) => !existsSync(join(SRC, f)) || (byFile.get(f) ?? []).length === 0);
    expect(stale).toEqual([]);
  });
});
