#!/bin/bash
# Production startup script for the nutrition app

# Set environment variables
export DATABASE_URL=${DATABASE_URL:-"sqlite:///./nutrition_app.db"}
export SECRET_KEY=${SECRET_KEY:-"your-super-secret-jwt-key-change-this"}
export ENVIRONMENT=${ENVIRONMENT:-"production"}
export DEBUG=${DEBUG:-"false"}

# Check if Groq API keys are set
if [ -z "$GROQ_API_KEY" ]; then
    echo "Warning: GROQ_API_KEY not set. AI features will not work."
fi

# Create database if it doesn't exist
python -c "
import sqlite3
import os
db_path = os.getenv('DATABASE_URL', 'sqlite:///./nutrition_app.db').replace('sqlite:///', '')
if not os.path.exists(db_path):
    print(f'Creating database at {db_path}')
    conn = sqlite3.connect(db_path)
    conn.close()
"

# Start the application
echo "Starting Nutrition App..."
echo "Environment: $ENVIRONMENT"
echo "Database: $DATABASE_URL"
echo "Port: ${PORT:-8000}"

exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
