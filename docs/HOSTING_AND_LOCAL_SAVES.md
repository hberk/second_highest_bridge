# Hosting on GitHub Pages, and saving games in the browser

Status: **notes, nothing built.** This is a companion to
[ONLINE_PLAN.md](ONLINE_PLAN.md), which stays the design for accounts, saved
hands and live tables (Supabase). What's here comes before that plan, or sits
alongside it:

- hosting the Svelte app on GitHub Pages instead of Azure Static Web Apps;
- what each feature needs from a server;
- what the browser can save with no server at all.

## Hosting the Svelte app on GitHub Pages

The Svelte app is a good fit for GitHub Pages:

- **Fully static.** `npm run build` writes plain HTML, CSS and JS to
  `frontend/dist`. Rules, robots, scoring and the challenge library all run in
  the browser.
- **No routes yet.** The tabs are component state, not URLs, so Pages' lack
  of a single-page-app fallback doesn't matter. A hash router (`#/history`, as
  ONLINE_PLAN Phase 1 proposes) keeps that true. Path-based routes would need
  the usual `404.html` copy of `index.html`.
- **Base path.** Pages serves the site at
  `https://hberk.github.io/second_highest_bridge/`, not at the domain root.
  Build with `base: './'` (relative asset paths) or
  `base: '/second_highest_bridge/'` in `vite.config.ts`. A relative base was
  tested on 2026-10-13: the built site works served from a sub-path.

| requirement | detail |
|---|---|
| Public repository | Pages from a **private** repo on a personal account needs GitHub Pro. On the free plan, the repo must be public. |
| The site is public | Pages has no access control for personal accounts. Anyone with the URL can play. |
| Pages source | Settings → Pages → Source: **GitHub Actions** |

### Workflow

Reuse the Azure workflow's gate: fixtures from Python 3.12, then `npm ci`,
`npm run check`, `npm test` and `npm run build`. Keep the 3.12 pin, which is
why the fixtures are exact. Then replace the Azure deploy step with the
standard Pages actions:

```yaml
permissions:
  contents: read
  pages: write
  id-token: write

# ...build job: the existing steps through `npm run build`, then
      - uses: actions/upload-pages-artifact@v3
        with:
          path: frontend/dist

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

Deploy only on pushes to `main`. Pages has no per-pull-request preview
environments the way Azure Static Web Apps does.

### Security headers

GitHub Pages can't set custom response headers, so
`frontend/public/staticwebapp.config.json` would do nothing there.

- **CSP:** move it into `frontend/index.html` as
  `<meta http-equiv="Content-Security-Policy" content="...">`.
  - `frame-ancestors` is ignored in a meta tag, so the site *can* be framed by
    other pages. That's acceptable for a game with no sign-in. Revisit when
    accounts arrive.
  - Once ONLINE_PLAN Phase 1 lands, the Supabase `connect-src` entries go in
    that meta tag instead of the Azure config.
- **Referrer policy:** `<meta name="referrer" content="no-referrer">`.
- **`X-Content-Type-Options`, `Permissions-Policy`:** these have no meta
  equivalent. Pages already serves correct content types.

## What needs a server

| want | server? | route |
|---|---|---|
| Saved games and stats on one device | **No** | Browser storage, next section |
| Accounts; history on every device | Hosted, no code of ours | Supabase Auth + Postgres with RLS (ONLINE_PLAN Phase 1) |
| Results other people can trust (leaderboards) | Yes, with logic | Server-side replay. Only `trusted=true` rows count, as ONLINE_PLAN already says |
| Live tables with friends | Yes, real-time | ONLINE_PLAN Phase 2: Edge Function + Realtime |

**Alternative considered: Cloudflare.** Workers plus Durable Objects (one
object per table) can serve the static site *and* run live tables on one
platform.
- **Free plan** (checked 2026-10-13; confirm on Cloudflare's pricing page):
  SQLite-backed Durable Objects only, 100,000 requests a day, and 5 GB of
  storage. Going over a limit fails requests; there are no charges.
- **Trade-off:** Cloudflare has no hosted login or Postgres RLS, so accounts
  would have to be built. Supabase stays the better fit for the plan as
  written. Cloudflare is worth a look only if Edge Function CPU limits bite in
  Phase 2.

## Saving games in the browser

### What is saved today

- **Saved:** only the **Display settings**, in `localStorage` under
  `shb-settings` (`frontend/src/lib/settings.svelte.ts`).
- **Lost on reload:** everything else lives in memory and is gone when the page
  reloads:
  - `Game.history` (`HistoryRecord[]`);
  - `Game.challengeLog`;
  - the passed-out count;
  - the session score derived from these.

  So `dealChallenge()` can re-deal a library board already played in an
  earlier visit.

### How long browser storage lasts

`localStorage` (and IndexedDB) survive closing the browser, restarts and
reboots. They are lost or kept apart when:

- **the player clears site data** or cookies for the site;
- **a private or incognito window** closes; nothing outlives it;
- **Safari on iPhone/iPad goes 7 days without a visit.** Safari deletes the
  site's script-written storage. A site added to the Home Screen is exempt. This
  is the one that matters for a phone game;
- **the device or browser differs.** Storage is per browser, per device.
  Nothing syncs; that's what accounts are for;
- **the origin differs.** Storage belongs to one origin (scheme + host).
  Moving the site, for example from a preview URL to `hberk.github.io`, starts
  everyone empty.

**Size is not a concern.** A board's record is about 1 KB and `localStorage`
allows about 5 MB per origin, so thousands of boards fit.
`navigator.storage.persist()` asks the browser not to evict the site's data
under storage pressure.

### Proposed: local saves before accounts

1. **Save after every finished board.** In `Game.finishBoard()` and the
   passed-out path, write `history`, `challengeLog` and `passedOutCount` to
   `localStorage`.
   - Use a versioned key, `shb-games-v1`, holding
     `{version, history, challengeLog, passedOut}`. A schema change bumps the
     version and migrates on read, as ONLINE_PLAN's `schema_version` does.
   - Wrap the write in `try/catch`, as `settings.save()` does. Storage can be
     full or blocked, and a failed save must never break play.
2. **Load in the `Game` constructor,** then deal the first board as today. On a
   failed parse or an unknown version, keep the raw string under a backup key
   and start empty rather than crash.
3. **Use the same record shape as the server.** `HistoryRecord` is already what
   ONLINE_PLAN stores in `boards.record`, so local boards upload unchanged.
   Phase 1's "boards played as a guest stay in memory; on sign-in, offer to
   save them" becomes **"on sign-in, offer to upload the boards saved on this
   device"**.
4. **Give the player control:**
   - a **Clear saved games** button;
   - **Download all boards (.lin)** stays the backup;
   - **Import LIN** is the way to move boards between devices until there are
     accounts.
5. **Cap the list.** Keep the most recent N boards (say 500) so `localStorage`
   can't fill up silently. The `.lin` export is the archive.
6. **Ask for persistence once.** Call `navigator.storage.persist()` after the
   first saved board. Browsers that refuse it lose nothing.

**Tests:** `game.test.ts` with a stubbed `localStorage` checks:
- a finished board survives a new `Game()`;
- a corrupt or old-version payload doesn't throw;
- a full or throwing storage never blocks `finishBoard()`;
- `dealChallenge()` skips deals in a restored `challengeLog`.
