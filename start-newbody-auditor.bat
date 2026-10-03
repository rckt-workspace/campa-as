@echo off
setlocal enabledelayedexpansion

title NewBody Content Auditor - Starting...

echo.
echo ==========================================
echo   NewBody Content Auditor
echo ==========================================
echo.

REM Cambiar al directorio del script
cd /d "%~dp0"

REM Detectar si los procesos ya están corriendo
netstat -ano | find "8005" >nul
if %errorlevel% equ 0 (
    echo Backend ya está corriendo en puerto 8005
) else (
    echo Iniciando backend en puerto 8005...
    cd backend
    set LOCAL_API_PORT=8005
    set LOCAL_API_HOST=127.0.0.1
    set BROWSER_HEADLESS=false
    start "NewBody Backend" /b python -m app.scripts.run_local_server
    cd ..
    timeout /t 3 /nobreak
)

netstat -ano | find "5173" >nul
if %errorlevel% equ 0 (
    echo Frontend ya está corriendo en puerto 5173
) else (
    echo Iniciando frontend...
    cd frontend
    start "NewBody Frontend" /b npm run dev
    cd ..
    timeout /t 5 /nobreak
)

echo.
echo ==========================================
echo   Servicios iniciados
echo ==========================================
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo.
echo Abriendo navegador...
timeout /t 2 /nobreak

start http://localhost:5173

echo.
echo Los servicios están corriendo.
echo Cierra esta ventana cuando termines.
echo.
pause
