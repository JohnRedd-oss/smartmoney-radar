# 聪明钱雷达 · 每日运行
# 用法：.\run.ps1               全量（默认跳过不稳定源 land）
#       .\run.ps1 -Skip ""      不跳过任何源
#       .\run.ps1 -Skip 13f     跳过指定源（逗号分隔）
#
# 若被执行策略拦截，改用：powershell -ExecutionPolicy Bypass -File .\run.ps1

param(
    [string]$Skip = "land"
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$env:PYTHONIOENCODING = "utf-8"
Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] 聪明钱雷达启动" -ForegroundColor Cyan

if (-not (Test-Path reports)) { New-Item -ItemType Directory -Path reports | Out-Null }
$stamp = Get-Date -Format "yyyyMMdd"
$out = Join-Path $here "reports\report-$stamp.md"

if ($Skip) {
    python -m smartmoney.cli run --skip=$Skip --out=$out
} else {
    python -m smartmoney.cli run --out=$out
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "运行失败 exit=$LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}
Write-Host "日报已存: $out" -ForegroundColor Green
