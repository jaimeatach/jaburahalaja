@echo off
chcp 65001 >nul
title PILOTO AUTOMATICO - Otzar HaTorah
cd /d "%~dp0"
set PYTHONUTF8=1
echo ============================================
echo   PILOTO AUTOMATICO - Otzar HaTorah
echo   Deja esta ventana abierta junto al robot.
echo   Hace solo lo de ANUNCIAR y ACTUALIZAR.
echo ============================================
python "C:\OTZAR\jabura\piloto.py"
echo.
echo El piloto se detuvo. Vuelve a abrir PILOTO.bat
pause
