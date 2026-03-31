@echo off
cd /d "%~dp0backend"
call venv\Scripts\activate.bat
@REM start "" http://localhost:8000
fastapi dev