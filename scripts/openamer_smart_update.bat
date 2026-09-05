@echo off
echo ==========================================
echo   OpenAmer Smart Update
echo   Automatically handles running app
echo ==========================================
echo.

echo [1/4] Closing Desktop App...
taskkill /IM OpenAmer.exe 2>nul
timeout /t 3 /nobreak >nul

echo [2/4] Killing leftover processes...
taskkill /F /IM OpenAmer.exe 2>nul
timeout /t 2 /nobreak >nul

echo [3/4] Running update...
call openamer update --force --yes
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Update had issues. Check output above.
)

echo [4/4] Restarting Desktop App...
start "" "C:\Users\damir\AppData\Local\openamer-laptop\openamer-agent\apps\desktop\OpenAmer.exe" 2>nul
if %errorlevel% neq 0 (
    echo [INFO] Please start the Desktop App manually.
)

echo.
echo ==========================================
echo   Update complete!
echo ==========================================
pause
