@echo off
setlocal EnableExtensions

set "PROJECT_DIR=%~dp0"
set "VENV_DIR=%PROJECT_DIR%venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "PIP_EXE=%VENV_DIR%\Scripts\pip.exe"
set "REQUIREMENTS_FILE=%PROJECT_DIR%requirements.txt"

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found on PATH.
    exit /b 1
)

if not exist "%PYTHON_EXE%" (
    echo Creating virtual environment...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 exit /b 1
)

"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 exit /b 1

"%PIP_EXE%" install -r "%REQUIREMENTS_FILE%"
if errorlevel 1 exit /b 1

call :RefreshMkvToolNixPath

where ffmpeg >nul 2>nul
if errorlevel 1 call :InstallPackage "ffmpeg" "Gyan.FFmpeg" "ffmpeg"
if errorlevel 1 exit /b 1

where ffprobe >nul 2>nul
if errorlevel 1 call :InstallPackage "ffmpeg" "Gyan.FFmpeg" "ffmpeg"
if errorlevel 1 exit /b 1

set "MKVTOOLNIX_MISSING="
where mkvpropedit >nul 2>nul
if errorlevel 1 set "MKVTOOLNIX_MISSING=1"
where mkvmerge >nul 2>nul
if errorlevel 1 set "MKVTOOLNIX_MISSING=1"
where mkvextract >nul 2>nul
if errorlevel 1 set "MKVTOOLNIX_MISSING=1"
if defined MKVTOOLNIX_MISSING call :InstallPackage "mkvtoolnix" "MoritzBunkus.MKVToolNix" "mkvtoolnix"
if errorlevel 1 exit /b 1

call :RefreshMkvToolNixPath
call :PersistMkvToolNixPath
if errorlevel 1 exit /b 1
call :RefreshMkvToolNixPath

where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo ffmpeg could not be resolved after installation.
    exit /b 1
)

where ffprobe >nul 2>nul
if errorlevel 1 (
    echo ffprobe could not be resolved after installation.
    exit /b 1
)

where mkvpropedit >nul 2>nul
if errorlevel 1 (
    echo mkvpropedit could not be resolved after installation.
    exit /b 1
)

where mkvmerge >nul 2>nul
if errorlevel 1 (
    echo mkvmerge could not be resolved after installation.
    exit /b 1
)

where mkvextract >nul 2>nul
if errorlevel 1 (
    echo mkvextract could not be resolved after installation.
    exit /b 1
)

ffmpeg -version >nul 2>nul
if errorlevel 1 exit /b 1

ffprobe -version >nul 2>nul
if errorlevel 1 exit /b 1

mkvpropedit --version >nul 2>nul
if errorlevel 1 exit /b 1

mkvmerge --version >nul 2>nul
if errorlevel 1 exit /b 1

mkvextract --version >nul 2>nul
if errorlevel 1 exit /b 1

echo Installation complete.
exit /b 0

:InstallPackage
set "CHOCO_PACKAGE=%~1"
set "WINGET_PACKAGE=%~2"
set "DISPLAY_NAME=%~3"

where choco >nul 2>nul
if not errorlevel 1 (
    echo Installing %DISPLAY_NAME% with Chocolatey...
    choco install "%CHOCO_PACKAGE%" -y
    exit /b %ERRORLEVEL%
)

where winget >nul 2>nul
if not errorlevel 1 (
    echo Installing %DISPLAY_NAME% with winget...
    winget install --id "%WINGET_PACKAGE%" --exact --accept-package-agreements --accept-source-agreements
    exit /b %ERRORLEVEL%
)

echo Neither Chocolatey nor winget was found. Install one package manager or install %DISPLAY_NAME% manually.
exit /b 1

:RefreshMkvToolNixPath
if exist "%ProgramFiles%\MKVToolNix\mkvpropedit.exe" set "PATH=%ProgramFiles%\MKVToolNix;%PATH%"
if not "%ProgramFiles(x86)%"=="" if exist "%ProgramFiles(x86)%\MKVToolNix\mkvpropedit.exe" set "PATH=%ProgramFiles(x86)%\MKVToolNix;%PATH%"
exit /b 0

:PersistMkvToolNixPath
set "MKVTOOLNIX_DIR="
if exist "%ProgramFiles%\MKVToolNix\mkvpropedit.exe" set "MKVTOOLNIX_DIR=%ProgramFiles%\MKVToolNix"
if "%MKVTOOLNIX_DIR%"=="" if not "%ProgramFiles(x86)%"=="" if exist "%ProgramFiles(x86)%\MKVToolNix\mkvpropedit.exe" set "MKVTOOLNIX_DIR=%ProgramFiles(x86)%\MKVToolNix"
if "%MKVTOOLNIX_DIR%"=="" exit /b 0
set "USER_PATH="
for /f "tokens=2,*" %%A in ('reg query HKCU\Environment /v Path 2^>nul') do set "USER_PATH=%%B"
echo ;%USER_PATH%; | find /I ";%MKVTOOLNIX_DIR%;" >nul
if not errorlevel 1 exit /b 0
if "%USER_PATH%"=="" (
    reg add HKCU\Environment /v Path /t REG_EXPAND_SZ /d "%MKVTOOLNIX_DIR%" /f >nul
) else (
    reg add HKCU\Environment /v Path /t REG_EXPAND_SZ /d "%USER_PATH%;%MKVTOOLNIX_DIR%" /f >nul
)
exit /b %ERRORLEVEL%
