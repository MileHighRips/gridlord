#!/usr/bin/env bash
# Install the requested VS Code / repo skills.
set -euo pipefail

echo "Installing skills..."
npx skills add https://github.com/vercel-labs/skills --skill find-skills
npx skills add https://github.com/mattpocock/skills --skill grill-me
npx skills add https://github.com/anthropics/skills --skill frontend-design
npx skills add https://github.com/mattpocock/skills --skill improve-codebase-architecture
echo "Done."
