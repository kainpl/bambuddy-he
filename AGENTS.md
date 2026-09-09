# AGENTS.md

The guide for coding agents working in this repository is **[`CLAUDE.md`](CLAUDE.md)**.
The name is Claude Code's convention; the content is tool-agnostic — read it
first whatever assistant you are. It covers the architecture, the commands that
actually verify a change, the invariants that must not be broken, and the
checklist for adding an endpoint, a column, a permission or a translation.

The five things that most often go wrong for an agent here:

1. **Every user-facing string exists in `en` and `uk`** — frontend locales and
   backend `data/*_en.json` / `*_uk.json` alike. One language is a failing test.
2. **A schema change is a model edit AND a new migration** (`backend/app/migrations/mNNN_*.py`).
   Existing migrations are frozen after a release; never edit one.
3. **`npm run typecheck`, never bare `npx tsc --noEmit`** — the latter enters no
   file and exits 0 on anything.
4. **Every new `Permission` lands in three places** (`core/permissions.py`, the
   API-key scope map in `core/auth.py`, and a seed for Administrators in the
   migration) — a drift-guard test fails otherwise.
5. **Tests are run, not described.** `ruff check backend/`, `pytest backend/tests/`
   (or the targeted file), `npm run lint && npm run typecheck && npm run test:run`
   — and the CHANGELOG entry goes in the same change.

`CONTRIBUTING.md` has the setup, the CI checks and the house rules, including
a section on working with an AI assistant.
