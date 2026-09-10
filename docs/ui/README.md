# BamDude UI — how to build with it

Feature design: [status monitor specification](../specs/status-monitor.md) ·
[implementation plan](../plans/status-monitor.md) · [operator guide](../status-monitor.md).

The frontend is React 19 + Tailwind 4 (`frontend/src`). This page is the
styling idiom a new screen or component is expected to follow — the same
rules the maintainer's design tooling is fed, written for a human or an agent
editing the app itself. Everything here is verifiable in the code it names.

## 1. Theme: classes on `<html>`, never on your component

`frontend/src/contexts/ThemeContext.tsx` puts the palette classes on `<html>`
(`dark` / `light`, a background family, an accent). Every `bg-bambu-*` /
`text-bambu-*` utility resolves through CSS variables declared for that
combination in `frontend/src/index.css` — so a component never picks colours
itself, it names a *role* (page ground, card surface, muted text, accent) and
the theme fills it in. `text-white` is overridden in `index.css`
(`.text-white`) to the theme's primary text colour: it is not literal white,
and reads correctly on a light theme too.

Fonts are shipped (`frontend/public/fonts`, Inter, self-hosted) — never add a
Google Fonts link.

## 2. The styling idiom: Tailwind utilities + the app's own semantic tokens

Style with Tailwind utility classes, the way the app does, and reach for the
semantic tokens before a raw colour:

| Purpose | Classes |
|---|---|
| Page ground | `bg-bambu-dark` |
| Card / panel surface | `bg-bambu-dark-secondary rounded-xl border border-bambu-dark-tertiary card-shadow` (that is `Card`) |
| Borders, tracks, hover fills | `border-bambu-dark-tertiary`, `bg-bambu-dark-tertiary` |
| Text: primary · secondary · muted | `text-white` (theme-aware, see above) · `text-bambu-gray-light` · `text-bambu-gray` |
| Accent (follows the theme accent) | `bg-bambu-green`, `text-bambu-green`, `ring-bambu-green` (selected) |
| Fixed status colours (never follow the accent) | `bg-status-ok` / `bg-status-warning` / `bg-status-error`; tints `bg-status-warning/20 text-status-warning`, `bg-status-ok/20 text-status-ok` |
| Pills with a hue of their own | `bg-blue-500/20 text-blue-400` (in use), `bg-yellow-500/20 text-yellow-400` (needs attention), `bg-red-900/50 text-red-300` (recording) |
| Radii | `rounded-xl` cards · `rounded-lg` controls and thumbnails · `rounded-full` pills, pips, progress tracks |
| Type ramp | `text-base font-semibold` names · `text-sm` body · `text-xs` meta and footers · `text-[11px]` metric lines · `text-[10px] font-medium` chips |
| Spacing | `p-4` card content · `gap-2`/`gap-3` rows · `mb-2`/`mt-2` blocks · `mt-1` a metric line · `gap-1` a chip strip |

A raw Tailwind colour (`bg-yellow-400`) is for a pill that carries its own
meaning, not for a surface — surfaces and text go through the tokens or they
break on the first theme that is not dark-neutral.

`card-shadow` is a Tailwind `@utility` in `index.css` that fills `--tw-shadow`,
so it composes with `ring-*` and `shadow-*` instead of overriding them. Keep it
that way: it used to be an unlayered rule and silently swallowed every focus
ring on every card.

Icons are **lucide-react** (`Clock`, `Layers`, `Pause`, `Maximize2`,
`MoreVertical`, `RotateCcw`, …): 16 px (`w-4 h-4`) inside ghost buttons, 12 px
(`w-3 h-3`) in metric lines and in 20 px round buttons, 20 px (`w-5 h-5`) in
secondary card controls. The only non-lucide glyph is
`components/icons/PlateClearedIcon.tsx`.

Controls come from the library, not from raw elements:

| Part | File |
|---|---|
| `Button` — variants `primary` `secondary` `outline` `danger` `ghost`; icon-only = `ghost` + `sm` with a 16 px icon | `components/Button.tsx` |
| `Card`, `CardHeader`, `CardContent` | `components/Card.tsx` |
| `Toggle` | `components/Toggle.tsx` |
| `SelectionBox` (inside a ghost `Button`) | `components/SelectionBox.tsx` |
| `PauseChip`, `PrinterTagChip`, `FilamentSlotCircle` | `components/*.tsx` of the same name |
| `Modal` — the only modal shell; see the invariant in `CLAUDE.md` | `components/Modal.tsx` |
| `PrinterQueueWidget` — the queue strip of an expanded printer card | `components/PrinterQueueWidget.tsx` |

A new modal renders through `Modal` — a hand-rolled `fixed inset-0` overlay
fails the `modalShellOwnership` test, not a style review.

## 3. Where the truth lives

- `frontend/src/index.css` — the tokens (`--bg-*`, `--text-*`, `--accent*`),
  the theme/background/accent class blocks, `card-shadow`, the container
  sizes (`--container-8xl` exists only for `Modal size="8xl"`).
- `frontend/src/components/` — the parts above; a screen composes them.
- `frontend/src/pages/PrintersPage.tsx::PrinterCard` — the printer card at
  every size (`cardSize`, `CARD_BODY_SCALE`) is inline in the page, not a
  component: when you touch the compact card, that function is the unit.
- Every user-facing string is `t('…')` from `useTranslation()`, with the key
  in **both** `frontend/src/i18n/locales/en.ts` and `uk.ts`.

## 4. One idiomatic block — the size-S status row

```tsx
<Card pointer={false}>
  <CardContent>
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-bambu-dark-tertiary rounded-full h-1.5">
        <div className="bg-bambu-green h-1.5 rounded-full" style={{ width: '44%' }} />
      </div>
      <span className="text-xs text-white">44%</span>
      <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium bg-blue-500/20 text-blue-400">
        {t('…')} {/* a translated label — never a literal string */}
      </span>
    </div>
    <div className="mt-1 flex min-h-[14px] items-center gap-2 text-[11px] leading-none text-bambu-gray">
      <span className="flex items-center gap-1"><Clock className="w-3 h-3" />2h 14m</span>
      <span className="font-medium text-bambu-green">ETA 18:42</span>
      <span className="flex items-center gap-1"><Layers className="w-3 h-3" />142/318</span>
    </div>
  </CardContent>
</Card>
```
