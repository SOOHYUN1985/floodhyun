@echo off
chcp 65001 >nul

cd /d "%~dp0"

set "PYTHON=%~dp0venv\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"

if not exist "%PYTHON%" (
    set "PYTHON=python"
)

if not "%~1"=="" (
    set "QUERY=%~1"
    goto :run
)

echo.
echo ======================================================================
echo   Stock Analysis - Target Price Consensus Report
echo   %date% %time%
echo ======================================================================
echo.
echo   Usage: stock_analysis.bat [stock name or 6-digit code]
echo   Ex)  : stock_analysis.bat 005380
echo          stock_analysis.bat 005930
echo.
echo ======================================================================
echo.
set /p QUERY=Enter stock name or code: 
if "%QUERY%"=="" (
    echo [ERROR] No input provided.
    pause
    exit /b 1
)

:run
echo.
echo ----------------------------------------------------------------------
"%PYTHON%" stock_consensus_report.py "%QUERY%"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Report generation failed.
    pause
) else (
    echo.
    echo ======================================================================
    echo   Done! Output folder: results\weekly_research\
    echo ======================================================================
    timeout /t 5
)

exit /b 0