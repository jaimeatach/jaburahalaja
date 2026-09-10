@echo off
chcp 65001 >nul
title Jabura: publicar shiurim nuevos
cd /d "%~dp0"

echo ============================================
echo   Jabura: Drive -^> archive.org -^> feed -^> Spotify
echo ============================================
echo.
for %%f in (jabura_publicar.py subir_a_archive.py) do (
  if not exist %%f (
    echo Descargando %%f...
    curl -L -s --ssl-no-revoke -o %%f https://raw.githubusercontent.com/jaimeatach/jaburahalaja/main/tools/%%f
  )
)
if not exist config.json (
  echo Falta config.json en esta carpeta. Bajalo de tools/otzar/config.json del repo.
  goto fin
)
echo --- Prueba en seco: NO sube nada, solo lista ---
python jabura_publicar.py --ver
if errorlevel 1 goto fin
echo.
set "RESP="
set /p "RESP=Se ve bien? Escribi SI y Enter para subir y publicar el feed: "
if /i not "%RESP%"=="SI" goto fin
if "%IA_ACCESS_KEY%"=="" set /p "IA_ACCESS_KEY=Pega tu ACCESS KEY de archive.org/account/s3.php: "
if "%IA_SECRET_KEY%"=="" set /p "IA_SECRET_KEY=Pega tu SECRET KEY: "
python jabura_publicar.py
:fin
echo.
pause
