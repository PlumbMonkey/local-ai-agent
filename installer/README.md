# Gene Installer Build Guide

## Prerequisites

1. **Python 3.11+** with virtual environment set up
2. **PyInstaller** - `pip install pyinstaller`
3. **Inno Setup 6** (optional, for Windows installer) - Download from https://jrsoftware.org/isinfo.php

## Files

| File | Description |
|------|-------------|
| `gene.spec` | PyInstaller specification file |
| `gene_setup.iss` | Inno Setup script for Windows installer |
| `build.ps1` | PowerShell build automation script |
| `gene.ico` | Application icon (you need to create this) |

## Creating the Icon

Convert the Gene icon PNG to ICO format:

### Option 1: Online Converter
1. Go to https://convertio.co/png-ico/
2. Upload `interfaces/desktop/assets/gene_icon.png`
3. Convert and download as `gene.ico`
4. Place in this `installer/` folder

### Option 2: Using Python
```python
from PIL import Image
img = Image.open('interfaces/desktop/assets/gene_icon.png')
img.save('installer/gene.ico', format='ICO', sizes=[(256,256), (128,128), (64,64), (48,48), (32,32), (16,16)])
```

## Building

### Quick Build (Executable Only)
```powershell
cd installer
.\build.ps1
```

### Clean Build
```powershell
.\build.ps1 -Clean
```

### Full Build with Installer
```powershell
.\build.ps1 -Clean -Installer
```

## Output

- **Executable**: `dist/Gene/Gene.exe`
- **Installer**: `dist/installer/Gene_Setup_1.0.0.exe`

## Manual Build Steps

If the script doesn't work, you can build manually:

```powershell
# From project root
cd "D:\Dev Projects 2025\local-ai-agent"

# Activate venv
.\.venv\Scripts\Activate.ps1

# Build with PyInstaller
python -m PyInstaller --noconfirm installer\gene.spec

# Run the app
.\dist\Gene\Gene.exe
```

## Customization

### Wizard Images (Optional)
For Inno Setup, you can add custom installer images:
- `wizard_large.bmp` - 164x314 pixels (left side of installer)
- `wizard_small.bmp` - 55x58 pixels (top right corner)

### Version Updates
Update the version number in:
1. `gene_setup.iss` - `#define MyAppVersion "1.0.0"`
2. Your app's `__init__.py` or version file

## Troubleshooting

### "DLL not found" errors
Add missing DLLs to the `binaries` list in `gene.spec`

### "Module not found" errors
Add missing modules to `hidden_imports` in `gene.spec`

### Antivirus false positives
PyInstaller executables sometimes trigger AV software. You may need to:
1. Sign the executable with a code signing certificate
2. Submit to AV vendors for whitelisting
