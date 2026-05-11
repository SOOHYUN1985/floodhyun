@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ============================================================
echo   포지션 분석 리포트 자동 생성
echo ============================================================
echo.

cd /d "%~dp0"
set PYTHON=%~dp0venv\Scripts\python.exe

:: ─── 기존 파일 → archive 이동 ──────────────
set "OUT_DIR=results\daily_position"
set "ARCHIVE=results\archive\daily_position"
if not exist "%ARCHIVE%" mkdir "%ARCHIVE%"
if exist "%OUT_DIR%" (
    for %%f in ("%OUT_DIR%\*.*") do move /Y "%%f" "%ARCHIVE%" >nul 2>&1
    echo   [OK] 이전 결과 → archive\daily_position 이동 완료
    echo.
)

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
