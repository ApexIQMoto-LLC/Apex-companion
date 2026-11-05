# Run from an extracted APEX Companion v0.11 public-source folder.
# Requires Git for Windows and a GitHub-authenticated credential helper.
$ErrorActionPreference = 'Stop'
$repo = 'https://github.com/Opticbossiyt/Apex-companion.git'
Set-Location $PSScriptRoot
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Install Git for Windows first: https://git-scm.com/download/win' }
$forbidden = @('.env','config.json','data','models','.venv','venv','__pycache__')
foreach ($item in $forbidden) {
  if (Test-Path -LiteralPath (Join-Path $PSScriptRoot $item)) {
    throw "Local private item found: $item. Move/remove it from the publish folder before continuing."
  }
}
if (-not (Test-Path .git)) { git init | Out-Host; if ($LASTEXITCODE -ne 0) { throw 'git init failed' } }
git remote get-url origin 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
  $existing = (git remote get-url origin).Trim()
  if ($existing -ne $repo) { throw "Refusing to use unexpected remote: $existing" }
} else { git remote add origin $repo }
# Preserve an existing remote main history without force push.
git fetch origin main 2>$null | Out-Host
if ($LASTEXITCODE -eq 0) {
  git checkout -B public-companion-v0.11 origin/main | Out-Host
} else {
  git checkout -B main | Out-Host
}
if ($LASTEXITCODE -ne 0) { throw 'Cannot create local branch' }
git add --all
if ($LASTEXITCODE -ne 0) { throw 'git add failed' }
Write-Host 'Review staged changes:' -ForegroundColor Cyan
git status --short | Out-Host
git diff --cached --check | Out-Host
if ($LASTEXITCODE -ne 0) { throw 'Diff check failed' }
git diff --cached --stat | Out-Host
Write-Host 'Check the staged files for private content. This script does not independently audit the source.' -ForegroundColor Yellow
$confirm = Read-Host 'Type PUBLISH to commit and push these files'
if ($confirm -cne 'PUBLISH') { throw 'Cancelled; nothing was pushed' }
git commit -m 'Import public-safe Apex Companion v0.11.0 application source' | Out-Host
if ($LASTEXITCODE -ne 0) { throw 'Commit failed; check git name/email and staged changes' }
$branch = (git branch --show-current).Trim()
git push -u origin $branch | Out-Host
if ($LASTEXITCODE -ne 0) { throw 'Push failed. Check repository permissions and GitHub sign-in.' }
Write-Host "Pushed $branch to $repo" -ForegroundColor Green
if ($branch -ne 'main') { Write-Host 'Open a PR into main and review it before merging.' }
