@echo off
title Lancement de DataIA
cd /d "%~dp0"
echo ==============================================
echo     DEMARRAGE DE L'APPLICATION DATAIA
echo ==============================================
echo.
echo Verification de MySQL sur le port 3306...
powershell -Command "if (!(Test-NetConnection -ComputerName 127.0.0.1 -Port 3306 -InformationLevel Quiet)) { Write-Host 'ATTENTION : Le serveur MySQL ne semble pas demarre sur le port 3306.' -ForegroundColor Yellow; Write-Host 'Veuillez demarrer MySQL via XAMPP ou WampServer.' -ForegroundColor Yellow; }"
echo.
echo Verification d'Ollama sur le port 11434...
powershell -Command "if (!(Test-NetConnection -ComputerName 127.0.0.1 -Port 11434 -InformationLevel Quiet)) { Write-Host 'ATTENTION : Ollama ne semble pas actif sur http://localhost:11434.' -ForegroundColor Yellow; Write-Host 'Assurez-vous de lancer Ollama et les modeles : ollama run qwen2.5:3b et ollama pull nomic-embed-text' -ForegroundColor Yellow; }"
echo.
echo Lancement du serveur Flask...
.\venv_dataia\Scripts\python.exe app.py
pause
