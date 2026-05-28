#!/bin/bash
# Build themed site into docs/ for GitHub Pages + local -pub backup
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/trail-5"
python3 generate_assets.py
python3 build_pages.py \
  --site "../0e2dba5e-b89a-4f6a-81be-1cc735c629c9" \
  --out "../docs" \
  --base-url /nexus-site-builder
python3 build_pages.py \
  --site "../0e2dba5e-b89a-4f6a-81be-1cc735c629c9" \
  --out "../0e2dba5e-b89a-4f6a-81be-1cc735c629c9-pub" \
  --base-url /nexus-site-builder
echo "Done. GitHub site: docs/ → https://tanay-media.github.io/nexus-site-builder/"
