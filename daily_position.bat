@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ============================================================
echo   포지션 분석 리포트 자동 생성
echo ============================================================
echo.

set PYTHON=%~dp0venv\Scripts\python.exe

:: ─── 입력 받기 ──────────────────────────────
if "%~1"=="" (
    set /p NET="  순자산 (억, 예: 23.0): "
    set /p STOCK="  평가금액 (억, 예: 27.85): "
    set /p DATEARG="  기준일 (YYYYMMDD, 엔터=오늘): "
) else (
    set NET=%~1
    set STOCK=%~2
    set DATEARG=%~3
)

echo.

:: ─── 실행 ─────────────────────────────────
if "!DATEARG!"=="" (
    "%PYTHON%" "%~dp0position_report.py" --net !NET! --stock !STOCK!
) else (
    "%PYTHON%" "%~dp0position_report.py" --net !NET! --stock !STOCK! --date !DATEARG!
)

if %errorlevel% neq 0 (
    echo.
    echo [오류] 리포트 생성 실패!
    pause
    exit /b 1
)

echo.
pause
