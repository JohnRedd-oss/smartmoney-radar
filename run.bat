@echo off
REM 聪明钱雷达 · 每日运行（cmd 版，绕过 PowerShell 执行策略限制）
REM 用法: run.bat                默认跳过 land 源
REM       run.bat all            全量
REM       run.bat 13f,land       跳过指定源
REM       run.bat -              不跳过任何源

setlocal enabledelayedexpansion
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

set SKIP=land
if /i "%~1"=="all" set SKIP=
if "%~1"=="-" set SKIP=
if "%~1"=="" goto :runit
if /i not "%~1"=="all" if not "%~1"=="-" set SKIP=%~1

:runit
echo [%date% %time%] 聪明钱雷达启动 (skip=%SKIP%)

if not exist reports mkdir reports
for /f "tokens=1-3 delims=/ " %%a in ("%date%") do set D=%%a%%b%%c

python -m smartmoney.cli run --skip=%SKIP% --out=reports\report-%D%.md
if errorlevel 1 (
    echo 运行失败 exit=%errorlevel%
    exit /b %errorlevel%
)

echo 完成: reports\report-%D%.md
endlocal
