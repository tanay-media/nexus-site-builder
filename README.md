# Nexus Site Builder

Dermatology static site export + **HEA-001 Trail 5** publisher theme (magazine-style health layout).

## Contents

| Folder | Description |
|--------|-------------|
| `trail-5/` | Theme source: `pub.css`, `pub.js`, `build_pages.py`, placeholders |
| `0e2dba5e-b89a-4f6a-81be-1cc735c629c9/` | Raw Archetype HTML export |
| `0e2dba5e-b89a-4f6a-81be-1cc735c629c9-pub/` | **Built themed site** (host this folder) |

## Local preview

```bash
cd 0e2dba5e-b89a-4f6a-81be-1cc735c629c9-pub
python3 -m http.server 8888
```

Open **http://localhost:8888/**

## Rebuild themed site

```bash
cd trail-5
python3 generate_assets.py
python3 build_pages.py --site ../0e2dba5e-b89a-4f6a-81be-1cc735c629c9
```

Add `--fetch-images` if WordPress media is reachable at `dermat.local`.

## GitHub Pages

Push to `main` — the included workflow deploys `0e2dba5e-b89a-4f6a-81be-1cc735c629c9-pub` automatically.

After the first deploy: **Settings → Pages** → confirm source is **GitHub Actions**.
