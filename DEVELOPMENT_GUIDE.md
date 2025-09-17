# Nutrition App Development Guide

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
