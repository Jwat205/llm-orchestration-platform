#!/bin/bash

# LLM API Platform - Database Restore Script
# This script restores database and application state from backup

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"
RESTORE_DATE="${1:-latest}"
ENVIRONMENT="${ENVIRONMENT:-development}"
NAMESPACE="${NAMESPACE:-llm-api-$ENVIRONMENT}"

# Logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >&2
}

error() {
    log "ERROR: $*"
    exit 1
}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

usage() {
    cat << EOF
Usage: $0 [BACKUP_DATE] [OPTIONS]

Restore database and application data from backup.

Arguments:
    BACKUP_DATE     Date of backup to restore (YYYY-MM-DD-HHMMSS) or 'latest' (default)

Environment Variables:
    ENVIRONMENT     Target environment (development|staging|production)
    NAMESPACE       Kubernetes namespace
    BACKUP_DIR      Directory containing backups
    DRY_RUN         Set to 'true' to simulate restore without making changes

Examples:
    $0                              # Restore from latest backup
    $0 latest                       # Same as above
    $0 2024-01-15-142500           # Restore from specific backup
    ENVIRONMENT=staging $0 latest   # Restore to staging environment

EOF
}

check_prerequisites() {
    print_status "Checking prerequisites..."

    # Check for required tools
    local required_tools=("kubectl" "pg_restore" "redis-cli")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            error "Required tool '$tool' is not installed"
        fi
    done

    # Check kubectl context
    local current_context
    current_context=$(kubectl config current-context)
    print_status "Current kubectl context: $current_context"

    # Verify namespace exists
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        error "Namespace '$NAMESPACE' does not exist"
    fi

    print_status "Prerequisites check completed"
}

find_backup() {
    local backup_date="$1"
    local backup_path=""

    if [[ "$backup_date" == "latest" ]]; then
        backup_path=$(find "$BACKUP_DIR" -name "backup-*" -type d | sort -r | head -1)
        if [[ -z "$backup_path" ]]; then
            error "No backups found in $BACKUP_DIR"
        fi
        backup_date=$(basename "$backup_path" | sed 's/backup-//')
    else
        backup_path="$BACKUP_DIR/backup-$backup_date"
        if [[ ! -d "$backup_path" ]]; then
            error "Backup directory not found: $backup_path"
        fi
    fi

    print_status "Selected backup: $backup_date"
    print_status "Backup path: $backup_path"

    # Verify backup integrity
    if [[ ! -f "$backup_path/backup.info" ]]; then
        error "Backup info file not found: $backup_path/backup.info"
    fi

    if [[ ! -f "$backup_path/postgres.sql" ]]; then
        error "PostgreSQL backup not found: $backup_path/postgres.sql"
    fi

    echo "$backup_path"
}

confirm_restore() {
    local backup_path="$1"

    echo
    print_warning "=== RESTORE CONFIRMATION ==="
    echo "Environment: $ENVIRONMENT"
    echo "Namespace: $NAMESPACE"
    echo "Backup: $(basename "$backup_path")"
    echo
    cat "$backup_path/backup.info"
    echo
    print_warning "This will OVERWRITE existing data in the target environment!"

    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        print_status "DRY RUN MODE - No actual changes will be made"
        return 0
    fi

    read -p "Are you sure you want to proceed? (type 'yes' to confirm): " confirmation
    if [[ "$confirmation" != "yes" ]]; then
        print_status "Restore cancelled"
        exit 0
    fi
}

scale_down_services() {
    print_status "Scaling down services..."

    # Scale down deployments
    local deployments=(
        "django-deployment"
        "fastapi-deployment"
        "worker-deployment"
        "scheduler-deployment"
    )

    for deployment in "${deployments[@]}"; do
        if kubectl get deployment "$deployment" -n "$NAMESPACE" &> /dev/null; then
            kubectl scale deployment "$deployment" --replicas=0 -n "$NAMESPACE"
            print_status "Scaled down $deployment"
        fi
    done

    # Wait for pods to terminate
    print_status "Waiting for pods to terminate..."
    sleep 30

    # Verify all application pods are terminated
    local remaining_pods
    remaining_pods=$(kubectl get pods -n "$NAMESPACE" --field-selector=status.phase=Running --no-headers | wc -l)
    if [[ "$remaining_pods" -gt 0 ]]; then
        print_warning "Some pods are still running. Waiting additional time..."
        sleep 60
    fi
}

