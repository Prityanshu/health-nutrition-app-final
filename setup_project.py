# setup_project.py
"""
Complete project setup script for Nutrition App with MFP dataset integration
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

def create_directory_structure():
    """Create the complete project directory structure"""
    directories = [
        "app",
        "app/routers", 
        "app/services",
        "scripts",
        "config",
        "frontend/src/components",
        "frontend/src/services",
        "frontend/src/utils",
        "frontend/public",
        "static/pdfs",
        "uploads",
        "tests"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✅ Created directory: {directory}")

def create_files_from_artifacts():
    """Create all necessary files from the provided code"""
    files_to_create = {
        "config/data_config.py": """# Configuration file - copy from the artifact above""",
        "scripts/load_mfp_data.py": """# MFP data loader - copy from the artifact above""",
        "scripts/load_initial_data.py": """# Initial data loader - copy from the artifact above""",
        "docker-compose.yml": """# Docker compose file - copy from the artifact above""",
        "Dockerfile": """# Dockerfile - copy from the artifact above""",
        "requirements.txt": """# Requirements file - copy from the artifact above""",
        ".env.example": """# Environment variables example - copy from the artifact above""",
        ".env": """# Copy from .env.example and modify as needed
DATABASE_URL=postgresql://nutrition_user:nutrition_pass@localhost:5432/nutrition_db
SECRET_KEY=your-super-secret-key-change-in-production-2024
MFP_DATASET_PATH=C:/Users/prity/major-project-redo/mfp-diaries.tsv
USE_MFP_DATASET=true
MAX_RECORDS_TO_LOAD=10000
REPLACE_EXISTING_DATA=true
"""
    }
    
    for file_path, content in files_to_create.items():
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ Created file: {file_path}")

def check_prerequisites():
    """Check if required tools are installed"""
    required_tools = ["docker", "docker-compose", "python"]
    missing_tools = []
    
    for tool in required_tools:
        try:
            subprocess.run([tool, "--version"], capture_output=True, check=True)
            print(f"✅ {tool} is installed")
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing_tools.append(tool)
            print(f"❌ {tool} is not installed or not in PATH")
    
    if missing_tools:
        print(f"\n⚠️  Please install the following tools: {', '.join(missing_tools)}")
        return False
    
    return True

def verify_mfp_dataset():
    """Verify that the MFP dataset exists"""
    dataset_path = r"C:\Users\prity\major-project-redo\mfp-diaries.tsv"
    
    if os.path.exists(dataset_path):
        file_size = os.path.getsize(dataset_path) / (1024 * 1024)  # MB
        print(f"✅ MFP dataset found: {dataset_path} ({file_size:.1f} MB)")
        return True
    else:
        print(f"❌ MFP dataset not found at: {dataset_path}")
        return False

def setup_python_environment():
    """Set up Python virtual environment"""
    venv_path = Path("venv")
    
    if not venv_path.exists():
        print("Creating Python virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", "venv"])
        print("✅ Virtual environment created")
    
    # Install requirements
    if os.name == 'nt':  # Windows
        pip_path = venv_path / "Scripts" / "pip.exe"
        python_path = venv_path / "Scripts" / "python.exe"
    else:  # Unix/Linux/Mac
        pip_path = venv_path / "bin" / "pip"
        python_path = venv_path / "bin" / "python"
    
    if pip_path.exists():
        print("Installing Python requirements...")
        subprocess.run([str(pip_path), "install", "-r", "requirements.txt"])
        print("✅ Python requirements installed")

def create_startup_scripts():
    """Create convenient startup scripts"""
    
    # Windows batch file
    windows_startup = """@echo off
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

"""
    
    # Linux/Mac shell script
    unix_startup = """#!/bin/bash
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
"""
    
    with open("start_app.bat", "w", encoding="utf-8") as f:
        f.write(windows_startup)
    
    with open("start_app.sh", "w", encoding="utf-8") as f:
        f.write(unix_startup)
    
    # Make shell script executable on Unix systems
    if os.name != 'nt':
        os.chmod("start_app.sh", 0o755)
    
    print("✅ Created startup scripts: start_app.bat (Windows) and start_app.sh (Unix)")

