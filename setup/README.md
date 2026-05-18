# Squelch Windows Installer

## Building the Installer

1. Install [Inno Setup 6.x](https://jrsoftware.org/isinfo.php)
2. Open `squelch.iss` in the Inno Setup Compiler
3. Build → Compile (F9)
4. Output: `setup/Output/Squelch_Setup_v0.9.0.exe`

## Requirements

The installer script expects this structure:
```
squelch/
├── setup/
│   └── squelch.iss    ← this file
├── assets/
│   └── squelch.ico    ← app icon (create or add)
├── main.py
├── installer.py
├── run_squelch.bat
└── ... (all app files)
```

## Creating the Icon

If `assets/squelch.ico` doesn't exist:
1. Create a PNG at 256x256
2. Convert with ImageMagick: `magick icon.png -resize 256x256 squelch.ico`
3. Or use an online ICO converter

## Code Signing (Recommended)

Without a certificate, Windows SmartScreen shows a warning.
Free for open source projects:
- [SignPath Foundation](https://signpath.io/product/foundation)
- Apply at: signpath.io/product/foundation

## Distribution Checklist

- [ ] Build installer
- [ ] Test on a clean Windows machine
- [ ] Sign with SignPath certificate
- [ ] Submit to Microsoft for SmartScreen review (free)
- [ ] Upload to GitHub Releases as `Squelch_Setup_v0.9.0.exe`
