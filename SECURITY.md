# Security policy

## Reporting a vulnerability

Please report security problems **privately**, not in a public issue: open the
repository's **Security** tab and choose **Report a vulnerability**. I'll
reply as soon as I can, and credit you in the fix if you'd like.

## What's in scope

- **The web app** (`frontend/`, served from GitHub Pages). It is a static
  site: no server, no accounts, no network calls after the page loads. Saved
  games stay in your browser's `localStorage`. The likeliest problem is
  markup injection through the two places it accepts text: the alert box in
  the bidding box, and LIN import in the History tab. No component renders
  raw HTML (`{@html}` is banned by a test), and the page's Content Security
  Policy allows scripts only from the site itself.
- **The Streamlit app** (`app.py`, `web/`). It renders some of its own HTML,
  and every string that reaches it is escaped; `tests/test_web_escaping.py`
  enforces that and lists each text input that has been reviewed.

`research/` holds offline tooling that neither app imports, so problems there
are ordinary bugs rather than security issues.

## Supported versions

Only the current `main` branch, which is what the live site runs.
