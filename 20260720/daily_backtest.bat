@echo off
chcp 65001 >nul
echo ======================================================================
echo   MarketTop v2 - Daily Backtest
echo   %date% %time%
echo ======================================================================
echo.

cd /d "%~dp0"

REM venv의 python 직접 사용
set "PYTHON=%~dp0venv\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"
if not exist "%PYTHON%" (
    echo [WARNING] venv 없음, 시스템 python 사용
    set "PYTHON=python"
)

REM ─── 기존 파일 → archive 이동 ─────────────────────
set "OUT_DIR=results\daily_backtest"
set "ARCHIVE=results\archive\daily_backtest"
if not exist "%ARCHIVE%" mkdir "%ARCHIVE%"
if exist "%OUT_DIR%" (
    for %%f in ("%OUT_DIR%\*.*") do move /Y "%%f" "%ARCHIVE%" >nul 2>&1
    if exist "%OUT_DIR%\premium\*.*" (
        if not exist "%ARCHIVE%\premium" mkdir "%ARCHIVE%\premium"
        for %%f in ("%OUT_DIR%\premium\*.*") do move /Y "%%f" "%ARCHIVE%\premium" >nul 2>&1
    )
    echo [OK] 이전 결과 → archive\daily_backtest 이동 완료
    echo.
)

echo [1/5] DB 업데이트 중 (지수 + 종목)...
echo ----------------------------------------------------------------------
"%PYTHON%" update_market_data.py
if %errorlevel% neq 0 (
    echo [ERROR] DB 업데이트 실패
    pause
    exit /b 1
)
echo [OK] DB 업데이트 완료
echo.

echo [2/5] 코스피 밸류에이션 차트 생성 중...
echo ----------------------------------------------------------------------
"%PYTHON%" kospi_valuation_chart.py
if %errorlevel% neq 0 (
    echo [WARNING] 밸류에이션 차트 실패 - 계속 진행
)
echo [OK] 밸류에이션 차트 완료
echo.

echo [3/5] 코스피 + 코스닥 백테스트 실행 중...
echo ----------------------------------------------------------------------
"%PYTHON%" main.py --all
if %errorlevel% neq 0 (
    echo [ERROR] 백테스트 실패
    pause
    exit /b 1
)
echo [OK] 백테스트 완료
echo.

echo [4/5] 보통주/우선주 괴리율 통합 분석 중...
echo ----------------------------------------------------------------------
"%PYTHON%" premium_analyzer.py
if %errorlevel% neq 0 (
    echo [WARNING] 괴리율 분석 실패 - 계속 진행
)
echo [OK] 괴리율 분석 완료
echo.

echo [5/5] 리포트 열기...
echo ----------------------------------------------------------------------
"%PYTHON%" -c "import glob,os;files=sorted(glob.glob('results/daily_backtest/*_고점판독리포트_*.md'),key=os.path.getmtime);[print(f'  {os.path.basename(f)}') or os.startfile(f) for f in files[-2:]] if files else print('  [WARNING] 백테스트 리포트 없음')"
"%PYTHON%" -c "import glob,os;files=sorted(glob.glob('results/daily_backtest/일일종합_*.md'),key=os.path.getmtime);[print(f'  ★ {os.path.basename(f)}') or os.startfile(f) for f in files[-1:]] if files else print('  [WARNING] 종합 리포트 없음')"

echo.
echo ======================================================================
echo   완료! %date% %time%
echo ======================================================================
echo.

timeout /t 10
exit /b 0