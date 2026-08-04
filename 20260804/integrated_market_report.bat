@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHON=%~dp0venv\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"
if not exist "%PYTHON%" set "PYTHON=python"

echo ======================================================================
echo   MarketTop v2 - Integrated Market Action Guide
echo ======================================================================
echo.

echo [1/3] 일일 백테스트 실행 중...
call "%~dp0daily_backtest.bat"
if errorlevel 1 exit /b 1

echo [2/3] 주간 리서치 실행 중...
call "%~dp0weekly_research.bat"
if errorlevel 1 exit /b 1

echo [3/3] 코스피/코스닥 통합 매매 가이드 생성 중...
"%PYTHON%" market_action_report.py
if errorlevel 1 (
    echo [ERROR] 통합 매매 가이드 생성 실패
    pause
    exit /b 1
)

"%PYTHON%" -c "import glob,os; files=sorted(glob.glob('results/daily_backtest/통합_매매실행가이드_*.md'), key=os.path.getmtime); os.startfile(files[-1]) if files else print('[WARNING] 가이드 없음')"
echo.
echo 완료! 결과: results\daily_backtest\통합_매매실행가이드_*.md
pause