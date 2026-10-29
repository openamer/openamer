@echo off
REM ---------------------------------------------------------------------------
REM OpenAmer OS -- hosted build of the kernel.
REM
REM The native kernel is freestanding x86_64 code: it is built with a cross
REM toolchain and linked into a bootable image. That toolchain is not present
REM on every machine, so this script builds the SAME sources as a hosted
REM userspace image with MSVC instead.
REM
REM That is not a compromise on the code: the sources are identical, and the
REM hosted build is what lets the kernel's logic -- the allocator, the
REM scheduler, the process table -- be exercised and tested on an ordinary
REM machine. The freestanding build is selected by defining nothing
REM (OPENAMER_HOSTED stays undefined); the hosted build defines it.
REM
REM Usage:  build_hosted.bat [output-dir]
REM ---------------------------------------------------------------------------
setlocal enabledelayedexpansion

REM The kernel root is the directory holding this script. It is normalized so
REM the source paths contain no "..\" segment (some tools mishandle that).
for %%i in ("%~dp0.") do set "KERNEL_ROOT=%%~fi"
set "KERNEL_SRC=%KERNEL_ROOT%\src"
set "KERNEL_INCLUDE=%KERNEL_ROOT%\include"
set "OUT_DIR=%~1"

if "%OUT_DIR%"=="" set "OUT_DIR=%KERNEL_ROOT%\build\hosted"

if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"

REM Locate MSVC. The VS installer path varies, so ask vswhere first and
REM fall back to the standard 2022 layout.
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
    echo [openamer] Install the "Desktop development with C++" workload,
    echo [openamer] or run this from a "Developer Command Prompt".
    exit /b 2
)

call "%VCVARS%" >nul || exit /b 2

pushd "%OUT_DIR%"

cl /nologo /c /W4 /WX ^
   /DOPENAMER_HOSTED=1 ^
   /I "%KERNEL_INCLUDE%" ^
   /Fo"%OUT_DIR%\\" ^
   "%KERNEL_SRC%\core.c" ^
   "%KERNEL_SRC%\memory.c" ^
   "%KERNEL_SRC%\interrupts.c" ^
   "%KERNEL_SRC%\scheduler.c" ^
   "%KERNEL_SRC%\ports.c" ^
   "%KERNEL_SRC%\display.c" ^
   "%KERNEL_SRC%\util.c" || (popd & exit /b 1)

lib /nologo /out:openamer_kernel.lib *.obj || (popd & exit /b 1)

echo [openamer] hosted kernel build OK -> %OUT_DIR%
popd
exit /b 0
