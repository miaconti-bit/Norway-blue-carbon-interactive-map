#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# setup_github.sh  —  One-time script to initialise the git repo and push to
#                      a new GitHub repository.
#
# BEFORE RUNNING:
#   1. Create an empty repo on GitHub (no README, no .gitignore, no licence).
#      Call it: norway-blue-carbon-map
#   2. Copy the repo URL from the "Quick setup" page — it looks like:
#          https://github.com/YOUR-USERNAME/norway-blue-carbon-map.git
#   3. Paste it into GITHUB_URL below, then run:
#          bash setup_github.sh
# ─────────────────────────────────────────────────────────────────────────────

GITHUB_URL="https://github.com/miaconti-bit/Norway-blue-carbon-interactive-map.git"

set -e

# ── Make sure we're in the right folder ──────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
echo "Working in: $SCRIPT_DIR"

# ── Remove any stale git state and start fresh ────────────────────────────────
rm -rf .git
# Remove nested .git dirs so subdirectories aren't treated as submodules
find . -mindepth 2 -name ".git" -exec rm -rf {} + 2>/dev/null || true
git init
git branch -m main
git config user.email "mlconti@ucsd.edu"
git config user.name "Mia Conti"

# ── Stage everything (respects .gitignore) ─────────────────────────────────
git add -A

echo ""
echo "=== Files to be committed ==="
git status --short

echo ""
echo "=== Size check — anything >50 MB will be flagged ==="
git ls-files | while read f; do
  size=$(stat -f%z "$f" 2>/dev/null || stat -c%s "$f" 2>/dev/null || echo 0)
  if [ "$size" -gt 52428800 ]; then
    echo "  ⚠  $(du -sh "$f" | cut -f1)  $f"
  fi
done
echo ""

# ── Initial commit ────────────────────────────────────────────────────────────
git commit -m "Initial commit: Norway blue carbon interactive map pipeline

- Interactive Folium map of Norwegian seagrass and kelp study sites
- Layers: Naturbase HB19 habitat polygons, marine protected areas,
  EMODnet human pressures, aquaculture register, MASSIMAL, SeaBee
- Full Python pipeline (build_master_inventory → build_norway_map)
- Spatial co-location analysis (pressure × protection overlap)
- Processed data CSVs and colocation figures
- GitHub Pages landing page in docs/
- MIT licence"

# ── Connect to GitHub and push ────────────────────────────────────────────────
git remote add origin "$GITHUB_URL"
git push -u origin main

echo ""
echo "✅  Done! Your repo is live at:"
echo "    ${GITHUB_URL%.git}"
echo ""
echo "Next steps:"
echo "  1. On GitHub → Settings → Pages → Source: 'Deploy from branch' →"
echo "     Branch: main, Folder: /docs → Save"
echo "  2. Copy maps/norway.html → docs/norway.html and push to make the"
echo "     map browseable at  https://YOUR-USERNAME.github.io/norway-blue-carbon-map/"
echo "  3. Update the two 'YOUR-USERNAME' placeholders in README.md and"
echo "     docs/index.html with your actual GitHub username."
