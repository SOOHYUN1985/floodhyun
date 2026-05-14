@echo off
REM AutoTradingTest 빌드 스크립트 (Visual Studio MSBuild)
setlocal
cd /d "%~dp0"

set SOLUTION=AutoTradingTest.sln
set MSBUILD=C:\Program Files\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe

if not exist "%MSBUILD%" (
    echo MSBuild.exe를 찾을 수 없습니다.
    echo 경로: %MSBUILD%
    pause
    exit /b 1
)

echo [빌드 시작] %SOLUTION% - Release

REM 실행 중인 AutoTradingTest 프로세스 종료
tasklist /FI "IMAGENAME eq AutoTradingTest.exe" 2>NUL | find /I "AutoTradingTest.exe" >NUL
if %ERRORLEVEL%==0 (
    echo [주의] AutoTradingTest.exe 실행 중 - 종료합니다...
    taskkill /F /IM AutoTradingTest.exe >NUL 2>&1
    timeout /t 2 /nobreak >NUL
)

"%MSBUILD%" %SOLUTION% /p:Configuration=Release /m /nologo
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ 빌드 실패! ]
    pause
    exit /b %ERRORLEVEL%
)
echo.
echo [ 빌드 성공! ] bin\Release\AutoTradingTest.exe
pause
