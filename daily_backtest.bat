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
if not exist "%PYTHON%" (
    echo [WARNING] venv 없음, 시스템 python 사용
    set "PYTHON=python"
)

echo [1/2] DB 업데이트 중...
echo ----------------------------------------------------------------------
"%PYTHON%" update_market_data.py
if %errorlevel% neq 0 (
    echo [ERROR] DB 업데이트 실패
    pause
    exit /b 1
)
echo [OK] DB 업데이트 완료
echo.

echo [2/2] 코스피 + 코스닥 백테스트 실행 중...
echo ----------------------------------------------------------------------
"%PYTHON%" main.py --all
if %errorlevel% neq 0 (
    echo [ERROR] 백테스트 실패
    pause
    exit /b 1
)
echo [OK] 백테스트 완료
echo.

echo 리포트 열기...
echo ----------------------------------------------------------------------
"%PYTHON%" -c "import glob,os;files=sorted(glob.glob('results/reports/*_고점판독리포트_*.md'),key=os.path.getmtime);[print(f'  {os.path.basename(f)}') or os.startfile(f) for f in files[-2:]] if files else print('  [WARNING] 리포트 없음')"

echo.
echo ======================================================================
echo   완료! %date% %time%
echo ======================================================================
echo.

timeout /t 10
exit /b 0