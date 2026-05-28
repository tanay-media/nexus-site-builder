# Nexus Site Builder

Dermatology static site + **HEA-001 Trail 5** publisher theme.

## Live site

**https://tanay-media.github.io/nexus-site-builder/**

After push, wait 2–3 minutes for GitHub Actions. In repo **Settings → Pages**, source must be **GitHub Actions** (not “Deploy from branch”).

## Repo layout

| Path | Purpose |
|------|---------|
| `trail-5/` | Theme (`pub.css`, `pub.js`, `build_pages.py`) |
| `images/` | Real images (filenames match raw HTML / WordPress) |
| `0e2dba5e-…/` | Raw Archetype export |
| `0e2dba5e-…-pub/` | Themed build (local backup) |
| `docs/` | **Deployed site** (built by CI / `build-for-github.sh`) |

## Build & push

```bash
./build-for-github.sh
git add -A
git commit -m "Rebuild site"
git push
```

`build-for-github.sh` reads `images/`, writes themed HTML into `docs/` with correct `/nexus-site-builder/…` paths for CSS and links.

## Images (no HTML edits)

Put files in `images/` with the same names as in raw HTML, e.g. `hyaluronic-acid-hero-1.png`. Rebuild copies them to `docs/assets/media/`.

## Local preview

```bash
cd docs && python3 -m http.server 8888
# open http://localhost:8888/  (paths are for GitHub; styling may need --base-url "" for local-only)
```

For local dev without path prefix, build with `--base-url ""` into `-pub`.
