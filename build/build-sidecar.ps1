# build-sidecar.ps1
# Build the Python sidecar into a single Windows executable via PyInstaller.
#
# Output:
#   desktop\resources\sidecar\agf-coscientist-backend.exe
#
# Prerequisites:
#   - Python 3.11 on PATH
#   - `pip install -r requirements-api.txt && pip install pyinstaller`

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

$OutDir = Join-Path $RepoRoot "desktop\resources\sidecar"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host "[build-sidecar] cleaning previous build artefacts..."
$WorkDir = Join-Path $RepoRoot "build\pyinstaller-work"
if (Test-Path $WorkDir) {
    Remove-Item -Recurse -Force $WorkDir
}

Write-Host "[build-sidecar] running pyinstaller..."
python -m PyInstaller `
    "build\pyinstaller.spec" `
    --distpath $OutDir `
    --workpath $WorkDir `
    --noconfirm `
    --clean

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "[build-sidecar] sidecar binary written to: $OutDir"
Get-ChildItem $OutDir | Format-Table -AutoSize