restore_postgresql() {
    local backup_path="$1"

    print_status "Restoring PostgreSQL database..."

    # Get PostgreSQL pod
    local postgres_pod
    postgres_pod=$(kubectl get pods -n "$NAMESPACE" -l app=postgres -o jsonpath='{.items[0].metadata.name}')

    if [[ -z "$postgres_pod" ]]; then
        error "PostgreSQL pod not found"
    fi

    # Copy backup file to pod
    kubectl cp "$backup_path/postgres.sql" "$NAMESPACE/$postgres_pod:/tmp/restore.sql"

    # Drop existing connections and recreate database
    kubectl exec -n "$NAMESPACE" "$postgres_pod" -- psql -U postgres -c "
        SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'llm_api' AND pid <> pg_backend_pid();
        DROP DATABASE IF EXISTS llm_api;
        CREATE DATABASE llm_api WITH ENCODING 'UTF8';
    "

    # Restore database
    kubectl exec -n "$NAMESPACE" "$postgres_pod" -- psql -U postgres -d llm_api -f /tmp/restore.sql

    # Clean up
    kubectl exec -n "$NAMESPACE" "$postgres_pod" -- rm -f /tmp/restore.sql

    print_status "PostgreSQL restore completed"
}

restore_redis() {
    local backup_path="$1"

    if [[ ! -f "$backup_path/redis.rdb" ]]; then
        print_warning "Redis backup not found, skipping Redis restore"
        return 0
    fi

    print_status "Restoring Redis data..."

    # Get Redis pod
    local redis_pod
    redis_pod=$(kubectl get pods -n "$NAMESPACE" -l app=redis -o jsonpath='{.items[0].metadata.name}')

    if [[ -z "$redis_pod" ]]; then
        print_warning "Redis pod not found, skipping Redis restore"
        return 0
    fi

    # Flush existing data
    kubectl exec -n "$NAMESPACE" "$redis_pod" -- redis-cli FLUSHALL

    # Copy backup file
    kubectl cp "$backup_path/redis.rdb" "$NAMESPACE/$redis_pod:/data/dump.rdb"

    # Restart Redis to load backup
    kubectl delete pod "$redis_pod" -n "$NAMESPACE"

    # Wait for Redis to restart
    kubectl wait --for=condition=Ready pod -l app=redis -n "$NAMESPACE" --timeout=300s

    print_status "Redis restore completed"
}

