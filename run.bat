@echo off
cd /d "%~dp0"
if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat
echo.
echo  Open in browser:  http://localhost:8000
echo  Do NOT use http://0.0.0.0:8000
echo.
python main.py
