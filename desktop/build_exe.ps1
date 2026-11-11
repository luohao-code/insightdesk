#requires -version 5.1
<#
.SYNOPSIS
    构建识文台 Windows 桌面版（单文件 exe）。

.DESCRIPTION
    1. 检查/安装 PyInstaller
    2. 生成应用图标
    3. 使用 desktop/insightdesk.spec 打包
    4. 输出到 dist/InsightDesk.exe 并复制到 release/
#>

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

Write-Host "[1/4] 检查 PyInstaller..." -ForegroundColor Cyan
& $Python -m PyInstaller --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "未检测到 PyInstaller，正在安装..." -ForegroundColor Yellow
    & $Python -m pip install pyinstaller
}

Write-Host "[2/4] 生成应用图标..." -ForegroundColor Cyan
& $Python scripts/make_icon.py

Write-Host "[3/4] 开始打包（首次构建可能需要数分钟）..." -ForegroundColor Cyan
& $Python -m PyInstaller desktop/insightdesk.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 打包失败"
}

Write-Host "[4/4] 复制产物..." -ForegroundColor Cyan
$Dist = Join-Path $Root "dist"
$Release = Join-Path $Root "release"
New-Item -ItemType Directory -Force -Path $Release | Out-Null
$Exe = Join-Path $Dist "InsightDesk.exe"
if (-not (Test-Path $Exe)) {
    throw "未找到打包产物：$Exe"
}
Copy-Item $Exe (Join-Path $Release "InsightDesk.exe") -Force

$Size = [math]::Round((Get-Item $Exe).Length / 1MB, 1)
Write-Host ""
Write-Host "构建完成：release\InsightDesk.exe（$Size MB）" -ForegroundColor Green
Write-Host "双击运行后会自动打开浏览器；数据保存在 %APPDATA%\InsightDesk\data" -ForegroundColor Gray
