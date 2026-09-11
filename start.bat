@echo off
echo Starting Smart Job Assistant...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /PID %%a /F >nul 2>&1
start "Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\uvicorn app.main:app --reload --port 8000"
timeout /t 3 /nobreak >nul
start "Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
echo.
echo Backend: http://127.0.0.1:8000
echo Frontend: http://localhost:5173
echo.
echo Set DEEPSEEK_API_KEY in system env (or backend\.env) to use real LLM (otherwise Mock mode)
