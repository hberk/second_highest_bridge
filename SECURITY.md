# Security policy

## Reporting a vulnerability

Please report security problems **privately**, not in a public issue: open the
repository's **Security** tab and choose **Report a vulnerability**. I'll
reply as soon as I can, and credit you in the fix if you'd like.

## What's in scope

- **The web app** (`frontend/`, served from GitHub Pages). It is a static
  site: no server and no accounts. Its one network call after loading is
  Cloudflare Web Analytics, which counts page views without cookies; the
  page's Content Security Policy allows that and nothing else. Saved games
  stay in your browser's `localStorage`. The likeliest problem is
  markup injection through the two places it accepts text: the alert box in
  the bidding box, and LIN import in the History tab. No component renders
  raw HTML (`{@html}` is banned by a test), and the page's Content Security
  Policy allows scripts only from the site itself and Cloudflare's analytics
  script, plus WebAssembly compiled from the site's own double dummy solver
  (`research/solver-rs/wasm`), which runs in a worker on boards from your own
  history.

The Python code is the engine the web app is ported from and isn't deployed.
`research/` holds offline tooling; apart from the solver's WebAssembly build,
the site doesn't include it, so problems there are ordinary bugs rather than
security issues.

## Supported versions

Only the current `main` branch, which is what the live site runs.
