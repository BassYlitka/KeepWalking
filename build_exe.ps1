$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$vg = python -c "import vgamepad, pathlib; print(pathlib.Path(vgamepad.__file__).resolve().parent)"
$dll = Join-Path $vg 'win\vigem\client\x64\ViGEmClient.dll'
$msi = Join-Path $vg 'win\vigem\install\x64\ViGEmBusSetup_x64.msi'
python (Join-Path $root 'make_ico.py') | Out-Host
python -m pip install --disable-pip-version-check pyinstaller | Out-Host
$iconDir = Join-Path $root 'icons'
python -m PyInstaller --noconfirm --clean --onefile --noconsole --name KeepWalking `
    --optimize 2 `
    --icon (Join-Path $iconDir 'app.ico') `
    --distpath (Join-Path $root 'dist') `
    --workpath (Join-Path $root 'build\pyinstaller') `
    --specpath (Join-Path $root 'build') `
    --add-binary "$dll;vgamepad/win/vigem/client/x64" `
    --add-data "$msi;vgamepad/win/vigem/install/x64" `
    --add-data "$iconDir;icons" `
    --hidden-import vgamepad.win.virtual_gamepad `
    --hidden-import vgamepad.win.vigem_client `
    --hidden-import vgamepad.win.vigem_commons `
    --exclude-module PIL `
    --exclude-module pystray `
    --exclude-module ssl `
    --exclude-module _ssl `
    --exclude-module hashlib `
    --exclude-module _hashlib `
    --exclude-module socket `
    --exclude-module _socket `
    --exclude-module vgamepad.lin `
    (Join-Path $root 'app\walk_tray.py')
$exe = Join-Path $root 'dist\KeepWalking.exe'
$size = [math]::Round((Get-Item $exe).Length / 1MB, 2)
Write-Host "Built $exe ($size MB)"
