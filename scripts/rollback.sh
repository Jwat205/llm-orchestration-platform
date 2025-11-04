#!/bin/bash

# LLM Platform Rollback Script
# Usage: ./rollback.sh [environment] [revision]

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
NAMESPACE_PREFIX="llm-platform"

# Default values
ENVIRONMENT="${1:-staging}"
REVISION="${2:-}"
DRY_RUN="${DRY_RUN:-false}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed"
        exit 1
    fi
    
    if ! command -v helm &> /dev/null; then
        log_error "helm is not installed"
        exit 1
    fi
    
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    log_info "Prerequisites check passed"
}

# Get namespace
get_namespace() {
    local namespace="$NAMESPACE_PREFIX"
    if [ "$ENVIRONMENT" != "production" ]; then
        namespace="$NAMESPACE_PREFIX-$ENVIRONMENT"
    fi
    echo "$namespace"
}

# List available revisions
list_revisions() {
    local namespace=$(get_namespace)
    
    log_info "Available Helm releases in namespace $namespace:"
    helm history llm-platform -n "$namespace" --max 10
    
    log_info "Available Kubernetes deployment revisions:"
    kubectl rollout history deployment/llm-platform-django -n "$namespace"
    kubectl rollout history deployment/llm-platform-fastapi -n "$namespace"
}

# Validate revision
validate_revision() {
    if [ -z "$REVISION" ]; then
        log_error "No revision specified"
        list_revisions
        exit 1
    fi
    
    local namespace=$(get_namespace)
    
    # Check if Helm revision exists
    if ! helm history llm-platform -n "$namespace" | grep -q "$REVISION"; then
        log_error "Helm revision $REVISION not found"
        list_revisions
        exit 1
    fi
}

# Backup current state
backup_current_state() {
    local namespace=$(get_namespace)
    local backup_dir="/tmp/llm-platform-backup-$(date +%Y%m%d-%H%M%S)"
    
    log_info "Creating backup of current state in $backup_dir"
    mkdir -p "$backup_dir"
    
    # Backup Helm values
    helm get values llm-platform -n "$namespace" > "$backup_dir/helm-values.yaml"
    
    # Backup Kubernetes manifests
    kubectl get deployment llm-platform-django -n "$namespace" -o yaml > "$backup_dir/django-deployment.yaml"
    kubectl get deployment llm-platform-fastapi -n "$namespace" -o yaml > "$backup_dir/fastapi-deployment.yaml"
    
    # Backup database
    log_info "Creating database backup..."
    kubectl exec -n "$namespace" deployment/llm-platform-django -- \
        python manage.py dbbackup --clean
    
    log_info "Backup created at $backup_dir"
}

# Perform Helm rollback
helm_rollback() {
    local namespace=$(get_namespace)
    
    log_info "Rolling back Helm release to revision $REVISION"
    
    local helm_args=(
        "rollback" "llm-platform" "$REVISION"
        "--namespace" "$namespace"
        "--wait" "--timeout=10m"
    )
    
    if [ "$DRY_RUN" = "true" ]; then
        helm_args+=("--dry-run")
    fi
    
    helm "${helm_args[@]}"
    
    log_info "Helm rollback completed"
}

# Verify rollback
verify_rollback() {
    if [ "$DRY_RUN" = "true" ]; then
        log_info "Skipping verification in dry-run mode"
        return
    fi
    
    local namespace=$(get_namespace)
    
    log_info "Verifying rollback..."
    
    # Wait for deployments to be ready
    log_info "Waiting for deployments to stabilize..."
    kubectl wait --for=condition=available --timeout=600s \
        deployment/llm-platform-django \
        deployment/llm-platform-fastapi \
        -n "$namespace"
    
    # Check rollout status
    kubectl rollout status deployment/llm-platform-django -n "$namespace"
    kubectl rollout status deployment/llm-platform-fastapi -n "$namespace"
    
    # Run health checks
    log_info "Running health checks..."
    
    # Django health check
    local django_healthy=false
    for i in {1..5}; do
        if kubectl run django-health-check-$i --rm -i --restart=Never \
            --image=curlimages/curl:latest \
            --namespace="$namespace" \
            -- curl -f "http://llm-platform-django:8000/health/" &> /dev/null; then
            django_healthy=true
            break
        fi
        log_warn "Django health check attempt $i failed, retrying..."
        sleep 10
    done
    
    if [ "$django_healthy" = "false" ]; then
        log_error "Django service health check failed after rollback"
        return 1
    fi
    
    # FastAPI health check
    local fastapi_healthy=false
    for i in {1..5}; do
        if kubectl run fastapi-health-check-$i --rm -i --restart=Never \
            --image=curlimages/curl:latest \
            --namespace="$namespace" \
            -- curl -f "http://llm-platform-fastapi:8001/health" &> /dev/null; then
            fastapi_healthy=true
            break
        fi
        log_warn "FastAPI health check attempt $i failed, retrying..."
        sleep 10
    done
    
    if [ "$fastapi_healthy" = "false" ]; then
        log_error "FastAPI service health check failed after rollback"
        return 1
    fi
    
    log_info "All health checks passed after rollback"
}

# Run post-rollback tests
run_post_rollback_tests() {
    if [ "$DRY_RUN" = "true" ]; then
        log_info "Skipping tests in dry-run mode"
        return
    fi
    
    local namespace=$(get_namespace)
    
    log_info "Running post-rollback smoke tests..."
    
    # Test basic API functionality
    kubectl run rollback-test --rm -i --restart=Never \
        --image=curlimages/curl:latest \
        --namespace="$namespace" \
        -- curl -f -X POST "http://llm-platform-fastapi:8001/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d '{"model":"test","messages":[{"role":"user","content":"Health check"}],"max_tokens":1}' \
        || log_warn "API smoke test failed - service may still be initializing"
    
    log_info "Post-rollback tests completed"
}

# Show current status
show_status() {
    local namespace=$(get_namespace)
    
    log_info "Current deployment status:"
    
    # Show Helm release info
    helm list -n "$namespace"
    helm status llm-platform -n "$namespace"
    
    # Show pod status
    kubectl get pods -n "$namespace" -l app.kubernetes.io/name=llm-platform
    
    # Show service status
    kubectl get services -n "$namespace" -l app.kubernetes.io/name=llm-platform
}

# Main rollback function
main() {
    log_info "Starting LLM Platform rollback"
    log_info "Environment: $ENVIRONMENT"
    log_info "Target revision: $REVISION"
    log_info "Dry run: $DRY_RUN"
    
    check_prerequisites
    
    if [ -z "$REVISION" ]; then
        list_revisions
        exit 0
    fi
    
    validate_revision
    
    if [ "$DRY_RUN" != "true" ]; then
        backup_current_state
    fi
    
    helm_rollback
    
    if verify_rollback; then
        run_post_rollback_tests
        log_info "Rollback completed successfully!"
    else
        log_error "Rollback verification failed"
        exit 1
    fi
    
    show_status
}

# Handle script interruption
trap 'log_error "Rollback interrupted"; exit 1' INT TERM

# Show help
if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    cat << EOF
LLM Platform Rollback Script

Usage: $0 [environment] [revision]

Arguments:
  environment    Target environment (development|staging|production)
  revision       Helm revision number to rollback to

Environment Variables:
  DRY_RUN        Set to 'true' for dry run mode

Examples:
  $0 staging 3
  DRY_RUN=true $0 production 5
  $0 staging  # List available revisions

EOF
    exit 0
fi

# List revisions if no revision specified
if [ -z "${2:-}" ]; then
    check_prerequisites
    list_revisions
    exit 0
fi

# Run main function
main "$@"