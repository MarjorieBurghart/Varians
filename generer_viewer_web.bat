@echo off
cd /d "%~dp0"
python web_viewer\generator.py project.xml
pause
