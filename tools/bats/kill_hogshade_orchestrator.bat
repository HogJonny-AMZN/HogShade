@echo off
REM HogShade: emergency shutdown of a broken Job_Orchestrator (BATS), relative to this checkout.
REM Runs the orchestrator's own scripts\kill_orchestrator.py with its venv; the most reliable way to
REM clear an orphaned or wedged orchestrator, its tray app, pool monitor and every DCC worker it
REM spawned, before starting again with run_hogshade_orchestrator.bat.
REM
REM   set JOB_ORCHESTRATOR_ROOT=D:\Depot\Job_Orchestrator   (default)
REM   tools\bats\kill_hogshade_orchestrator.bat
REM
REM For a human at the keyboard. Besides the orchestrator's own processes, the script ends EVERY
REM maya.exe, mayapy.exe, houdini.exe and hython.exe on the machine by name, workers or not, so save
REM work in any open DCC first. An agent never runs it: an agent only stops processes it started.

setlocal
if "%JOB_ORCHESTRATOR_ROOT%"=="" set "JOB_ORCHESTRATOR_ROOT=D:\Depot\Job_Orchestrator"

if not exist "%JOB_ORCHESTRATOR_ROOT%\scripts\kill_orchestrator.py" (
    echo Job_Orchestrator not found at %JOB_ORCHESTRATOR_ROOT%; set JOB_ORCHESTRATOR_ROOT
    exit /b 1
)

echo HogShade: emergency shutdown of the Job_Orchestrator at %JOB_ORCHESTRATOR_ROOT%
echo This ends the orchestrator server, tray app, pool monitor, and EVERY Maya and Houdini process on this machine.
call "%JOB_ORCHESTRATOR_ROOT%\.venv\Scripts\Activate.bat"
python "%JOB_ORCHESTRATOR_ROOT%\scripts\kill_orchestrator.py"
set "RESULT=%ERRORLEVEL%"
echo.
echo Shutdown script finished with exit code %RESULT%. Start again with tools\bats\run_hogshade_orchestrator.bat
exit /b %RESULT%
