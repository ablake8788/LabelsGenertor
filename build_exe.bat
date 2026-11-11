@echo off
setlocal
rem ======================================================================
rem  LabelGenerator - FULL REBUILD
rem   1. close the running app
rem   2. create .venv (Dropbox told to ignore .venv and build)
rem   3. install packages
rem   4. run all unit tests               -> stops if any test fails
rem   5. build dist\LabelGenerator.exe
rem   6. run the built .exe self-test     -> stops if it fails
rem   7. check the database connection    -> warning only (read-only)
rem ======================================================================
cd /d "%~dp0"
set PY=.venv\Scripts\python.exe

echo [1/7] Closing LabelGenerator if it is running...
taskkill /IM LabelGenerator.exe /F >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2/7] Python environment...
if not exist ".venv" mkdir ".venv"
if not exist "build" mkdir "build"
powershell -NoProfile -Command "Set-Content -Path '.venv' -Stream com.dropbox.ignored -Value 1; Set-Content -Path 'build' -Stream com.dropbox.ignored -Value 1"
if not exist "%PY%" (
    python -m venv .venv
    if errorlevel 1 goto fail
)

echo [3/7] Installing packages...
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 goto fail

echo [4/7] Running unit tests...
"%PY%" -m unittest discover -s tests -t . -v
if errorlevel 1 (
    echo TESTS FAILED - the .exe was NOT built.
    goto fail
)

echo [5/7] Building dist\LabelGenerator.exe ...
"%PY%" -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name LabelGenerator --hidden-import pyodbc --collect-submodules labelgen --distpath dist label_app.py
if errorlevel 1 goto fail
if not exist "dist\config.ini" copy "config.ini" "dist\config.ini" >nul

echo [6/7] Self-test of the built .exe ...
start "" /wait "dist\LabelGenerator.exe" --selftest
set RC=%errorlevel%
type "dist\selftest.log"
if not "%RC%"=="0" (
    echo EXE SELF-TEST FAILED.
    goto fail
)

echo [7/7] Database connection check (read-only, nothing is written)...
start "" /wait "dist\LabelGenerator.exe" --check-db
set DBRC=%errorlevel%
type "dist\selftest.log"

echo.
echo ======================================================================
echo  BUILD OK:  %~dp0dist\LabelGenerator.exe
if not "%DBRC%"=="0" echo  WARNING:   database check failed - see dist\selftest.log and dist\config.ini
echo ======================================================================
pause
exit /b 0

:fail
echo.
echo BUILD FAILED - see the messages above.
pause
exit /b 1
