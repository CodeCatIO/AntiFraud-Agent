@echo off
REM ============================================================
REM  AI Detection Service - One-click launcher for Windows
REM  AI检测微服务一键启动脚本（Windows）
REM  双击本文件即可启动；出错时窗口不会闪退，会停在错误信息处
REM ============================================================
chcp 65001 >nul
title AI Detection Service (Flask :5000)

REM Always run from the flask_app directory next to this .bat
cd /d "%~dp0flask_app"

echo ============================================================
echo   AI Detection Service - starting...
echo   Working directory: %CD%
echo ============================================================
echo.

echo [1/3] Checking Python...
python --version
if errorlevel 1 (
    echo.
    echo [ERROR] Python not found.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo IMPORTANT: tick "Add python.exe to PATH" during installation.
    echo.
    pause
    exit /b 1
)
echo.

echo [2/3] Checking dependencies (flask, flask-cors)...
python -c "import flask, flask_cors" 2>nul
if errorlevel 1 (
    echo Dependencies missing, installing from requirements.txt ...
    if exist "..\requirements.txt" (
        pip install -r "..\requirements.txt"
    ) else (
        pip install flask flask-cors
    )
    if errorlevel 1 (
        echo [ERROR] Dependency installation failed. Check your network / pip.
        pause
        exit /b 1
    )
) else (
    echo Dependencies OK.
)
echo.

echo [3/3] Starting service...  (URL: http://localhost:5000/api/health)
echo Press Ctrl+C to stop.
echo ------------------------------------------------------------
python app.py

echo.
echo ------------------------------------------------------------
echo Service stopped (or crashed). The message above shows why.
pause
