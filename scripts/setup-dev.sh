#!/bin/bash

# LLM API Platform - Development Environment Setup Script
# This script sets up a complete development environment with debugging capabilities

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_status "Setting up LLM API Platform development environment..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker Desktop first."
    exit 1
fi

print_success "Docker is running"

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null; then
    print_error "docker-compose is not installed. Please install Docker Desktop with Compose."
    exit 1
fi

print_success "Docker Compose is available"

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    print_status "Creating .env file..."

    # Generate secure random keys
    DJANGO_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))' 2>/dev/null || echo "dev-secret-key-change-in-production-$(date +%s)")
    JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))' 2>/dev/null || echo "jwt-secret-$(date +%s)")

    cat > .env << EOF
# Development Environment Variables
# Generated on $(date)

# Django Settings
DEBUG=True
DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}
DJANGO_SETTINGS_MODULE=core.settings.development
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,django

# Database
DATABASE_URL=postgresql://postgres:dev_password@localhost:5432/llm_api
DB_HOST=postgres
DB_NAME=llm_api
DB_USER=postgres
DB_PASSWORD=dev_password
DB_PORT=5432

# Redis
REDIS_URL=redis://:dev_password@localhost:6379/0
REDIS_HOST=redis
REDIS_PASSWORD=dev_password
REDIS_PORT=6379

# API Keys (Update these with your actual keys)
OPENAI_API_KEY=your-openai-key-here
ANTHROPIC_API_KEY=your-anthropic-key-here
HUGGINGFACE_API_KEY=your-huggingface-key-here

# Authentication
JWT_SECRET=${JWT_SECRET}
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Email (Development - using MailHog)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=mailhog
EMAIL_PORT=1025
EMAIL_USE_TLS=False
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=

# File Storage
MEDIA_ROOT=/app/media
STATIC_ROOT=/app/static

# Model Cache
MODEL_CACHE_DIR=/app/models
HF_HOME=/app/huggingface_cache
TRANSFORMERS_CACHE=/app/transformers_cache

# Development URLs
DJANGO_URL=http://localhost:8000
FASTAPI_URL=http://localhost:8001
FRONTEND_URL=http://localhost:3000

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Monitoring (Development)
SENTRY_DSN=
MONITORING_ENABLED=False

# Feature Flags
ENABLE_DEBUG_TOOLBAR=True
ENABLE_SILK_PROFILING=True
ENABLE_API_THROTTLING=False
EOF

    print_success "Created .env file with development defaults"
    print_warning "Please update API keys in .env file before proceeding"
else
    print_success ".env file already exists"
fi

# Create necessary directories
print_status "Creating project directories..."
mkdir -p {logs,media,static,data/postgres,data/redis,models,huggingface_cache,transformers_cache}
print_success "Project directories created"

