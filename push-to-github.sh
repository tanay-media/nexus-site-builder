#!/bin/bash
# Run once after: gh auth login
set -euo pipefail
cd "$(dirname "$0")"

REPO="tanay-media/nexus-site-builder"

if ! gh auth status &>/dev/null; then
  echo "Not logged in. Run: gh auth login"
  exit 1
fi

if git remote get-url origin &>/dev/null; then
  echo "Remote origin already set."
else
  gh repo create "$REPO" --public \
    --description "Dermatology static site + HEA-001 Trail 5 publisher theme" \
    --source=. --remote=origin
fi

git push -u origin main
echo ""
echo "Done: https://github.com/${REPO}"
echo "Enable Pages: Settings → Pages → Source: GitHub Actions (workflow included)"
