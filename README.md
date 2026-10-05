# Keep Walking

Tray utility for Helldivers 2 that adds a keyboard walk mode by emulating a partial Xbox 360 left stick through [ViGEmBus](https://github.com/nefarius/ViGEmBus).

Optional Bingus addon lets you bind Walk / Faster / Slower in **Options → Mouse & Keyboard → MODS** (section **Keep Walking**).

This repository is the source for the Nexus Mods upload. The downloadable file is a PyInstaller one-file `.exe`.

## Requirements to build

- Windows 64-bit
- Python 3.12+ (64-bit)
- `pip install vgamepad pyinstaller`

## Build the exe

From this folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

Output:

```text
dist\KeepWalking.exe
```

## Optional Bingus addon zip

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

Output:

```text
build\Keep-Walking-Addon-v1.zip
```

Requires Bingus Shared Loader v17+ and Mod Bindings Menu v2.0+.

## What the exe does

- Runs in the system tray
- Creates a virtual Xbox pad only while Helldivers 2 is running
- Swallows WASD while walk mode is on and drives a partial left stick instead
- May ask once to install the ViGEmBus driver (user confirmation required)
- Does not inject into the game process and does not modify game memory
- No auto-updater / no intended network features

## Main source files

| Path | Role |
|---|---|
| `app/walk_tray.py` | Tray app (built into `KeepWalking.exe`) |
| `build_exe.ps1` | PyInstaller build script |
| `src/keep_walking.lua` | Optional Bingus addon |
| `build.ps1` / `scripts/build_addon.py` | Arsenal addon packer |
