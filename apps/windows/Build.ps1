$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $python)) { throw 'Create the root Python 3.11 .venv and install packages/engine/requirements.txt first.' }
& $python (Join-Path $PSScriptRoot 'scripts\build_icon.py')
if ($LASTEXITCODE) { throw 'Icon generation failed.' }
& node --test (Join-Path $PSScriptRoot 'tests\lifecycle.test.cjs')
if ($LASTEXITCODE) { throw 'Desktop lifecycle checks failed.' }
Push-Location (Join-Path $projectRoot 'apps\website')
try { & npm.cmd run build; if ($LASTEXITCODE) { throw 'Website build failed.' } } finally { Pop-Location }
Push-Location (Join-Path $PSScriptRoot 'backend')
try {
  & $python -m PyInstaller --noconfirm --distpath dist --workpath build CopilotEngine.spec
  if ($LASTEXITCODE) { throw 'Python packaging failed.' }
  & $python test_bridge.py -v
  if ($LASTEXITCODE) { throw 'Packaged engine checks failed.' }
} finally { Pop-Location }
Push-Location $PSScriptRoot
try {
  if (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'vendor\nsis\Bin\makensis.exe')) {
    $env:ELECTRON_BUILDER_NSIS_DIR = Join-Path $PSScriptRoot 'vendor\nsis'
    $env:ELECTRON_BUILDER_NSIS_RESOURCES_DIR = Join-Path $PSScriptRoot 'vendor\nsis-resources'
  }
  & npm.cmd run dist
  if ($LASTEXITCODE) { throw 'Windows installer build failed.' }
  & node scripts\check-packaged.cjs
  if ($LASTEXITCODE) { throw 'Packaged startup and shutdown checks failed.' }
  & node scripts\check-icons.cjs
  if ($LASTEXITCODE) { throw 'Packaged icon checks failed.' }
} finally { Pop-Location }
$version = (Get-Content -Raw (Join-Path $PSScriptRoot 'package.json') | ConvertFrom-Json).version
$installer = Join-Path $projectRoot "releases\windows\ReplyCue-Setup-$version.exe"
foreach ($folder in @('apps\website\public\downloads','apps\website\out\downloads')) {
  $destination = Join-Path $projectRoot $folder
  New-Item -ItemType Directory -Force $destination | Out-Null
  Copy-Item -LiteralPath $installer -Destination $destination -Force
}
Get-FileHash -Algorithm SHA256 -LiteralPath $installer | Format-List
Write-Host "Installer ready: $installer"
