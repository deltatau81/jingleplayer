$ErrorActionPreference = "Stop"

$ProjectRoot = $PSScriptRoot
$EntryPoint  = Join-Path $ProjectRoot "jingleplayer_gui_tkinter.py"
$Icon       = Join-Path $ProjectRoot "assets\jingleplayer.ico"
$HelpFile   = Join-Path $ProjectRoot "HELP.md"
$BuildDir   = Join-Path $ProjectRoot "build"
$DistDir    = Join-Path $ProjectRoot "dist"
$SpecDir    = Join-Path $BuildDir "pyinstaller-spec"
$TestTemp   = Join-Path $env:USERPROFILE "jingleplayer-pytest-temp"

Set-Location $ProjectRoot

Write-Host ""
Write-Host "========================================"
Write-Host " Jingleplayer - Windows Build"
Write-Host "========================================"
Write-Host ""

# Required files
foreach ($File in @($EntryPoint, $Icon, $HelpFile)) {
    if (-not (Test-Path $File)) {
        throw "Erforderliche Datei fehlt: $File"
    }
}

Write-Host "[1/6] Python"
python --version
if ($LASTEXITCODE -ne 0) {
    throw "Python konnte nicht gestartet werden."
}

Write-Host ""
Write-Host "[2/6] PyInstaller"
python -m PyInstaller --version
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller ist nicht installiert."
}

Write-Host ""
Write-Host "[3/6] Syntaxpruefung"
python -m py_compile $EntryPoint
if ($LASTEXITCODE -ne 0) {
    throw "Syntaxpruefung fehlgeschlagen."
}

Write-Host ""
Write-Host "[4/6] Automatische Tests"
New-Item -ItemType Directory -Force -Path $TestTemp | Out-Null

python -m pytest -v `
    --basetemp="$TestTemp" `
    -p no:cacheprovider

if ($LASTEXITCODE -ne 0) {
    throw "Tests fehlgeschlagen. Build wird abgebrochen."
}

Write-Host ""
Write-Host "[5/6] Alte Build-Artefakte entfernen"

if (Test-Path $BuildDir) {
    Remove-Item $BuildDir -Recurse -Force
}

if (Test-Path $DistDir) {
    Remove-Item $DistDir -Recurse -Force
}


Write-Host ""
Write-Host "[6/6] Jingleplayer.exe erstellen"

New-Item -ItemType Directory -Force -Path $SpecDir | Out-Null

python -m PyInstaller `
    --noconfirm `
    --clean `
    --specpath "$SpecDir" `
    --onefile `
    --windowed `
    --name "Jingleplayer" `
    --icon "$Icon" `
    --add-data "$Icon;assets" `
    --add-data "$HelpFile;." `
    "$EntryPoint"

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller-Build fehlgeschlagen."
}

$Exe = Join-Path $DistDir "Jingleplayer.exe"

if (-not (Test-Path $Exe)) {
    throw "Build abgeschlossen, aber Jingleplayer.exe wurde nicht gefunden."
}

$ExeInfo = Get-Item $Exe

Write-Host ""
Write-Host "========================================"
Write-Host " BUILD ERFOLGREICH"
Write-Host "========================================"
Write-Host ""
Write-Host "EXE:   $($ExeInfo.FullName)"
Write-Host "Groesse: $([math]::Round($ExeInfo.Length / 1MB, 2)) MB"
Write-Host ""
Write-Host "Die EXE wurde noch nicht automatisch gestartet."
Write-Host "Bitte anschliessend manuell testen."
Write-Host ""
