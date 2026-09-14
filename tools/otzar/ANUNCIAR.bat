@echo off
chcp 65001 >nul
title ANUNCIAR - Otzar HaTorah

REM ESTA LINEA ES LA CLAVE: obliga al bat a pararse en SU carpeta
cd /d "%~dp0"

echo ============================================
echo   ANUNCIAR - Otzar HaTorah
echo ============================================
echo.
echo Carpeta: %CD%
echo.

if not exist "robot_whatsapp.js" (
  echo  !! No veo robot_whatsapp.js en esta carpeta.
  echo     Este ANUNCIAR.bat tiene que estar JUNTO al robot.
  echo.
  pause
  exit /b
)

rem === daf de hoy por calendario (otzar) ===
set PYTHONUTF8=1
python "%~dp0dafyomi_calendario.py"

rem === Otzar (sep/2026): mantenimiento antes de anunciar ===
rem Publica jabura y los shows de WhatsApp (Peretz, Nacach, Ofir, Tefila...),
rem alinea carpetas, espeja nacach y deja memorizado lo viejo (sin atrasos).
if exist "C:\OTZAR\jabura\mantenimiento.py" (
  python "C:\OTZAR\jabura\mantenimiento.py"
  echo.
)

echo anunciar> comando.txt

if not exist "comando.txt" (
  echo  !! No pude crear comando.txt ^(permisos?^)
  pause
  exit /b
)

echo  OK orden enviada. Esperando a que el robot la recoja...
echo.

set CUENTA=0
:esperar
timeout /t 2 /nobreak >nul
set /a CUENTA+=1
if not exist "comando.txt" goto recogida
if %CUENTA% LSS 8 goto esperar

echo ============================================
echo   !! EL ROBOT NO RECOGIO LA ORDEN
echo ============================================
echo.
echo  Revisa:
echo   1. Que la ventana del ROBOT este ABIERTA
echo   2. Que diga "ROBOT LISTO"
echo   3. Que el robot corra desde ESTA carpeta:
echo      %CD%
echo.
del comando.txt >nul 2>&1
pause
exit /b

:recogida
echo ============================================
echo   OK EL ROBOT RECOGIO LA ORDEN
echo ============================================
echo.
echo  Mira la ventana del ROBOT: ahi va el avance.
echo  Debe decir "=== ANUNCIANDO (boton) ==="
echo.
pause
