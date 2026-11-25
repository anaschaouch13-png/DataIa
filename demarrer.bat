@echo off
chcp 65001 >nul
title Lancement de DataIA
cd /d "%~dp0"
echo ==============================================
echo     DEMARRAGE DE L'APPLICATION DATAIA
echo ==============================================
echo.
if not exist ".env" (
  echo ATTENTION : fichier .env absent. Copiez .env.example en .env et completez-le.
  pause
  exit /b 1
)
echo Verification de MySQL sur le port 3306...
powershell -Command "if (!(Test-NetConnection -ComputerName 127.0.0.1 -Port 3306 -InformationLevel Quiet)) { Write-Host 'ATTENTION : MySQL ne semble pas demarre (lancez WampServer).' -ForegroundColor Yellow }"
echo.
echo Verification d'Ollama sur le port 11434...
powershell -Command "if (!(Test-NetConnection -ComputerName 127.0.0.1 -Port 11434 -InformationLevel Quiet)) { Write-Host 'ATTENTION : Ollama inactif. Lancez : ollama serve' -ForegroundColor Yellow }"
echo.
echo Lancement du serveur Flask (venv du projet : ..\venv)...
"..\venv\Scripts\python.exe" app.py
pause
