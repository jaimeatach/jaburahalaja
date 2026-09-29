@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title INSISTIR - taamim a Archive
cd /d C:\OTZAR\taamim
set N=0
:otra
set /a N+=1
echo ============ intento %N% (%date% %time%) ============
python podcast_bot.py > ultimo_intento.txt 2>&1
type ultimo_intento.txt
findstr /c:"Publicados y marcados" ultimo_intento.txt >nul && goto listo
findstr /c:"No hay audios nuevos" ultimo_intento.txt >nul && goto listo
if %N% GEQ 40 goto rendido
echo.
echo Archive no dejo; espero 15 minutos y vuelvo a intentar (Ctrl+C para parar)...
timeout /t 900 /nobreak >nul
goto otra
:listo
echo.
echo ============ LISTO: taamim publicado. Falta el redirect en Spotify. ============
pause
exit /b 0
:rendido
echo.
echo Despues de 40 intentos Archive sigue sin dejar. Vuelve a correr este bat mas tarde.
pause
