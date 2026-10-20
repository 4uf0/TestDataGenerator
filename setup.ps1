# Legt eine virtuelle Python-Umgebung an und installiert alle Abhängigkeiten.
# Verwendung: .\setup.ps1  (danach: .venv\Scripts\Activate.ps1)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$VenvDir = if ($env:VENV_DIR) { $env:VENV_DIR } else { ".venv" }

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "python nicht gefunden. Bitte Python 3.10+ installieren (https://www.python.org/downloads/, 'Add to PATH' aktivieren)."
}

Write-Host "Erstelle virtuelle Umgebung in $VenvDir ..."
python -m venv $VenvDir

Write-Host "Installiere Abhaengigkeiten ..."
& "$VenvDir\Scripts\python.exe" -m pip install --upgrade pip
& "$VenvDir\Scripts\python.exe" -m pip install -r requirements.txt

Write-Host ""
Write-Host "Fertig. Umgebung aktivieren mit:"
Write-Host "    $VenvDir\Scripts\Activate.ps1"
Write-Host ""
Write-Host "Dann z. B.:"
Write-Host "    python generate_fit.py --duration 40"
Write-Host "    `$env:GARMIN_EMAIL='...'; `$env:GARMIN_PASSWORD='...'; python upload_to_garmin.py out/"
