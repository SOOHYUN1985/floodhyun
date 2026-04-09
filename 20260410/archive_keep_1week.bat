@echo off
chcp 65001 >nul
echo ======================================================================
echo   Archive 정리 — 1주일(7일) 이전 파일 삭제
echo ======================================================================
echo.

cd /d "%~dp0"
set "PYTHON=%~dp0venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

"%PYTHON%" -c "
import os, time
base = 'results/archive'
cutoff = time.time() - 7*24*3600
n = 0
for root, dirs, files in os.walk(base):
    for f in files:
        fp = os.path.join(root, f)
        if os.path.getmtime(fp) < cutoff:
            os.remove(fp)
            n += 1
print(f'  {n}개 파일 삭제 (7일 이전)')
for root, dirs, files in os.walk(base, topdown=False):
    for d in dirs:
        dp = os.path.join(root, d)
        if not os.listdir(dp):
            os.rmdir(dp)
"

echo.
echo [OK] 완료
timeout /t 5
