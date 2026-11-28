# Security policy

## Reporting a vulnerability

Please report security problems **privately**, not in a public issue: open the
repository's **Security** tab and choose **Report a vulnerability**. I'll
reply as soon as I can, and credit you in the fix if you'd like.

## What's in scope

- **The web app** (`frontend/`), served from Cloudflare at
  https://bridge.second-highest.workers.dev with the table server for play
  with friends (`server/cf`, a Worker and a Durable Object per table). Solo
  play sends nothing during play, only one anonymous visit beacon (no
  cookies) when the page loads; the page's only other connection is the table
  socket on its own origin, and the Content Security Policy (sent as a header,
  `server/cf/_headers`) allows that and nothing else. There are no accounts,
  and saved games stay in your browser's `localStorage`. The likeliest problem
  is markup injection through the places it accepts text: the alert box in
  the bidding box, LIN import in the History tab and a table name. No
  component renders raw HTML (`{@html}` is banned by a test), and the Content
  Security Policy allows scripts only from the site itself, plus WebAssembly
  compiled from the site's own double dummy solver (`research/solver-rs/wasm`),
  which runs in a worker on boards from your own history. A seat must never
  see another hand's cards before they are played; a table that leaks one is
  in scope.

The Python code is the engine the web app is ported from and isn't deployed.
`research/` holds offline tooling; apart from the solver's WebAssembly build,
the site doesn't include it, so problems there are ordinary bugs rather than
security issues.

## Supported versions

Only the current `main` branch, which is what the live site runs.
