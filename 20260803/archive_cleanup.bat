@echo off
chcp 65001 >nul
echo ======================================================================
echo   Archive 정리 도구
echo ======================================================================
echo.
echo   [1] 최근 5회분만 보관  (권장)
echo   [2] 7일 이전 파일 삭제
echo   [3] 30일 이전 파일 삭제
echo.

cd /d "%~dp0"
set "PYTHON=%~dp0venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

set /p CHOICE="  선택 (1/2/3): "

if "%CHOICE%"=="1" goto KEEP_5
if "%CHOICE%"=="2" goto KEEP_1WEEK
if "%CHOICE%"=="3" goto KEEP_1MONTH
echo [ERROR] 잘못된 선택
pause
exit /b 1

:KEEP_5
echo.
echo   최근 5회분만 보관합니다...
"%PYTHON%" archive_cleanup.py 1
goto DONE

:KEEP_1WEEK
echo.
echo   7일 이전 파일을 삭제합니다...
"%PYTHON%" archive_cleanup.py 2
goto DONE

:KEEP_1MONTH
echo.
echo   30일 이전 파일을 삭제합니다...
"%PYTHON%" archive_cleanup.py 3
goto DONE

:DONE
echo.
echo   정리 완료!
echo.
pause
