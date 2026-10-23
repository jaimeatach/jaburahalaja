@echo off
chcp 65001 >nul
title PILOTO AUTOMATICO - Otzar HaTorah
cd /d "%~dp0"
set PYTHONUTF8=1
echo ============================================
echo   PILOTO AUTOMATICO - Otzar HaTorah
echo   Deja esta ventana abierta junto al robot.
echo   Hace solo lo de ANUNCIAR y ACTUALIZAR.
echo   Para apagarlo: cierra esta ventana.
echo ============================================
:otra_vez
python "C:\OTZAR\jabura\piloto.py"
echo.
echo El piloto se detuvo. Se vuelve a abrir solo en 30 segundos (cierra la ventana para apagarlo).
timeout /t 30
goto otra_vez
