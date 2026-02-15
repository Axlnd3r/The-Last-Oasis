@echo off
echo === THE LAST OASIS - Reset and Run ===
echo.

:: Kill existing server
taskkill /F /IM uvicorn.exe 2>nul
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul

:: Delete old database
if exist last_oasis.sqlite3 del last_oasis.sqlite3
echo [OK] Database cleared

:: Start server in background
echo [..] Starting server...
start "LastOasis-Server" cmd /c "cd /d %~dp0 && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
timeout /t 4 /nobreak >nul
echo [OK] Server started at http://127.0.0.1:8000

:: Open dashboard
start http://127.0.0.1:8000/dashboard/
echo [OK] Dashboard opened in browser

:: Wait a moment then launch agents
timeout /t 2 /nobreak >nul
echo [..] Launching 5 agents (Random_A, Random_B, Belief_A, Trader_A, DQN_Sim)...
echo.
.venv\Scripts\python.exe run_agents.py 5
echo.
echo === All agents died. Press any key to exit ===
pause
