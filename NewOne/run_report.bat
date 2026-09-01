@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title 시장 국면·유사구간 기반 주식비중 리포트

rem ── 실행 파이썬 선택: 로컬 venv → Test venv → 시스템 python ──
set "NEWDIR=%~dp0"
set "PY=%NEWDIR%venv\Scripts\python.exe"
if not exist "%PY%" set "PY=C:\FREE\gitTest\Test\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

cd /d "%NEWDIR%"

echo ============================================================
echo   시장 국면 - 유사구간 기반 적정 주식비중 리포트
echo   (DB: %NEWDIR%data)
echo ============================================================
echo.

rem ── [1/2] 프로젝트 내부 DB 최신 업데이트 ──
echo [1/2] DB 최신 업데이트 중... (네트워크 필요, 1~2분)
"%PY%" update_data.py
if errorlevel 1 (
    echo.
    echo [경고] DB 업데이트에 실패했습니다. 기존 DB로 분석을 계속합니다.
    echo.
)

rem ── [2/2] 분석 + 백테스트 + 리포트 생성 및 열기 ──
echo.
echo [2/2] 시장 분석 - 유사구간 - 백테스트 - 리포트 생성 중... (약 30초)
"%PY%" main.py --open
if errorlevel 1 (
    echo.
    echo [오류] 분석에 실패했습니다. 위 메시지를 확인하세요.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   완료. HTML 리포트가 브라우저에 열렸습니다.
echo   결과 폴더: %NEWDIR%results\
echo ============================================================
echo.
pause
endlocal
