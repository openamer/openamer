@echo off
REM ---------------------------------------------------------------------------
REM OpenAmer OS -- build and run the hosted kernel tests.
REM
REM Compiles the kernel sources plus the test harness with MSVC and runs
REM the result. The exit code is the number of failed checks, so CI can
REM gate on it directly.
REM
REM Usage:  run_tests.bat
REM ---------------------------------------------------------------------------
setlocal enabledelayedexpansion

set "KERNEL_ROOT=%~dp0."
set "KERNEL_SRC=%KERNEL_ROOT%\src"
set "KERNEL_INCLUDE=%KERNEL_ROOT%\include"
set "KERNEL_TESTS=%KERNEL_ROOT%\tests"
set "OUT_DIR=%KERNEL_ROOT%\build\hosted"

if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"

set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
set "VCVARS="
if exist "%VSWHERE%" (
    for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -latest -products * ^
        -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 ^
        -property installationPath`) do (
            set "VSPATH=%%i"
        )
    if defined VSPATH (
        if exist "!VSPATH!\VC\Auxiliary\Build\vcvars64.bat" (
            set "VCVARS=!VSPATH!\VC\Auxiliary\Build\vcvars64.bat"
        )
    )
)
if not defined VCVARS (
    if exist "%ProgramFiles%\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" (
        set "VCVARS=%ProgramFiles%\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
    )
)
if not defined VCVARS (
    echo [openamer] ERROR: no MSVC toolchain found.
    exit /b 2
)

call "%VCVARS%" >nul || exit /b 2

pushd "%OUT_DIR%"

cl /nologo /W4 /WX ^
   /DOPENAMER_HOSTED=1 ^
   /I "%KERNEL_INCLUDE%" ^
   /Fo"%OUT_DIR%\\" ^
   "%KERNEL_SRC%\core.c" ^
   "%KERNEL_SRC%\memory.c" ^
   "%KERNEL_SRC%\interrupts.c" ^
   "%KERNEL_SRC%\scheduler.c" ^
   "%KERNEL_SRC%\ports.c" ^
   "%KERNEL_SRC%\display.c" ^
   "%KERNEL_SRC%\util.c" ^
   "%KERNEL_TESTS%\kernel_tests.c" ^
   /Fe"%OUT_DIR%\openamer_kernel_tests.exe" || (popd & exit /b 1)

popd

"%OUT_DIR%\openamer_kernel_tests.exe"
set "RESULT=%ERRORLEVEL%"

if not "%RESULT%"=="0" (
    echo [openamer] kernel tests FAILED: %RESULT% checks failed.
    exit /b %RESULT%
)

echo [openamer] kernel tests passed.
exit /b 0
