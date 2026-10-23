# dashboard

## Owners

- `docs/dashboard.md`; the core-hub write token: `docs/core-hub/http-api.md`.

## Commands

Run from `services/dashboard/`.

```bash
npm ci && npm run lint && npx tsc --noEmit && npm run test:ci   # lint, types, tests
npm run build && npm run test:bundle                              # build + bundle secret check
```

The bundle check needs the server-only variables set for the build; CI sets sentinel values in `.github/workflows/dashboard.yml`.

## Layout

- `src/app/`: pages and route handlers; `src/proxy.ts`: session check; `src/lib/`: BFF, typed client, session.
- `src/__tests__/`: tests; `scripts/hash-password.mjs`: password hash for `.env`.

## Requirements that bite here

- DSH-002: browser talks only to the dashboard.
- DSH-003: single-user login.
- DSH-006: `src/proxy.ts` is the only authorization point.
- DSH-009: BFF sends the write token on core-hub writes.
- HUB-041: core-hub writes need the bearer token.
- DSH-013: no secret or backend URL in the bundle.

## Trap pointers

- DSH-003: bcrypt `$` in `.env` and `.env.local`: `docs/dashboard.md`, Known traps.
- DSH-006: Next 16 `proxy`, no `next lint`: `docs/dashboard.md`, Known traps.
