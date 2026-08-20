# Install the requested VS Code / repo skills (Windows PowerShell).
$ErrorActionPreference = 'Stop'

Write-Host 'Installing skills...'
npx skills add https://github.com/vercel-labs/skills --skill find-skills
npx skills add https://github.com/mattpocock/skills --skill grill-me
npx skills add https://github.com/anthropics/skills --skill frontend-design
npx skills add https://github.com/mattpocock/skills --skill improve-codebase-architecture
Write-Host 'Done.'
