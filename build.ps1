$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$out = Join-Path $root 'build\Keep-Walking-Addon-v1.zip'
New-Item -ItemType Directory -Force -Path (Join-Path $root 'build') | Out-Null
Push-Location (Join-Path $root 'scripts')
try {
    python -B build_addon.py `
        --name mods/bass/keep_walking `
        --entry (Join-Path $root 'src\keep_walking.lua') `
        --guid 7d2f1b84-6e3a-4c91-9b50-2f8e0c4a91d6 `
        --display-name 'Keep Walking Addon' `
        --description-file (Join-Path $root 'description.txt') `
        --thumbnail (Join-Path $root 'thumbnail.png') `
        --output $out
} finally {
    Pop-Location
}
Write-Host "Built $out"
