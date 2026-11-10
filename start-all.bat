@echo off
chcp 65001 >nul
setlocal EnableExtensions
title Anti-Fraud Launcher

REM ============================================================
REM  Anti-Fraud System - local launcher (Redis started by you)
REM
REM  double click        -> open 4 console windows
REM  start-all.bat stop  -> stop all services by port
REM ============================================================

REM ============== CONFIG (only edit here) ==============
set "ROOT=C:\Users\BQY\Desktop\AIfanzhapian\ai_-anti_fraud_-software-master"
set "AGENT_SERVICE_TOKEN=dev-local-token-1234567890abcdef"
set "DB_PASSWORD=SWJ811018"
set "DB_HOST=localhost"
set "DB_PORT=3306"
set "DB_NAME=anti_fraud"
set "REDIS_HOST=127.0.0.1"
set "REDIS_PORT=6379"
set "JWT_SECRET=local-dev-jwt-secret-please-change"
REM =====================================================

set "AI_SERVICE_URL=http://localhost:5000"
set "AGENT_SERVICE_URL=http://localhost:8001"
set "MCP_SERVICE_URL=http://127.0.0.1:8001"
set "BACKEND_EVENT_URL=http://localhost:9090/internal/agent/v1/runs"
set "CHECKPOINT_DB_PATH=data/agent-checkpoints.sqlite"

if /i "%~1"=="stop" goto STOP_ALL

echo ============================================================
echo   Anti-Fraud System - local launcher
echo ============================================================
echo.

if not exist "%ROOT%" goto NO_ROOT

where python >nul 2>&1
if errorlevel 1 goto NO_PYTHON

where node >nul 2>&1
if errorlevel 1 goto NO_NODE

set "MVN_OK=1"
where mvn >nul 2>&1
if errorlevel 1 set "MVN_OK=0"

echo [check] python / node  OK
if "%MVN_OK%"=="0" echo [warn]  mvn not found, backend will be skipped

call :PORT_CHECK 6379
if errorlevel 1 (
    echo [warn]  Redis 6379 is not listening, please start Redis first
)

call :PORT_CHECK 3306
if errorlevel 1 (
    echo [warn]  MySQL 3306 is not listening, please start MySQL first
)

echo.
echo ---------- launching ----------
echo.

call :PORT_CHECK 5000
if not errorlevel 1 goto SKIP_AI
echo [1/4] AI service      :5000
start "AI-Service :5000" /D "%ROOT%\ai-service" cmd /k "python app.py"
call :WAIT_PORT 5000 45
goto AI_DONE
:SKIP_AI
echo [1/4] AI service      :5000 already running, skip
:AI_DONE

call :PORT_CHECK 8001
if not errorlevel 1 goto SKIP_AGENT
echo [2/4] Agent service   :8001  (minimized)
set "PYEXE=python"
if exist "%ROOT%\agent-service\.venv\Scripts\python.exe" set "PYEXE=.venv\Scripts\python.exe"
start "Agent-Service :8001" /MIN /D "%ROOT%\agent-service" cmd /k "%PYEXE% -m uvicorn agent_service.main:app --host 127.0.0.1 --port 8001"
call :WAIT_PORT 8001 60
goto AGENT_DONE
:SKIP_AGENT
echo [2/4] Agent service   :8001 already running, skip
:AGENT_DONE

call :PORT_CHECK 9090
if not errorlevel 1 goto SKIP_BACKEND
if "%MVN_OK%"=="0" goto SKIP_BACKEND
echo [3/4] Backend         :9090
start "Backend :9090" /D "%ROOT%\backend" cmd /k "mvn spring-boot:run"
call :WAIT_PORT 9090 150
goto BACKEND_DONE
:SKIP_BACKEND
echo [3/4] Backend         :9090 skipped
:BACKEND_DONE

call :PORT_CHECK 5173
if not errorlevel 1 goto SKIP_FRONT
if exist "%ROOT%\frontend\node_modules" (
    echo [4/4] Frontend        :5173
    start "Frontend :5173" /D "%ROOT%\frontend" cmd /k "npm run dev"
) else (
    echo [4/4] Frontend        :5173  first run, npm install needed
    start "Frontend :5173" /D "%ROOT%\frontend" cmd /k "npm install && npm run dev"
)
goto FRONT_DONE
:SKIP_FRONT
echo [4/4] Frontend        :5173 already running, skip
:FRONT_DONE

echo.
echo ============================================================
echo   URLs
echo     frontend  http://localhost:5173
echo     backend   http://localhost:9090/health
echo     ai        http://localhost:5000/api/health
echo     agent     http://localhost:8001/health
echo.
echo   close a console window = stop that service
echo   stop everything       = start-all.bat stop
echo ============================================================
echo.
pause
exit /b 0

:NO_ROOT
echo [error] project folder not found: %ROOT%
echo         edit ROOT at the top of this file
pause
exit /b 1

:NO_PYTHON
echo [error] python not found in PATH
pause
exit /b 1

:NO_NODE
echo [error] node not found in PATH
pause
exit /b 1

:STOP_ALL
echo stopping all services by port ...
call :KILL_PORT 5173 frontend
call :KILL_PORT 9090 backend
call :KILL_PORT 8001 agent
call :KILL_PORT 5000 ai
echo done. Redis left untouched.
pause
exit /b 0

:PORT_CHECK
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort %~1 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>&1
exit /b %errorlevel%

:WAIT_PORT
powershell -NoProfile -Command "$p=%~1; for($i=0;$i -lt %~2;$i++){ if(Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue){ exit 0 }; Start-Sleep -Seconds 1 }; exit 1" >nul 2>&1
if errorlevel 1 echo       [warn] port %~1 not ready in %~2s, continue anyway
exit /b 0

:KILL_PORT
set "KP="
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%~1 " ^| findstr "LISTENING"') do set "KP=%%a"
if defined KP (
    taskkill /F /PID %KP% >nul 2>&1
    echo   stopped %~2  port %~1  pid %KP%
) else (
    echo   %~2 not running  port %~1
)
exit /b 0
