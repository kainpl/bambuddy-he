import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { STOCK_NOTE_TOKENS } from '../../api/client';
import type { StockMovement } from '../../api/client';

/** The seven tokens, as a set, for the one question this file asks of them. */
const NOTE_TOKENS: ReadonlySet<string> = new Set(STOCK_NOTE_TOKENS);

/**
 * Whether a note is one the SERVER wrote, and therefore one to translate.
 *
 * ⚠️ **The token set is closed and the fallback is verbatim, not blank.** The
 * backend writes tokens (Ruling 17) precisely so its half can be read in the
 * operator's language; the other half is a hand correction, whose whole value
 * is the sentence the person typed. Translating by prefix or dropping an
 * unknown note would lose exactly the notes that matter.
 */
// This file also exports `MovementSource`, a component, so these two pure
// helpers trip react-refresh/only-export-components; they stay beside it
// because ProductStock.tsx and the Stock tab both need all three together.
// eslint-disable-next-line react-refresh/only-export-components
export function isNoteToken(note: string): boolean {
  return NOTE_TOKENS.has(note);
}

/** `+5` / `−3`. Signed on purpose: a reversal is a movement too, and a column
 *  of unsigned numbers cannot be read as a ledger. The ledger never writes a
 *  zero, so there is no third case. */
// eslint-disable-next-line react-refresh/only-export-components
export function signed(delta: number): string {
  return delta > 0 ? `+${delta}` : `−${Math.abs(delta)}`;
}

/**
 * Where a movement came from: its order, or the print that made it.
 *
 * ⚠️ **The archive is text, not a link.** There is no per-archive route in this
 * app — `/archives` is a filtered list and takes `printer`, `file` and `search`
 * params, none of which addresses one row — so a link would have to invent a
 * destination. The id is what the operator searches with; the order, which does
 * have a page, is a real link.
 */
export function MovementSource({ movement }: { movement: StockMovement }) {
  const { t } = useTranslation();
  if (movement.order_id != null) {
    return (
      <Link to={`/projects/${movement.order_id}`} className="text-bambu-green hover:underline">
        {movement.order_name ?? `#${movement.order_id}`}
      </Link>
    );
  }
  if (movement.archive_id != null) {
    return <span>{t('stock.archiveRef', { n: movement.archive_id })}</span>;
  }
  return <span className="text-bambu-gray">—</span>;
}
