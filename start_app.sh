#!/bin/bash
set -e

echo "Starting Nutrition App..."

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker."
    exit 1
fi

# Start the application
echo "Starting Docker containers..."
docker-compose up --build -d

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 10

# Load initial data
echo "Loading initial data..."
docker-compose exec backend python scripts/load_initial_data.py

echo ""
echo "✅ Nutrition App is ready!"
echo ""
echo "🌐 Backend API: http://localhost:8000"
echo "📱 Frontend: http://localhost:3000" 
echo "📊 API Docs: http://localhost:8000/docs"
echo "🗄️ Database: localhost:5432"
echo ""
echo "Press Ctrl+C to view logs..."
docker-compose logs -f
