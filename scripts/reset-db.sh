#!/bin/bash

# LLM API Platform - Database Reset Script
# This script completely resets the development database

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

COMPOSE_FILE="docker-compose.dev.yml"

print_warning "⚠️  DATABASE RESET WARNING ⚠️"
echo ""
print_warning "This will permanently delete ALL data in the development database!"
echo ""
echo "This includes:"
echo "  • All user accounts"
echo "  • All API keys"
echo "  • All chat history"
echo "  • All fine-tuning jobs"
echo "  • All uploaded files"
echo ""
print_warning "Are you absolutely sure you want to continue? (type 'yes' to confirm)"
read -r response

if [[ "$response" != "yes" ]]; then
    print_error "Database reset cancelled"
    exit 0
fi

print_status "Starting database reset process..."

# Stop all services
print_status "Stopping all services..."
docker-compose -f $COMPOSE_FILE down

# Remove database volume
print_status "Removing database volume..."
PROJECT_NAME=$(basename "$(pwd)" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]//g')
VOLUME_NAME="${PROJECT_NAME}_postgres_data"

if docker volume ls | grep -q "$VOLUME_NAME"; then
    docker volume rm "$VOLUME_NAME"
    print_success "Database volume removed"
else
    print_warning "Database volume not found (may already be clean)"
fi

# Remove Redis volume (optional)
print_status "Removing Redis volume..."
REDIS_VOLUME_NAME="${PROJECT_NAME}_redis_data"
if docker volume ls | grep -q "$REDIS_VOLUME_NAME"; then
    docker volume rm "$REDIS_VOLUME_NAME"
    print_success "Redis volume removed"
fi

# Start database service
print_status "Starting PostgreSQL service..."
docker-compose -f $COMPOSE_FILE up -d postgres
sleep 10

# Wait for PostgreSQL to be ready
print_status "Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
    if docker-compose -f $COMPOSE_FILE exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
        print_success "PostgreSQL is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        print_error "PostgreSQL failed to start"
        exit 1
    fi
    sleep 2
done

# Start Redis service
print_status "Starting Redis service..."
docker-compose -f $COMPOSE_FILE up -d redis
sleep 5

# Start Django service
print_status "Starting Django service..."
docker-compose -f $COMPOSE_FILE up -d django
sleep 10

# Run migrations
print_status "Running database migrations..."
docker-compose -f $COMPOSE_FILE exec -T django python manage.py migrate

# Create superuser
print_status "Creating Django superuser..."
docker-compose -f $COMPOSE_FILE exec -T django python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Superuser created: admin/admin123')
else:
    print('Superuser already exists')
"

# Load sample data (optional)
print_status "Would you like to load sample development data? (y/N)"
read -r load_data

if [[ "$load_data" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    print_status "Loading sample data..."

    # Create sample data
    docker-compose -f $COMPOSE_FILE exec -T django python manage.py shell -c "
from django.contrib.auth.models import User
from django.utils import timezone
import json

# Create sample users
users_data = [
    {'username': 'developer', 'email': 'dev@example.com', 'password': 'dev123'},
    {'username': 'tester', 'email': 'test@example.com', 'password': 'test123'},
    {'username': 'demo_user', 'email': 'demo@example.com', 'password': 'demo123'},
]

for user_data in users_data:
    if not User.objects.filter(username=user_data['username']).exists():
        user = User.objects.create_user(
            username=user_data['username'],
            email=user_data['email'],
            password=user_data['password']
        )
        print(f'Created user: {user.username}')

print('Sample data loaded successfully')
"

    print_success "Sample data loaded"
fi

# Start all services
print_status "Starting all services..."
docker-compose -f $COMPOSE_FILE up -d

# Wait for services to be ready
print_status "Waiting for services to start..."
sleep 15

# Collect static files
print_status "Collecting static files..."
docker-compose -f $COMPOSE_FILE exec -T django python manage.py collectstatic --noinput

# Test connectivity
print_status "Testing service connectivity..."

if curl -f http://localhost:8000/health/ > /dev/null 2>&1; then
    print_success "Django service is responding"
else
    print_warning "Django service may not be ready yet"
fi

if curl -f http://localhost:8001/health > /dev/null 2>&1; then
    print_success "FastAPI service is responding"
else
    print_warning "FastAPI service may not be ready yet"
fi

echo ""
print_success "Database reset completed successfully!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${GREEN}✅ Fresh Development Environment Ready${NC}"
echo ""
echo -e "${BLUE}Admin Access:${NC}"
echo "  URL: http://localhost:8000/admin/"
echo "  Username: admin"
echo "  Password: admin123"
echo ""

if [[ "$load_data" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo -e "${BLUE}Sample User Accounts:${NC}"
    echo "  developer/dev123"
    echo "  tester/test123"
    echo "  demo_user/demo123"
    echo ""
fi

echo -e "${BLUE}Services:${NC}"
echo "  Django:   http://localhost:8000"
echo "  FastAPI:  http://localhost:8001"
echo "  Frontend: http://localhost:3000"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""