@echo off
setlocal
if not defined STAGE1_WSL_DISTRO set "STAGE1_WSL_DISTRO=Ubuntu-24.04"
where wsl.exe >nul 2>nul
if errorlevel 1 (
  echo Install WSL2 Ubuntu-24.04 and Docker Desktop first. See START_HERE.md.
  pause
  exit /b 1
)
for /f "delims=" %%P in ('wsl.exe -d "%STAGE1_WSL_DISTRO%" --exec wslpath -u "%~dp0."') do set "LOCAL_STAGE1_PATH=%%P"
if not defined LOCAL_STAGE1_PATH (
  echo Ubuntu-24.04 unavailable. See START_HERE.md; no data was deleted.
  pause
  exit /b 1
)
wsl.exe -d "%STAGE1_WSL_DISTRO%" --exec bash "%LOCAL_STAGE1_PATH%/launcher/windows-to-wsl.sh" %*
pause
