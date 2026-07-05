@echo off
REM ============================================================
REM One-click boot launcher: starts BOTH tunnels after Windows reboot
REM   9090 (panel 8080)  - Blender work channel
REM   9091 (panel 8081)  - SFT training channel (agentpre)
REM Blender MCP (9876) is NOT started here: it needs Blender opened
REM   and the blender-mcp addon "Start" clicked manually first,
REM   then run: python start_blender.py --vps 49.233.189.223 --vps-pass <VPS_PASS>
REM
REM Usage:
REM   start_boot.bat [VPS_PASS] [PANEL_PASS]
REM   With no args, reads %~dp0boot_secrets.bat (NOT in git; create once):
REM       set VPS_PASS=xxx
REM       set PANEL_PASS=xxx
REM ============================================================
setlocal
set VPS=49.233.189.223

if not "%~1"=="" set VPS_PASS=%~1
if not "%~2"=="" set PANEL_PASS=%~2
if "%VPS_PASS%"=="" if exist "%~dp0boot_secrets.bat" call "%~dp0boot_secrets.bat"
if "%VPS_PASS%"=="" (
  echo [!] Missing password. Pass args or create %~dp0boot_secrets.bat
  exit /b 1
)
if "%PANEL_PASS%"=="" set PANEL_PASS=%VPS_PASS%

cd /d "%~dp0"

echo [1/2] starting Blender channel: panel 8080 - VPS:9090 ...
python start_all.py --vps %VPS% --vps-pass %VPS_PASS% --password %PANEL_PASS%

echo [2/2] starting training channel: panel 8081 - VPS:9091 ...
python start_all.py --vps %VPS% --vps-pass %VPS_PASS% --password %PANEL_PASS% --port 8081 --vps-port 9091

echo.
echo Done. Verify from the control machine:
echo   9090/9091 should be OPEN on %VPS%
echo (Blender MCP 9876 needs Blender + addon Start + start_blender.py, see README)
endlocal
