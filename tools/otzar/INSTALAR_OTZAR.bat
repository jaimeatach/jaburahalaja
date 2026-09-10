@echo off
chcp 65001 >nul
title Instalar jabura + arreglar nacach
cd /d "%~dp0"
echo Bajando el instalador...
curl -L -s --ssl-no-revoke -o instalar_otzar.py https://raw.githubusercontent.com/jaimeatach/jaburahalaja/main/tools/otzar/instalar_otzar.py
if not exist instalar_otzar.py (
  echo No se pudo bajar. Revisa la conexion.
  goto fin
)
python instalar_otzar.py
:fin
echo.
pause
