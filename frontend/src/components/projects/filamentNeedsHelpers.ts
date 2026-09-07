/**
 * Pure (non-component) export shared by `<FilamentNeeds>` and any future
 * farm-wide counterpart that needs the identical testid shape.
 *
 * Lives in its own file so `FilamentNeeds.tsx` stays component-only and
 * satisfies the `react-refresh/only-export-components` ESLint rule — the same
 * split already used by `filamentSwatchHelpers.ts` / `plateDialogLayout.ts` /
 * `staggerGroupIds.ts` (spec 2026-09-07).
 */
export function needTestId(material: string, colour: string | null): string {
  return colour ? `filament-need-${material}-${colour}` : `filament-need-${material}`;
}
