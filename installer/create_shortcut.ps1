# Create Desktop Shortcut for Gene
# Run this after building to add Gene to your desktop

$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $DesktopPath "Gene.lnk"

# Get the Gene executable path
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$GenePath = Join-Path $ProjectRoot "dist\Gene\Gene.exe"
$IconPath = Join-Path $ProjectRoot "installer\gene.ico"

if (-not (Test-Path $GenePath)) {
    Write-Host "Error: Gene.exe not found at $GenePath" -ForegroundColor Red
    Write-Host "Please build Gene first using: .\installer\build.ps1" -ForegroundColor Yellow
    exit 1
}

# Create the shortcut
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $GenePath
$Shortcut.WorkingDirectory = Split-Path $GenePath
$Shortcut.Description = "Gene - Generative Engine for Natural Engagement"

if (Test-Path $IconPath) {
    $Shortcut.IconLocation = $IconPath
}

$Shortcut.Save()

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Desktop Shortcut Created!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Location: $ShortcutPath" -ForegroundColor White
Write-Host ""
Write-Host "You can now launch Gene from your desktop!" -ForegroundColor Cyan