restore_persistent_volumes() {
    local backup_path="$1"

    if [[ ! -d "$backup_path/volumes" ]]; then
        print_warning "Volume backups not found, skipping volume restore"
        return 0
    fi

    print_status "Restoring persistent volumes..."

    # Restore model cache
    if [[ -d "$backup_path/volumes/model-cache" ]]; then
        local model_cache_pod
        model_cache_pod=$(kubectl get pods -n "$NAMESPACE" -l app=fastapi -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

        if [[ -n "$model_cache_pod" ]]; then
            kubectl exec -n "$NAMESPACE" "$model_cache_pod" -- rm -rf /app/model_cache/*
            kubectl cp "$backup_path/volumes/model-cache/." "$NAMESPACE/$model_cache_pod:/app/model_cache/"
            print_status "Model cache restored"
        fi
    fi

    # Restore uploaded files
    if [[ -d "$backup_path/volumes/uploads" ]]; then
        local django_pod
        django_pod=$(kubectl get pods -n "$NAMESPACE" -l app=django -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

        if [[ -n "$django_pod" ]]; then
            kubectl exec -n "$NAMESPACE" "$django_pod" -- rm -rf /app/uploads/*
            kubectl cp "$backup_path/volumes/uploads/." "$NAMESPACE/$django_pod:/app/uploads/"
            print_status "Uploaded files restored"
        fi
    fi

    print_status "Persistent volumes restore completed"
}

scale_up_services() {
    print_status "Scaling up services..."

    # Read original replica counts from backup info
    local backup_path="$1"
    local django_replicas=3
    local fastapi_replicas=3

    if [[ -f "$backup_path/deployment-replicas.json" ]]; then
        django_replicas=$(jq -r '.django' "$backup_path/deployment-replicas.json")
        fastapi_replicas=$(jq -r '.fastapi' "$backup_path/deployment-replicas.json")
    fi

    # Scale up deployments
    kubectl scale deployment django-deployment --replicas="$django_replicas" -n "$NAMESPACE"
    kubectl scale deployment fastapi-deployment --replicas="$fastapi_replicas" -n "$NAMESPACE"

    # Wait for deployments to be ready
    kubectl wait --for=condition=Available deployment/django-deployment -n "$NAMESPACE" --timeout=600s
    kubectl wait --for=condition=Available deployment/fastapi-deployment -n "$NAMESPACE" --timeout=600s

    print_status "Services scaled up successfully"
}

run_post_restore_tasks() {
    print_status "Running post-restore tasks..."

    # Run Django migrations (in case of schema changes)
    local django_pod
    django_pod=$(kubectl get pods -n "$NAMESPACE" -l app=django -o jsonpath='{.items[0].metadata.name}')

    if [[ -n "$django_pod" ]]; then
        kubectl exec -n "$NAMESPACE" "$django_pod" -- python manage.py migrate --noinput
        kubectl exec -n "$NAMESPACE" "$django_pod" -- python manage.py collectstatic --noinput
        print_status "Django migrations completed"
    fi

    # Clear caches
    local redis_pod
    redis_pod=$(kubectl get pods -n "$NAMESPACE" -l app=redis -o jsonpath='{.items[0].metadata.name}')

    if [[ -n "$redis_pod" ]]; then
        kubectl exec -n "$NAMESPACE" "$redis_pod" -- redis-cli EVAL "return redis.call('del', unpack(redis.call('keys', ARGV[1])))" 0 "cache:*"
        print_status "Cache cleared"
    fi

    # Restart workers to reload models
    if kubectl get deployment worker-deployment -n "$NAMESPACE" &> /dev/null; then
        kubectl rollout restart deployment/worker-deployment -n "$NAMESPACE"
        kubectl rollout status deployment/worker-deployment -n "$NAMESPACE"
    fi

    print_status "Post-restore tasks completed"
}

verify_restore() {
    print_status "Verifying restore..."

    # Health checks
    local django_health
    local fastapi_health

    # Wait for services to be ready
    sleep 30

    # Check Django health
    if kubectl get service django-service -n "$NAMESPACE" &> /dev/null; then
        kubectl port-forward service/django-service 8080:80 -n "$NAMESPACE" &
        local pf_pid=$!
        sleep 5

        if curl -f http://localhost:8080/health/ &> /dev/null; then
            django_health="OK"
        else
            django_health="FAILED"
        fi

        kill $pf_pid 2>/dev/null || true
        sleep 2
    fi

    # Check FastAPI health
    if kubectl get service fastapi-service -n "$NAMESPACE" &> /dev/null; then
        kubectl port-forward service/fastapi-service 8081:80 -n "$NAMESPACE" &
        local pf_pid=$!
        sleep 5

        if curl -f http://localhost:8081/health &> /dev/null; then
            fastapi_health="OK"
        else
            fastapi_health="FAILED"
        fi

        kill $pf_pid 2>/dev/null || true
        sleep 2
    fi

    # Report status
    echo
    print_status "=== RESTORE VERIFICATION ==="
    echo "Django Service: ${django_health:-N/A}"
    echo "FastAPI Service: ${fastapi_health:-N/A}"

    # Check database connectivity
    local postgres_pod
    postgres_pod=$(kubectl get pods -n "$NAMESPACE" -l app=postgres -o jsonpath='{.items[0].metadata.name}')

    if [[ -n "$postgres_pod" ]]; then
        local db_tables
        db_tables=$(kubectl exec -n "$NAMESPACE" "$postgres_pod" -- psql -U postgres -d llm_api -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" | xargs)
        echo "Database Tables: $db_tables"
    fi

    if [[ "$django_health" == "FAILED" || "$fastapi_health" == "FAILED" ]]; then
        print_error "Some services failed health checks. Please investigate."
        exit 1
    fi

    print_status "Restore verification completed successfully"
}

main() {
    if [[ "$#" -gt 0 && ("$1" == "-h" || "$1" == "--help") ]]; then
        usage
        exit 0
    fi

    print_status "Starting restore process..."
    print_status "Environment: $ENVIRONMENT"
    print_status "Namespace: $NAMESPACE"

    check_prerequisites

    local backup_path
    backup_path=$(find_backup "$RESTORE_DATE")

    confirm_restore "$backup_path"

    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        print_status "DRY RUN COMPLETED - No changes were made"
        exit 0
    fi

    # Record start time
    local start_time
    start_time=$(date +%s)

    scale_down_services
    restore_postgresql "$backup_path"
    restore_redis "$backup_path"
    restore_persistent_volumes "$backup_path"
    scale_up_services "$backup_path"
    run_post_restore_tasks
    verify_restore

    # Calculate duration
    local end_time duration
    end_time=$(date +%s)
    duration=$((end_time - start_time))

    print_status "=== RESTORE COMPLETED ==="
    print_status "Duration: ${duration}s"
    print_status "Backup: $(basename "$backup_path")"
    print_status "Environment: $ENVIRONMENT"
    print_status "Timestamp: $(date)"

    # Log restore event
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Restore completed - Backup: $(basename "$backup_path") - Environment: $ENVIRONMENT - Duration: ${duration}s" >> "$PROJECT_ROOT/logs/restore.log"
}

# Handle script termination
cleanup() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        print_error "Restore failed with exit code $exit_code"
        echo "$(date '+%Y-%m-%d %H:%M:%S') - Restore failed - Environment: $ENVIRONMENT - Exit code: $exit_code" >> "$PROJECT_ROOT/logs/restore.log"
    fi

    # Kill any background port-forward processes
    jobs -p | xargs -r kill 2>/dev/null || true
}

trap cleanup EXIT
main "$@"