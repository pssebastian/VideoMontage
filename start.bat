@echo off
setlocal
title VideoMontage Launcher

cd /d "%~dp0"

echo ===================================================
echo               VideoMontage Studio
echo ===================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [!] Virtual environment not found. Setting up...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    python -m pip install -r requirements.txt piper-tts
) else (
    call .venv\Scripts\activate.bat
)

:MENU
echo Choose an option to open:
echo.
echo  [1] Open Web Dashboard
echo  [2] Open Remotion Studio ^(Visual Video Player / Previewer^)
echo  [3] Run Dashboard Live Simulation Demo
echo  [4] Render Built-in Demo Video ^(code-to-screen^)
echo  [5] Run VideoMontage MCP Server ^(SSE mode on port 8000^)
echo  [6] Open Interactive Python Shell
echo  [7] Exit
echo.
set /p CHOICE="Enter choice (1-7) [Default: 1]: "

if "%CHOICE%"=="" set CHOICE=1
if "%CHOICE%"=="1" goto DASHBOARD
if "%CHOICE%"=="2" goto REMOTION
if "%CHOICE%"=="3" goto SIMULATION
if "%CHOICE%"=="4" goto RENDER_DEMO
if "%CHOICE%"=="5" goto MCP_SERVER
if "%CHOICE%"=="6" goto SHELL
if "%CHOICE%"=="7" goto EXIT

echo [!] Invalid choice. Please try again.
echo.
goto MENU

:DASHBOARD
echo.
echo [*] Launching Web Dashboard and opening your browser...
python -m backlot open
pause
goto MENU

:REMOTION
echo.
echo [*] Launching Remotion Studio on http://localhost:3000 ...
cd remotion-composer
start http://localhost:3000
npm start
cd ..
goto MENU

:SIMULATION
echo.
echo [*] Running dashboard simulation demo...
python scripts/backlot_simulate_run.py
echo.
echo [*] Opening dashboard for simulated run...
python -m backlot open backlot-demo-run
pause
goto MENU

:RENDER_DEMO
echo.
echo [*] Rendering code-to-screen demo...
python render_demo.py code-to-screen
echo.
pause
goto MENU

:MCP_SERVER
echo.
echo [*] Starting VideoMontage MCP Server over SSE (port 8000)...
python -m mcp_server --transport sse --port 8000
pause
goto MENU

:SHELL
echo.
echo [*] Starting Python shell with VideoMontage environment...
python
goto MENU

:EXIT
echo Exiting VideoMontage. Goodbye!
exit /b 0
