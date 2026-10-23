@echo off
rem Installe les bibliotheques de Varians : PySide6, lxml et Saxon (saxonche).
cd /d "%~dp0"
python -m pip install --user -r requirements.txt
pause
