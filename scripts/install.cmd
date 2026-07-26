@echo off
REM ============================================================================
REM OpenAmer Agent Installer for Windows (CMD wrapper)
REM ============================================================================
REM This batch file launches the PowerShell installer for users running CMD.
REM
REM Usage:
REM   curl -fsSL https://raw.githubusercontent.com/NousResearch/openamer-agent/main/scripts/install.cmd -o install.cmd && install.cmd && del install.cmd
REM
REM Or if you're already in PowerShell, use the direct command instead:
REM   iex (irm https://openamer-agent.nousresearch.com/install.ps1)
REM ============================================================================

echo.
echo  OpenAmer Agent Installer
echo  Launching PowerShell installer...
echo.

powershell -ExecutionPolicy ByPass -NoProfile -Command "iex (irm https://openamer-agent.nousresearch.com/install.ps1)"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  Installation failed. Please try running PowerShell directly:
    echo    powershell -ExecutionPolicy ByPass -c "iex (irm https://openamer-agent.nousresearch.com/install.ps1)"
    echo.
    pause
    exit /b 1
)
