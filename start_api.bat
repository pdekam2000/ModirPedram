@echo off
echo Stopping old API process...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8765') do (
    taskkill /F /PID %%a 2>nul
)
timeout /t 2 /nobreak >nul
echo Starting API...
cd /d C:\Users\kaman\Desktop\ModirAgentOS
call venv\Scripts\activate
python -m ui.api.main
