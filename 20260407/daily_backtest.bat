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

echo [5/5] 48시간 이전 결과 정리 중...
echo ----------------------------------------------------------------------
"%PYTHON%" -c "import os,time;now=time.time();c=48*3600;n=0;dirs=['results/reports/premium','results/reports/backtest'];[(os.remove(os.path.join(d,f)),n:=n+1) for d in dirs if os.path.isdir(d) for f in os.listdir(d) if now-os.path.getmtime(os.path.join(d,f))>c];print(f'  {n}개 오래된 파일 정리')"
echo [OK] 정리 완료
echo.

echo 리포트 열기...
echo ----------------------------------------------------------------------
"%PYTHON%" -c "import glob,os;files=sorted(glob.glob('results/reports/backtest/*_고점판독리포트_*.md'),key=os.path.getmtime);[print(f'  {os.path.basename(f)}') or os.startfile(f) for f in files[-2:]] if files else print('  [WARNING] 백테스트 리포트 없음')"
"%PYTHON%" -c "import glob,os;files=sorted(glob.glob('results/reports/backtest/일일종합_*.md'),key=os.path.getmtime);[print(f'  ★ {os.path.basename(f)}') or os.startfile(f) for f in files[-1:]] if files else print('  [WARNING] 종합 리포트 없음')"

echo.
echo ======================================================================
echo   완료! %date% %time%
echo ======================================================================
echo.

timeout /t 10
exit /b 0