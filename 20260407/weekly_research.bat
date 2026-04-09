@echo off
chcp 65001 >nul
echo ======================================================================
echo   MarketTop v2 - Weekly Research
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

echo [1/8] 명절 효과 분석 (전체 기간)...
echo ----------------------------------------------------------------------
"%PYTHON%" holiday_effect_analyzer.py
if %errorlevel% neq 0 (
    echo [WARNING] 명절 효과 분석 실패 - 계속 진행
)
echo [OK] 명절 효과 분석 완료
echo.

echo [2/8] 명절 효과 분석 ^(2010년 이후^)...
echo ----------------------------------------------------------------------
"%PYTHON%" holiday_effect_analyzer.py 2010
if %errorlevel% neq 0 (
    echo [WARNING] 명절 효과 분석 2010+ 실패 - 계속 진행
)
echo [OK] 명절 효과 분석 (2010+) 완료
echo.

echo [3/8] 연말연초 효과 분석...
echo ----------------------------------------------------------------------
"%PYTHON%" yearend_effect_analyzer.py
if %errorlevel% neq 0 (
    echo [WARNING] 연말연초 효과 분석 실패 - 계속 진행
)
echo [OK] 연말연초 효과 분석 완료
echo.

echo [4/8] 외국인 순매도 Top20 분석 (네이버 스크래핑)...
echo ----------------------------------------------------------------------
"%PYTHON%" foreign_selling_analyzer.py
if %errorlevel% neq 0 (
    echo [WARNING] 외국인 순매도 분석 실패 - 계속 진행
)
echo [OK] 외국인 순매도 분석 완료
echo.

echo [5/8] 외국인 순매도 심층 분석...
echo ----------------------------------------------------------------------
"%PYTHON%" foreign_selling_deep_analysis.py
if %errorlevel% neq 0 (
    echo [WARNING] 외국인 심층 분석 실패 - 계속 진행
)
echo [OK] 외국인 심층 분석 완료
echo.

echo [6/8] 담보비율 시뮬레이션...
echo ----------------------------------------------------------------------
"%PYTHON%" margin_calculator.py
if %errorlevel% neq 0 (
    echo [WARNING] 담보비율 시뮬레이션 실패 - 계속 진행
)
echo [OK] 담보비율 시뮬레이션 완료
echo.

echo [7/8] 반도체 밸류에이션 분석...
echo ----------------------------------------------------------------------
"%PYTHON%" stock_valuation_report.py
if %errorlevel% neq 0 (
    echo [WARNING] 반도체 밸류에이션 실패 - 계속 진행
)
echo [OK] 반도체 밸류에이션 완료
echo.

echo [8/8] 코스피/코스닥 추세 + MDD 차트 생성...
echo ----------------------------------------------------------------------
"%PYTHON%" visualize_charts.py
if %errorlevel% neq 0 (
    echo [WARNING] 추세/MDD 차트 생성 실패 - 계속 진행
)
echo [OK] 추세/MDD 차트 생성 완료
echo.

echo 리포트 열기...
echo ----------------------------------------------------------------------
"%PYTHON%" -c "import glob,os;patterns=['results/analysis/명절효과_분석_*.md','results/analysis/연말연초_효과_분석_*.md','results/analysis/외국인_순매도_심층분석_*.md','results/analysis/담보대출_전략_*.md','results/analysis/반도체_밸류에이션_분석_*.md'];[print(f'  {os.path.basename(f)}') or os.startfile(f) for p in patterns for f in sorted(glob.glob(p),key=os.path.getmtime)[-1:]]"

echo.
echo ======================================================================
echo   완료! %date% %time%
echo   결과 폴더: results\analysis\
echo ======================================================================
echo.

timeout /t 10
exit /b 0
