@echo off
start "API" cmd /k "C:\Users\kaman\Desktop\ModirAgentOS\start_api.bat"
timeout /t 3
start "Frontend" cmd /k "cd /d C:\Users\kaman\Desktop\ModirAgentOS\ui\web && npm run dev"
