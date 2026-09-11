@echo off
chcp 65001 >nul
rem Lo corre el Programador de tareas de Windows cada 30 minutos (lo crea
rem instalar_otzar.py). Sube lo nuevo de la jabura y de tefila, espeja nacach
rem y, SOLO si la jabura subio algo, le pide al robot que anuncie.
set PYTHONUTF8=1
set "LOG=C:\OTZAR\jabura\auto.log"
echo. >> "%LOG%"
echo ===== %date% %time% ===== >> "%LOG%"
set ANUNCIAR=0

pushd "C:\OTZAR\jabura"
python jabura_publicar.py >> "%LOG%" 2>&1
if errorlevel 3 set ANUNCIAR=1
popd

if exist "C:\OTZAR\tefila\podcast_bot.py" (
  pushd "C:\OTZAR\tefila"
  python podcast_bot.py >> "%LOG%" 2>&1
  popd
)
if exist "C:\OTZAR\nacach\espejo_nacash.py" (
  pushd "C:\OTZAR\nacach"
  python espejo_nacash.py >> "%LOG%" 2>&1
  popd
)
if "%ANUNCIAR%"=="1" if exist "C:\robotwhats\robot_whatsapp.js" (
  echo anunciar> "C:\robotwhats\comando.txt"
  echo [auto] shiur nuevo de la jabura: orden de anunciar enviada al robot >> "%LOG%"
)
