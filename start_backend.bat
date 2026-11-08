@echo off
echo ==========================================
echo  Options Trading Platform - Local Hosting
echo ==========================================
echo.
echo  Starting Backend (FastAPI)...
echo  API will be available at: http://localhost:8000
echo.
cd /d C:\app
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
pause