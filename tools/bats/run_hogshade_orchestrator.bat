@echo off
REM HogShade: start the Job_Orchestrator (BATS) dev checkout with HogShade's own profile:
REM one headless Maya, one GUI Maya (DirectX 11 override), one Python worker, plus the tray app.
REM
REM   set JOB_ORCHESTRATOR_ROOT=D:\Depot\Job_Orchestrator   (default)
REM   tools\bats\run_hogshade_orchestrator.bat [--tray-only|--orchestrator-only|--flush-logs]
REM
REM Stop any orchestrator already running first (its tray icon, or launchers\kill_orchestrator.bat in the
REM Job_Orchestrator checkout): two orchestrators on one port do not coexist.
REM
REM The orchestrator loads named profiles only from its own config folder, so this copies
REM tools\bats\orchestrator_config_hogshade.json there (a to-do on Job_Orchestrator: load a profile by path).

setlocal
if "%JOB_ORCHESTRATOR_ROOT%"=="" set "JOB_ORCHESTRATOR_ROOT=D:\Depot\Job_Orchestrator"
set "HOGSHADE_ROOT=%~dp0..\.."
for %%I in ("%HOGSHADE_ROOT%") do set "HOGSHADE_ROOT=%%~fI"

if not exist "%JOB_ORCHESTRATOR_ROOT%\launchers\run_orchestrator_ui.bat" (
    echo Job_Orchestrator not found at %JOB_ORCHESTRATOR_ROOT%; set JOB_ORCHESTRATOR_ROOT
    exit /b 1
)

copy /y "%HOGSHADE_ROOT%\tools\bats\orchestrator_config_hogshade.json" "%JOB_ORCHESTRATOR_ROOT%\job_orchestrator\config\orchestrator_config_hogshade.json" >nul
echo HogShade profile copied into the orchestrator config folder
echo HOGSHADE_ROOT=%HOGSHADE_ROOT%

call "%JOB_ORCHESTRATOR_ROOT%\launchers\run_orchestrator_ui.bat" --config hogshade %*
exit /b %ERRORLEVEL%
