@echo off
REM ============================================================
REM  DataIA - lancement en un double-clic
REM  1. verifie le venv, le fichier .env, MySQL (WampServer) et Ollama
REM  2. demarre Ollama s'il est installe mais arrete
REM  3. signale les migrations de base de donnees en attente
REM  4. lance Flask avec le Python du venv et ouvre le navigateur
REM ============================================================
chcp 65001 >nul
title DataIA
cd /d "%~dp0"

set "PYTHON=%~dp0..\venv\Scripts\python.exe"
set "URL=http://127.0.0.1:5000"

echo ==============================================
echo     DEMARRAGE DE L'APPLICATION DATAIA
echo ==============================================
echo.

REM ---------- 1. venv ----------
if not exist "%PYTHON%" (
  echo [ERREUR] Python du venv introuvable : %PYTHON%
  echo          Le venv doit se trouver dans le dossier parent : ..\venv
  pause
  exit /b 1
)
echo [OK] venv : %PYTHON%

REM ---------- 2. .env ----------
if not exist ".env" (
  echo [ERREUR] Fichier .env absent. Copiez .env.example en .env et completez-le.
  pause
  exit /b 1
)
echo [OK] .env present

REM ---------- 3. MySQL (WampServer) ----------
powershell -NoProfile -Command "$c=New-Object Net.Sockets.TcpClient; try{$c.Connect('127.0.0.1',3306); exit 0}catch{exit 1}finally{$c.Close()}"
if errorlevel 1 (
  echo [ATTENTION] MySQL ne repond pas sur le port 3306 : lancez WampServer ^(icone verte^).
  echo             Appuyez sur une touche une fois WampServer demarre...
  pause >nul
) else (
  echo [OK] MySQL
)

REM ---------- 4. Ollama ----------
powershell -NoProfile -Command "$c=New-Object Net.Sockets.TcpClient; try{$c.Connect('127.0.0.1',11434); exit 0}catch{exit 1}finally{$c.Close()}"
if errorlevel 1 (
  where ollama >nul 2>nul
  if errorlevel 1 (
    echo [ATTENTION] Ollama n'est pas installe ou pas dans le PATH : le chat IA sera indisponible.
  ) else (
    echo [INFO] Ollama arrete : demarrage de "ollama serve" en arriere-plan...
    start "Ollama" /min ollama serve
    timeout /t 5 /nobreak >nul
  )
) else (
  echo [OK] Ollama
)

REM ---------- 5. Migrations en attente ----------
"%PYTHON%" migrate.py --statut | findstr /C:"en attente]" >nul
if not errorlevel 1 (
  echo [ATTENTION] Des migrations de base de donnees sont en attente.
  echo             Lancez : "%PYTHON%" migrate.py   ^(sauvegarde automatique avant migration^)
)

REM ---------- 6. Ouverture du navigateur des que le serveur repond ----------
REM (DATAIA_NO_BROWSER=1 desactive l'ouverture, utile pour les tests automatiques)
if not defined DATAIA_NO_BROWSER start "" /min powershell -NoProfile -WindowStyle Hidden -Command "for($i=0;$i -lt 90;$i++){ $c=New-Object Net.Sockets.TcpClient; try{ $c.Connect('127.0.0.1',5000); Start-Process '%URL%'; break }catch{ Start-Sleep 1 }finally{ $c.Close() } }"

REM ---------- 7. Flask ----------
echo.
echo Lancement du serveur Flask sur %URL%  (fermez cette fenetre ou Ctrl+C pour arreter)
echo.
"%PYTHON%" app.py
echo.
echo Le serveur s'est arrete.
pause
