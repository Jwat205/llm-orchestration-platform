#!/bin/bash

# LLM Platform Deployment Script
# Usage: ./deploy.sh [environment] [version]

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
NAMESPACE_PREFIX="llm-platform"
HELM_CHART_PATH="$PROJECT_ROOT/helm-chart"

# Default values
ENVIRONMENT="${1:-staging}"
VERSION="${2:-latest}"
DRY_RUN="${DRY_RUN:-false}"
SKIP_TESTS="${SKIP_TESTS:-false}"

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
    
    # Check if kubectl is installed
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed"
        exit 1
    fi
    
    # Check if helm is installed
    if ! command -v helm &> /dev/null; then
        log_error "helm is not installed"
        exit 1
    fi
    
    # Check kubectl connection
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    log_info "Prerequisites check passed"
}

# Validate environment
validate_environment() {
    case $ENVIRONMENT in
        development|staging|production)
            log_info "Deploying to $ENVIRONMENT environment"
            ;;
        *)
            log_error "Invalid environment: $ENVIRONMENT"
            log_error "Valid environments: development, staging, production"
            exit 1
            ;;
    esac
}

# Create namespace if it doesn't exist
create_namespace() {
    local namespace="$NAMESPACE_PREFIX"
    if [ "$ENVIRONMENT" != "production" ]; then
        namespace="$NAMESPACE_PREFIX-$ENVIRONMENT"
    fi
    
    log_info "Creating namespace: $namespace"
    kubectl create namespace "$namespace" --dry-run=client -o yaml | kubectl apply -f -
}

# Pre-deployment checks
pre_deployment_checks() {
    log_info "Running pre-deployment checks..."
    
    local namespace="$NAMESPACE_PREFIX"
    if [ "$ENVIRONMENT" != "production" ]; then
        namespace="$NAMESPACE_PREFIX-$ENVIRONMENT"
    fi
    
    # Check if there are running pods
    if kubectl get pods -n "$namespace" &> /dev/null; then
        local pod_count=$(kubectl get pods -n "$namespace" --no-headers | wc -l)
        if [ "$pod_count" -gt 0 ]; then
            log_warn "Found $pod_count running pods in namespace $namespace"
        fi
    fi
    
    # Check resource quotas
    if kubectl get resourcequota -n "$namespace" &> /dev/null; then
        log_info "Resource quotas found in namespace"
        kubectl describe resourcequota -n "$namespace"
    fi
}

# Run database migrations
run_migrations() {
    log_info "Running database migrations..."
    
    local namespace="$NAMESPACE_PREFIX"
    if [ "$ENVIRONMENT" != "production" ]; then
        namespace="$NAMESPACE_PREFIX-$ENVIRONMENT"
    fi
    
    # Create migration job
    kubectl create job "migration-$(date +%s)" \
        --from=deployment/llm-platform-django \
        --namespace="$namespace" \
        --dry-run=client -o yaml | \
        sed 's/restartPolicy: OnFailure/restartPolicy: Never/' | \
        kubectl apply -f -
    
    # Wait for migration to complete
    local job_name=$(kubectl get jobs -n "$namespace" --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}')
    kubectl wait --for=condition=complete --timeout=300s "job/$job_name" -n "$namespace"
    
    # Check migration status
    if kubectl get job "$job_name" -n "$namespace" -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}' | grep -q "True"; then
        log_info "Database migrations completed successfully"
    else
        log_error "Database migrations failed"
        kubectl logs "job/$job_name" -n "$namespace"
        exit 1
    fi
}

