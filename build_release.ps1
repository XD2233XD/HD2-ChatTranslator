# Build the distributable package with author watermark + ed25519 signature.
#   pwsh -File build_release.ps1 -Version 1.0.0
param([string]$Version = "1.0.0")

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Py = "E:\Python312\python.exe"
$PillowPy = "C:\Users\Windows\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if (-not (Test-Path $Py)) { throw "python not found: $Py" }
if (-not (Test-Path $PillowPy)) { throw "Pillow python not found: $PillowPy" }

$Brand = Get-Content "$Root\branding.json" -Raw | ConvertFrom-Json
$Author = $Brand.author
$Wid = $Brand.watermark_id
Write-Host "author=$Author  watermark=$Wid"

Write-Host "== 1/5 icon watermark =="
& $PillowPy "$Root\assets\_icon.py"

Write-Host "== 2/5 Lua compile check =="
& $Py "$Root\mod\tools\lua_syntax_check.py" "$Root\mod\src\chat_translator.lua"
if ($LASTEXITCODE -ne 0) { throw "Lua compile failed" }

Write-Host "== 3/5 Arsenal mod ZIP =="
& $Py "$Root\mod\tools\pack_addon.py" `
  --src "$Root\mod\src\chat_translator.lua" `
  --path "mods/hd2ct/chat_translator" `
  --name "HD2 Chat Translator" `
  --guid "2dc3c7ca-4cdd-4cb1-b488-85dd9db483b3" `
  --version $Version `
  --delivery "HD2ChatTranslator" `
  --author $Author `
  --watermark $Wid `
  --dist "$Root\mod\dist"
if ($LASTEXITCODE -ne 0) { throw "pack_addon failed" }

Write-Host "== 4/5 console EXE (PyInstaller onedir/windowed) =="
Push-Location "$Root\console"
& $Py -m PyInstaller --noconfirm --clean --onedir --windowed `
  --name "HD2ChatTranslator" `
  --icon "$Root\assets\icon.ico" `
  --add-data "web;web" `
  --hidden-import ime_guard --hidden-import installer --hidden-import paths --hidden-import branding `
  app.py
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "PyInstaller failed" }
Pop-Location

Write-Host "== 5/5 assemble + watermark + sign + zip =="
$Out = "$Root\release\HD2ChatTranslator-$Version"
if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path $Out, "$Out\mod", "$Out\loader" | Out-Null
Copy-Item "$Root\console\dist\HD2ChatTranslator\*" $Out -Recurse -Force
Copy-Item "$Root\mod\dist\HD2ChatTranslator-$Version.zip" "$Out\mod\" -Force
Copy-Item "$Root\mod\vendor\Bingus-Shared-Loader-v20.zip" "$Out\loader\" -Force
Copy-Item "$Root\release\使用说明.txt" "$Out\" -Force
Copy-Item "$Root\LICENSE", "$Root\NOTICE.md", "$Root\README.md", "$Root\assets\icon.png", "$Root\branding.json" $Out -Force
Remove-Item -Recurse -Force "$Out\data" -ErrorAction SilentlyContinue

$Zip = "$Root\release\HD2ChatTranslator-$Version-win64.zip"
& $Py "$Root\tools\watermark.py" `
  --folder $Out `
  --version $Version `
  --author $Author `
  --watermark-id $Wid `
  --key "$Root\keys\hd2ct_ed25519" `
  --out $Zip
if ($LASTEXITCODE -ne 0) { throw "watermark/sign failed" }

Get-Content "$Root\release\SHA256SUMS.txt"
Write-Host ""
Write-Host "done: $Zip"
