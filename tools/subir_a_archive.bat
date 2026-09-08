@echo off
chcp 65001 >nul
title Subir shiurim a archive.org
cd /d "%~dp0"

echo ============================================
echo   Subir los shiurim a archive.org
echo ============================================
echo.

if not exist subir_a_archive.py (
  echo Descargando el script...
  curl -L -s -o subir_a_archive.py https://raw.githubusercontent.com/jaimeatach/jaburahalaja/main/tools/subir_a_archive.py
)
if not exist subir_a_archive.py (
  echo No se pudo descargar el script. Revisa tu conexion.
  goto fin
)

echo --- Prueba en seco: NO sube nada, solo lista ---
echo.
python subir_a_archive.py --ver
if errorlevel 1 goto fin
echo.

set "RESP="
set /p "RESP=Se ve bien la lista? Escribi SI y Enter para subir de verdad: "
if /i not "%RESP%"=="SI" (
  echo.
  echo No se subio nada. Volve a abrir este archivo cuando quieras.
  goto fin
)

echo.
if "%IA_ACCESS_KEY%"=="" set /p "IA_ACCESS_KEY=Pega tu ACCESS KEY de archive.org/account/s3.php: "
if "%IA_SECRET_KEY%"=="" set /p "IA_SECRET_KEY=Pega tu SECRET KEY: "
echo.
echo Subiendo. Esto tarda: no cierres esta ventana.
echo.
python subir_a_archive.py

:fin
echo.
pause