# Deploy application
deploy_application() {
    log_info "Deploying application..."
    
    local namespace="$NAMESPACE_PREFIX"
    local values_file="$HELM_CHART_PATH/values.yaml"
    
    if [ "$ENVIRONMENT" != "production" ]; then
        namespace="$NAMESPACE_PREFIX-$ENVIRONMENT"
        if [ -f "$HELM_CHART_PATH/values-$ENVIRONMENT.yaml" ]; then
            values_file="$HELM_CHART_PATH/values-$ENVIRONMENT.yaml"
        fi
    else
        if [ -f "$HELM_CHART_PATH/values-prod.yaml" ]; then
            values_file="$HELM_CHART_PATH/values-prod.yaml"
        fi
    fi
    
    local helm_args=(
        "upgrade" "--install" "llm-platform"
        "$HELM_CHART_PATH"
        "--namespace" "$namespace"
        "--values" "$values_file"
        "--set" "image.django.tag=$VERSION"
        "--set" "image.fastapi.tag=$VERSION"
        "--set" "image.fastapiGpu.tag=gpu-$VERSION"
        "--wait" "--timeout=15m"
    )
    
    if [ "$DRY_RUN" = "true" ]; then
        helm_args+=("--dry-run")
    fi
    
    if [ "$ENVIRONMENT" = "production" ]; then
        helm_args+=("--atomic")
    fi
    
    log_info "Running: helm ${helm_args[*]}"
    helm "${helm_args[@]}"
    
    log_info "Application deployed successfully"
}

# Post-deployment verification
verify_deployment() {
    log_info "Verifying deployment..."
    
    local namespace="$NAMESPACE_PREFIX"
    if [ "$ENVIRONMENT" != "production" ]; then
        namespace="$NAMESPACE_PREFIX-$ENVIRONMENT"
    fi
    
    # Wait for deployments to be ready
    log_info "Waiting for deployments to be ready..."
    kubectl wait --for=condition=available --timeout=600s \
        deployment/llm-platform-django \
        deployment/llm-platform-fastapi \
        -n "$namespace"
    
    # Run health checks
    log_info "Running health checks..."
    
    # Django health check
    if kubectl run django-health-check --rm -i --restart=Never \
        --image=curlimages/curl:latest \
        --namespace="$namespace" \
        -- curl -f "http://llm-platform-django:8000/health/" &> /dev/null; then
        log_info "Django service health check passed"
    else
        log_error "Django service health check failed"
        exit 1
    fi
    
    # FastAPI health check
    if kubectl run fastapi-health-check --rm -i --restart=Never \
        --image=curlimages/curl:latest \
        --namespace="$namespace" \
        -- curl -f "http://llm-platform-fastapi:8001/health" &> /dev/null; then
        log_info "FastAPI service health check passed"
    else
        log_error "FastAPI service health check failed"
        exit 1
    fi
    
    log_info "All health checks passed"
}

# Run smoke tests
run_smoke_tests() {
    if [ "$SKIP_TESTS" = "true" ]; then
        log_warn "Skipping smoke tests"
        return
    fi
    
    log_info "Running smoke tests..."
    
    local namespace="$NAMESPACE_PREFIX"
    if [ "$ENVIRONMENT" != "production" ]; then
        namespace="$NAMESPACE_PREFIX-$ENVIRONMENT"
    fi
    
    # Test chat completion endpoint
    kubectl run smoke-test-chat --rm -i --restart=Never \
        --image=curlimages/curl:latest \
        --namespace="$namespace" \
        -- curl -f -X POST "http://llm-platform-fastapi:8001/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d '{"model":"test","messages":[{"role":"user","content":"Hello"}],"max_tokens":1}'
    
    log_info "Smoke tests completed"
}

# Main deployment function
main() {
    log_info "Starting LLM Platform deployment"
    log_info "Environment: $ENVIRONMENT"
    log_info "Version: $VERSION"
    log_info "Dry run: $DRY_RUN"
    
    check_prerequisites
    validate_environment
    create_namespace
    pre_deployment_checks
    
    if [ "$ENVIRONMENT" = "production" ] && [ "$DRY_RUN" != "true" ]; then
        run_migrations
    fi
    
    deploy_application
    
    if [ "$DRY_RUN" != "true" ]; then
        verify_deployment
        run_smoke_tests
    fi
    
    log_info "Deployment completed successfully!"
}

# Handle script interruption
trap 'log_error "Deployment interrupted"; exit 1' INT TERM

# Show help
if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    cat << EOF
LLM Platform Deployment Script

Usage: $0 [environment] [version]

Arguments:
  environment    Target environment (development|staging|production)
  version        Image version tag (default: latest)

Environment Variables:
  DRY_RUN        Set to 'true' for dry run mode
  SKIP_TESTS     Set to 'true' to skip smoke tests

Examples:
  $0 staging v1.2.3
  DRY_RUN=true $0 production latest
  SKIP_TESTS=true $0 development main

EOF
    exit 0
fi

# Run main function
main "$@"