def create_development_guide():
    """Create a development guide"""
    guide_content = """# Nutrition App Development Guide

## Quick Start

### Windows:
```bash
# Run the setup script
python setup_project.py

# Start the application
start_app.bat
```

### Linux/Mac:
```bash
# Run the setup script
python setup_project.py

# Start the application
./start_app.sh
```

## Manual Setup Steps

1. **Copy all artifact code to respective files**
2. **Build and start containers:**
   ```bash
   docker-compose up --build -d
   ```

3. **Load initial data:**
   ```bash
   docker-compose exec backend python scripts/load_initial_data.py
   ```

## Access Points

- **Backend API:** http://localhost:8000
- **API Documentation:** http://localhost:8000/docs
- **Frontend:** http://localhost:3000
- **Database:** localhost:5432

## Development Commands

### Backend Development:
```bash
# Access backend container
docker-compose exec backend bash

# Run tests
docker-compose exec backend pytest

# Check logs
docker-compose logs backend -f
```

### Database Operations:
```bash
# Access database
docker-compose exec db psql -U nutrition_user -d nutrition_db

# Backup database
docker-compose exec db pg_dump -U nutrition_user nutrition_db > backup.sql

# Load MFP data manually
docker-compose exec backend python scripts/load_mfp_data.py
```

### Frontend Development:
```bash
# Access frontend container
docker-compose exec frontend sh

# Install new packages
docker-compose exec frontend npm install package-name

# Build for production
docker-compose exec frontend npm run build
```

## Project Structure

```
nutrition-app/
├── app/                    # Backend application
│   ├── models.py          # Database models
│   ├── database.py        # Database configuration
│   ├── auth.py           # Authentication
│   └── routers/          # API routes
├── config/               # Configuration files
├── scripts/              # Data loading scripts  
├── frontend/             # React frontend
├── static/               # Static files
└── docker-compose.yml    # Docker configuration
```

## Customization

### Adding New Food Items:
1. Modify `scripts/load_mfp_data.py`
2. Update cuisine detection patterns
3. Run data loader

### Adding New Features:
1. Update database models in `app/models.py`
2. Create new API routes in `app/routers/`
3. Update frontend components

### Health Conditions:
1. Modify `HEALTH_RESTRICTIONS` in `config/data_config.py`
2. Update meal planning logic in services

## Troubleshooting

### Common Issues:
1. **Docker not running:** Start Docker Desktop
2. **Port conflicts:** Change ports in docker-compose.yml
3. **Database connection:** Check DATABASE_URL in .env
4. **MFP dataset not loading:** Verify file path and permissions

### Reset Database:
```bash
docker-compose down -v
docker-compose up --build -d
docker-compose exec backend python scripts/load_initial_data.py
```

## Production Deployment

1. **Set strong passwords** in docker-compose.yml
2. **Configure SSL/HTTPS** 
3. **Set up proper logging**
4. **Configure backups**
5. **Use production database** (PostgreSQL cluster)

For support, check the API documentation at http://localhost:8000/docs
"""
    
    with open("DEVELOPMENT_GUIDE.md", "w", encoding="utf-8") as f:
        f.write(guide_content)
    
    print("✅ Created DEVELOPMENT_GUIDE.md")

def main():
    """Main setup function"""
    print("🚀 Setting up Nutrition App with MFP Dataset Integration...\n")
    
    # Check prerequisites
    if not check_prerequisites():
        print("\n❌ Setup aborted due to missing prerequisites")
        return
    
    # Verify MFP dataset
    dataset_exists = verify_mfp_dataset()
    if not dataset_exists:
        print("⚠️  MFP dataset not found. App will work with sample data only.")
    
    # Create directory structure
    print("\n📁 Creating project structure...")
    create_directory_structure()
    
    # Create files
    print("\n📄 Creating configuration files...")
    create_files_from_artifacts()
    
    # Create startup scripts
    print("\n🚀 Creating startup scripts...")
    create_startup_scripts()
    
    # Create development guide
    print("\n📚 Creating development guide...")
    create_development_guide()
    
    print(f"""
🎉 Setup Complete!

⚠️  IMPORTANT: You still need to copy the actual code from the artifacts above into these files:
   📄 Copy FastAPI models and routes code to app/ directory
   📄 Copy React frontend code to frontend/ directory
   📄 Copy the actual implementation from all artifacts

Next Steps:
1. 📋 Copy all artifact code to the respective files
2. 🔧 Modify paths in config/data_config.py if needed
3. 🐳 Run: start_app.bat (Windows) or ./start_app.sh (Unix)
4. 🌐 Open http://localhost:8000/docs to see the API

Dataset Status: {'✅ Found' if dataset_exists else '❌ Not found - will use sample data'}
""")

if __name__ == "__main__":
    main()
