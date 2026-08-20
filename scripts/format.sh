#!/usr/bin/env bash
# Format all frontend + config files with Prettier.
set -euo pipefail
npx prettier --write "frontend/src/**/*.{ts,tsx,css}" "**/*.{json,md,yml}"
