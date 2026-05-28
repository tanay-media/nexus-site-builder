# HEA-001 Trail 5 — Health Publisher Theme

Transforms any **Archetype** static HTML export (`arch-*` classes) into a magazine-style health publisher layout (hims / WebMD inspired).

## Quick start

```bash
cd trail-5

# 1. Generate placeholder images (first time only)
python3 generate_assets.py

# 2. Build themed site from a raw export folder
python3 build_pages.py --site ../0e2dba5e-b89a-4f6a-81be-1cc735c629c9

# 3. Preview (from output folder)
cd ../0e2dba5e-b89a-4f6a-81be-1cc735c629c9-pub
python3 -m http.server 8080
# Open http://localhost:8080/
```

## Apply to any site

```bash
python3 build_pages.py --site /path/to/raw-export --out /path/to/output
```

- **Input**: folder containing Archetype `index.html` pages and optional `assets/archetype.css`
- **Output**: full static site with `assets/pub.css`, `assets/pub.js`, themed homepage, category hubs, and all articles

Raw exports are never modified; output defaults to `<site-folder-name>-pub` beside the input.

### Images

Archetype exports usually reference **remote WordPress URLs** (e.g. `http://dermat.local/wp-content/uploads/...`) — image files are **not** included in the HTML folder, only links.

The builder:

1. Copies theme placeholder JPEGs into `assets/`
2. Maps every remote URL to a local file in `assets/media/` (one file per unique URL)
3. Rewrites all `<img src="…">` in the output HTML

By default, placeholders are used (fast, works offline). For real photos from your WordPress install:

```bash
python3 build_pages.py --site ../your-export --fetch-images
```

Requires WordPress/media reachable at `dermat.local` (or edit hosts to point at your server).

## Files

| File | Purpose |
|------|---------|
| `pub.css` | Design tokens + layout (Inter, cream palette, soft shadows) |
| `pub.js` | Mobile nav, TOC scroll-spy, copy link |
| `build_pages.py` | Parses raw HTML, maps `arch-*` → `pub-*`, generates pages |
| `generate_assets.py` | Creates local placeholder JPEGs in `shared/assets/` |
| `THEME-SPEC.md` | Full theme DNA specification |

## Dermatology example

| Folder | Description |
|--------|-------------|
| `../0e2dba5e-b89a-4f6a-81be-1cc735c629c9` | Original Archetype export |
| `../0e2dba5e-b89a-4f6a-81be-1cc735c629c9-pub` | Themed output (71 pages) |
