@echo off
cd /d "%~dp0"
rem Deposer le project.xml d'un projet sur ce fichier pour generer son viewer web.
python web_viewer\generator.py %*
pause