# Create nginx development configuration
print_status "Creating nginx development configuration..."
mkdir -p nginx
cat > nginx/dev.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream django_backend {
        server django:8000;
    }

    upstream fastapi_backend {
        server fastapi:8001;
    }

    upstream frontend_backend {
        server frontend:3000;
    }

    server {
        listen 80;
        server_name localhost;

        # Frontend
        location / {
            proxy_pass http://frontend_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # WebSocket support
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }

        # Django Admin and API
        location /admin {
            proxy_pass http://django_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /api/v1/auth {
            proxy_pass http://django_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # FastAPI
        location /api/v1 {
            proxy_pass http://fastapi_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Static files
        location /static/ {
            alias /var/www/static/;
        }

        location /media/ {
            alias /var/www/media/;
        }
    }
}
EOF
print_success "Nginx configuration created"

# Create database initialization script
print_status "Creating database initialization script..."
mkdir -p scripts
cat > scripts/init-db.sql << 'EOF'
-- Create additional databases for testing
CREATE DATABASE llm_api_test;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE llm_api TO postgres;
GRANT ALL PRIVILEGES ON DATABASE llm_api_test TO postgres;
EOF
print_success "Database initialization script created"

# Pull required Docker images
print_status "Pulling Docker images (this may take a while)..."
docker-compose -f docker-compose.dev.yml pull

# Build and start services
print_status "Building and starting services..."
docker-compose -f docker-compose.dev.yml up --build -d

# Wait for services to be ready
print_status "Waiting for services to start..."
sleep 20

# Check service health
print_status "Checking service health..."

# Wait for PostgreSQL
print_status "Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
    if docker-compose -f docker-compose.dev.yml exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
        print_success "PostgreSQL is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        print_error "PostgreSQL failed to start"
        exit 1
    fi
    sleep 2
done

# Wait for Redis
print_status "Waiting for Redis to be ready..."
for i in {1..30}; do
    if docker-compose -f docker-compose.dev.yml exec -T redis redis-cli -a dev_password ping > /dev/null 2>&1; then
        print_success "Redis is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        print_error "Redis failed to start"
        exit 1
    fi
    sleep 2
done

# Run Django migrations
print_status "Running Django database migrations..."
docker-compose -f docker-compose.dev.yml exec -T django python manage.py migrate

# Create Django superuser if it doesn't exist
print_status "Creating Django superuser..."
docker-compose -f docker-compose.dev.yml exec -T django python manage.py shell -c "
from django.contrib.auth.models import User
import os
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Superuser created: admin/admin123')
else:
    print('Superuser already exists')
"

# Collect static files
print_status "Collecting Django static files..."
docker-compose -f docker-compose.dev.yml exec -T django python manage.py collectstatic --noinput

# Test service connectivity
print_status "Testing service connectivity..."

# Test Django
if curl -f http://localhost:8000/health/ > /dev/null 2>&1; then
    print_success "Django service is responding"
else
    print_warning "Django service may not be ready yet"
fi

# Test FastAPI
if curl -f http://localhost:8001/health > /dev/null 2>&1; then
    print_success "FastAPI service is responding"
else
    print_warning "FastAPI service may not be ready yet"
fi

# Test Frontend
if curl -f http://localhost:3000 > /dev/null 2>&1; then
    print_success "Frontend service is responding"
else
    print_warning "Frontend service may not be ready yet"
fi

# Display final status
echo ""
print_success "Development environment setup complete!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${GREEN}🚀 Services are now running:${NC}"
echo ""
echo -e "   📊 ${BLUE}Django Admin:${NC}     http://localhost:8000/admin/"
echo -e "      Username: admin"
echo -e "      Password: admin123"
echo ""
echo -e "   🔧 ${BLUE}FastAPI Docs:${NC}     http://localhost:8001/docs"
echo -e "   📱 ${BLUE}Frontend:${NC}         http://localhost:3000"
echo -e "   🐘 ${BLUE}Database Admin:${NC}   http://localhost:8080 (Adminer)"
echo -e "   📧 ${BLUE}Mail Interface:${NC}   http://localhost:8025 (MailHog)"
echo ""
echo -e "${GREEN}🔧 Development Tools:${NC}"
echo ""
echo -e "   Debug Django:   Port 5678 (attach debugger in VSCode)"
echo -e "   Debug FastAPI:  Port 5679 (attach debugger in VSCode)"
echo ""
echo -e "${GREEN}📖 Useful Commands:${NC}"
echo ""
echo -e "   View logs:           ${YELLOW}docker-compose -f docker-compose.dev.yml logs -f${NC}"
echo -e "   Stop services:       ${YELLOW}docker-compose -f docker-compose.dev.yml down${NC}"
echo -e "   Restart services:    ${YELLOW}docker-compose -f docker-compose.dev.yml restart${NC}"
echo -e "   Django shell:        ${YELLOW}docker-compose -f docker-compose.dev.yml exec django python manage.py shell${NC}"
echo -e "   Run tests:           ${YELLOW}docker-compose -f docker-compose.dev.yml exec django python manage.py test${NC}"
echo ""
echo -e "${GREEN}🎯 VSCode Integration:${NC}"
echo ""
echo -e "   1. Open VSCode in this directory"
echo -e "   2. Install recommended extensions"
echo -e "   3. Use Ctrl+Shift+P → 'Tasks: Run Task' for quick commands"
echo -e "   4. Set breakpoints and use F5 to debug"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
print_warning "Don't forget to update API keys in the .env file!"
echo ""