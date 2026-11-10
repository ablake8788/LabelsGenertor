@echo off
cd /d "%~dp0"
python label_app.py
if errorlevel 1 pause
