#!/bin/bash

# LLM API Platform - Development Helper Functions
# Source this file to get useful development commands

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Helper function for colored output
print_info() {
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

# Docker Compose file
COMPOSE_FILE="docker-compose.dev.yml"

# Quick service management
start_dev() {
    print_info "Starting development environment..."
    docker-compose -f $COMPOSE_FILE up -d
    print_success "Development environment started"
}

stop_dev() {
    print_info "Stopping development environment..."
    docker-compose -f $COMPOSE_FILE down
    print_success "Development environment stopped"
}

restart_dev() {
    print_info "Restarting development environment..."
    docker-compose -f $COMPOSE_FILE restart
    print_success "Development environment restarted"
}

rebuild_dev() {
    print_info "Rebuilding and starting development environment..."
    docker-compose -f $COMPOSE_FILE up --build -d
    print_success "Development environment rebuilt and started"
}

# Service-specific commands
django_shell() {
    print_info "Opening Django shell..."
    docker-compose -f $COMPOSE_FILE exec django python manage.py shell
}

django_dbshell() {
    print_info "Opening Django database shell..."
    docker-compose -f $COMPOSE_FILE exec django python manage.py dbshell
}

fastapi_shell() {
    print_info "Opening FastAPI Python shell..."
    docker-compose -f $COMPOSE_FILE exec fastapi python -c "
import asyncio
from app.main import app
from app.database import get_db
print('FastAPI app and database available as: app, get_db')
print('Use: db = next(get_db()) to get database session')
"
}

# Database operations
migrate() {
    print_info "Running Django migrations..."
    docker-compose -f $COMPOSE_FILE exec django python manage.py migrate
    print_success "Migrations completed"
}

makemigrations() {
    print_info "Creating Django migrations..."
    docker-compose -f $COMPOSE_FILE exec django python manage.py makemigrations
    print_success "Migrations created"
}

reset_db() {
    print_warning "This will destroy all data. Are you sure? (y/N)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        print_info "Stopping services..."
        docker-compose -f $COMPOSE_FILE down

        print_info "Removing database volume..."
        docker volume rm "$(basename "$(pwd)")_postgres_data" 2>/dev/null || true

        print_info "Starting database..."
        docker-compose -f $COMPOSE_FILE up -d postgres
        sleep 10

        print_info "Running migrations..."
        docker-compose -f $COMPOSE_FILE up -d django
        sleep 5
        docker-compose -f $COMPOSE_FILE exec django python manage.py migrate

        print_info "Creating superuser..."
        docker-compose -f $COMPOSE_FILE exec django python manage.py shell -c "
from django.contrib.auth.models import User
User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
print('Superuser created: admin/admin123')
"
        print_success "Database reset completed"
    else
        print_info "Database reset cancelled"
    fi
}

create_superuser() {
    print_info "Creating Django superuser..."
    docker-compose -f $COMPOSE_FILE exec django python manage.py createsuperuser
}

# Testing commands
run_tests() {
    print_info "Running all tests..."
    echo ""
    print_info "Running Django tests..."
    docker-compose -f $COMPOSE_FILE exec django python manage.py test
    echo ""
    print_info "Running FastAPI tests..."
    docker-compose -f $COMPOSE_FILE exec fastapi python -m pytest
    print_success "All tests completed"
}

test_django() {
    print_info "Running Django tests..."
    docker-compose -f $COMPOSE_FILE exec django python manage.py test "$@"
}

test_fastapi() {
    print_info "Running FastAPI tests..."
    docker-compose -f $COMPOSE_FILE exec fastapi python -m pytest "$@"
}

test_coverage() {
    print_info "Running tests with coverage..."
    docker-compose -f $COMPOSE_FILE exec django coverage run --source='.' manage.py test
    docker-compose -f $COMPOSE_FILE exec django coverage report
    docker-compose -f $COMPOSE_FILE exec fastapi python -m pytest --cov=app
}

# Logging and monitoring
logs() {
    if [ -z "$1" ]; then
        print_info "Showing logs for all services..."
        docker-compose -f $COMPOSE_FILE logs -f
    else
        print_info "Showing logs for $1..."
        docker-compose -f $COMPOSE_FILE logs -f "$1"
    fi
}

logs_django() {
    docker-compose -f $COMPOSE_FILE logs -f django
}

logs_fastapi() {
    docker-compose -f $COMPOSE_FILE logs -f fastapi
}

logs_frontend() {
    docker-compose -f $COMPOSE_FILE logs -f frontend
}

logs_db() {
    docker-compose -f $COMPOSE_FILE logs -f postgres
}

# Service status
status() {
    print_info "Service status:"
    docker-compose -f $COMPOSE_FILE ps
    echo ""

    print_info "Health checks:"
    services=("django:8000/health/" "fastapi:8001/health" "frontend:3000")
    for service in "${services[@]}"; do
        service_name=$(echo "$service" | cut -d':' -f1)
        url="http://localhost:${service#*:}"
        if curl -f "$url" > /dev/null 2>&1; then
            print_success "$service_name is healthy"
        else
            print_error "$service_name is not responding"
        fi
    done
}

# Development utilities
flush_cache() {
    print_info "Flushing Redis cache..."
    docker-compose -f $COMPOSE_FILE exec redis redis-cli -a dev_password FLUSHALL
    print_success "Cache flushed"
}

collect_static() {
    print_info "Collecting Django static files..."
    docker-compose -f $COMPOSE_FILE exec django python manage.py collectstatic --noinput
    print_success "Static files collected"
}

# Database backup and restore
backup_db() {
    timestamp=$(date +%Y%m%d_%H%M%S)
    filename="backup_${timestamp}.sql"
    print_info "Creating database backup: $filename"
    docker-compose -f $COMPOSE_FILE exec postgres pg_dump -U postgres llm_api > "backups/$filename"
    print_success "Database backed up to backups/$filename"
}

restore_db() {
    if [ -z "$1" ]; then
        print_error "Please specify backup file: restore_db <filename>"
        return 1
    fi

    if [ ! -f "backups/$1" ]; then
        print_error "Backup file not found: backups/$1"
        return 1
    fi

    print_warning "This will overwrite the current database. Continue? (y/N)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        print_info "Restoring database from backups/$1..."
        docker-compose -f $COMPOSE_FILE exec -T postgres psql -U postgres llm_api < "backups/$1"
        print_success "Database restored"
    else
        print_info "Database restore cancelled"
    fi
}

# Performance monitoring
monitor_resources() {
    print_info "Monitoring container resources (press Ctrl+C to stop)..."
    docker-compose -f $COMPOSE_FILE exec django python -c "
import psutil
import time
while True:
    print(f'CPU: {psutil.cpu_percent()}%, Memory: {psutil.virtual_memory().percent}%')
    time.sleep(5)
"
}

# Quick setup for new developers
quick_setup() {
    print_info "Running quick setup for new developers..."

    # Check if environment is already set up
    if docker-compose -f $COMPOSE_FILE ps | grep -q "Up"; then
        print_warning "Development environment is already running"
        return 0
    fi

    # Run the main setup script
    if [ -f "./scripts/setup-dev.sh" ]; then
        ./scripts/setup-dev.sh
    else
        print_error "Setup script not found. Please run from project root."
        return 1
    fi
}

# Help function
dev_help() {
    echo ""
    echo -e "${GREEN}🔧 LLM API Platform - Development Helper Commands${NC}"
    echo ""
    echo -e "${YELLOW}Service Management:${NC}"
    echo "  start_dev          - Start development environment"
    echo "  stop_dev           - Stop development environment"
    echo "  restart_dev        - Restart development environment"
    echo "  rebuild_dev        - Rebuild and start development environment"
    echo "  status             - Show service status and health"
    echo ""
    echo -e "${YELLOW}Database Operations:${NC}"
    echo "  migrate            - Run Django migrations"
    echo "  makemigrations     - Create Django migrations"
    echo "  reset_db           - Reset database (destroys all data)"
    echo "  create_superuser   - Create Django superuser"
    echo "  backup_db          - Backup database"
    echo "  restore_db <file>  - Restore database from backup"
    echo ""
    echo -e "${YELLOW}Shell Access:${NC}"
    echo "  django_shell       - Open Django shell"
    echo "  django_dbshell     - Open Django database shell"
    echo "  fastapi_shell      - Open FastAPI Python shell"
    echo ""
    echo -e "${YELLOW}Testing:${NC}"
    echo "  run_tests          - Run all tests"
    echo "  test_django [args] - Run Django tests"
    echo "  test_fastapi [args]- Run FastAPI tests"
    echo "  test_coverage      - Run tests with coverage"
    echo ""
    echo -e "${YELLOW}Logging:${NC}"
    echo "  logs [service]     - Show logs (all services or specific)"
    echo "  logs_django        - Show Django logs"
    echo "  logs_fastapi       - Show FastAPI logs"
    echo "  logs_frontend      - Show Frontend logs"
    echo "  logs_db            - Show Database logs"
    echo ""
    echo -e "${YELLOW}Utilities:${NC}"
    echo "  flush_cache        - Clear Redis cache"
    echo "  collect_static     - Collect Django static files"
    echo "  monitor_resources  - Monitor container resources"
    echo "  quick_setup        - Quick setup for new developers"
    echo "  dev_help           - Show this help"
    echo ""
    echo -e "${GREEN}💡 To use these commands, source this file:${NC}"
    echo "   source ./scripts/dev-helpers.sh"
    echo ""
}

# Create backups directory
mkdir -p backups

# Show help if this script is run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    dev_help
    echo ""
    print_info "To use these functions, source this file:"
    echo "   source ./scripts/dev-helpers.sh"
    echo ""
fi

# Make functions available when sourced
export -f start_dev stop_dev restart_dev rebuild_dev
export -f django_shell django_dbshell fastapi_shell
export -f migrate makemigrations reset_db create_superuser
export -f run_tests test_django test_fastapi test_coverage
export -f logs logs_django logs_fastapi logs_frontend logs_db status
export -f flush_cache collect_static backup_db restore_db
export -f monitor_resources quick_setup dev_help

# Show welcome message when sourced
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    print_success "Development helper functions loaded!"
    echo "Type 'dev_help' to see available commands"
fi