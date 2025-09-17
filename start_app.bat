@echo off
echo Starting Nutrition App...

REM Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Docker is not running. Please start Docker Desktop.
    pause
    exit /b 1
)

REM Start the application
echo Starting Docker containers...
docker-compose up --build -d

REM Wait for services to be ready
echo Waiting for services to start...
timeout /t 10 /nobreak >nul

REM Load initial data
echo Loading initial data...
docker-compose exec backend python scripts/load_initial_data.py

echo.
echo [SUCCESS] Nutrition App is ready!
echo.
echo Backend API: http://localhost:8000
echo Frontend: http://localhost:3000
echo API Docs: http://localhost:8000/docs
echo Database: localhost:5432
echo.
echo Press any key to view logs...
pause >nul
docker-compose logs -f

