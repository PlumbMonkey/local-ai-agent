# Gene Desktop Application - Build Script
# This script builds the Gene application using PyInstaller

param(
    [switch]$Clean,
    [switch]$Installer
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$InstallerDir = $PSScriptRoot
$DistDir = Join-Path $ProjectRoot "dist"
$BuildDir = Join-Path $ProjectRoot "build"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Gene Desktop Application Builder" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Clean previous builds
if ($Clean) {
    Write-Host "[1/5] Cleaning previous builds..." -ForegroundColor Yellow
    if (Test-Path $DistDir) { Remove-Item -Recurse -Force $DistDir }
    if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir }
    Write-Host "      Cleaned!" -ForegroundColor Green
} else {
    Write-Host "[1/5] Skipping clean (use -Clean flag to clean)" -ForegroundColor Gray
}

# Check for icon
Write-Host "[2/5] Checking assets..." -ForegroundColor Yellow
$IconPath = Join-Path $InstallerDir "gene.ico"
if (-not (Test-Path $IconPath)) {
    Write-Host "      Warning: gene.ico not found. Building without custom icon." -ForegroundColor Yellow
    Write-Host "      Convert Gene Icon.png to .ico format for best results." -ForegroundColor Yellow
} else {
    Write-Host "      Icon found!" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "[3/5] Activating virtual environment..." -ForegroundColor Yellow
$VenvPath = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $VenvPath) {
    & $VenvPath
    Write-Host "      Activated!" -ForegroundColor Green
} else {
    Write-Host "      Error: Virtual environment not found!" -ForegroundColor Red
    exit 1
}

# Build with PyInstaller
Write-Host "[4/5] Building with PyInstaller..." -ForegroundColor Yellow
$SpecFile = Join-Path $InstallerDir "gene.spec"

Push-Location $ProjectRoot
try {
    & python -m PyInstaller --noconfirm $SpecFile
    if ($LASTEXITCODE -ne 0) {
        Write-Host "      PyInstaller failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host "      Build complete!" -ForegroundColor Green
} finally {
    Pop-Location
}

# Create output directory structure
Write-Host "[5/5] Finalizing..." -ForegroundColor Yellow
$OutputDir = Join-Path $DistDir "Gene"
if (Test-Path $OutputDir) {
    Write-Host "      Output: $OutputDir" -ForegroundColor Green
    
    # Copy additional files
    $ReadmeSrc = Join-Path $ProjectRoot "README.md"
    if (Test-Path $ReadmeSrc) {
        Copy-Item $ReadmeSrc (Join-Path $OutputDir "README.txt")
    }
    
    # Create data directories
    $ChatHistoryDir = Join-Path $OutputDir "chat_history"
    $BusinessDataDir = Join-Path $OutputDir "business_data"
    if (-not (Test-Path $ChatHistoryDir)) { New-Item -ItemType Directory -Path $ChatHistoryDir | Out-Null }
    if (-not (Test-Path $BusinessDataDir)) { New-Item -ItemType Directory -Path $BusinessDataDir | Out-Null }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Build Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Output: $OutputDir" -ForegroundColor White
Write-Host ""

# Build installer if requested
if ($Installer) {
    Write-Host "Building Windows Installer..." -ForegroundColor Yellow
    $InnoSetupPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    $IssFile = Join-Path $InstallerDir "gene_setup.iss"
    
    if (Test-Path $InnoSetupPath) {
        & $InnoSetupPath $IssFile
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Installer created successfully!" -ForegroundColor Green
        }
    } else {
        Write-Host "Inno Setup not found. Install from: https://jrsoftware.org/isinfo.php" -ForegroundColor Yellow
    }
}

Write-Host "To run Gene: .\dist\Gene\Gene.exe" -ForegroundColor Cyan
