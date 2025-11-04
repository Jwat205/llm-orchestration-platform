#!/bin/bash

# LLM Platform Health Check Script
# Usage: ./health-check.sh [environment]

set -euo pipefail

# Configuration
ENVIRONMENT="${1:-staging}"
NAMESPACE_PREFIX="llm-platform"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

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

# Get namespace
get_namespace() {
    local namespace="$NAMESPACE_PREFIX"
    if [ "$ENVIRONMENT" != "production" ]; then
        namespace="$NAMESPACE_PREFIX-$ENVIRONMENT"
    fi
    echo "$namespace"
}

# Check Kubernetes connectivity
check_k8s_connectivity() {
    log_info "Checking Kubernetes connectivity..."
    
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        return 1
    fi
    
    log_info "✓ Kubernetes connectivity OK"
    return 0
}

# Check namespace
check_namespace() {
    local namespace=$(get_namespace)
    
    log_info "Checking namespace: $namespace"
    
    if ! kubectl get namespace "$namespace" &> /dev/null; then
        log_error "Namespace $namespace does not exist"
        return 1
    fi
    
    log_info "✓ Namespace OK"
    return 0
}

# Check deployments
check_deployments() {
    local namespace=$(get_namespace)
    local failed=0
    
    log_info "Checking deployments in namespace: $namespace"
    
    # List of expected deployments
    local deployments=("llm-platform-django" "llm-platform-fastapi")
    
    for deployment in "${deployments[@]}"; do
        if kubectl get deployment "$deployment" -n "$namespace" &> /dev/null; then
            local ready=$(kubectl get deployment "$deployment" -n "$namespace" -o jsonpath='{.status.readyReplicas}')
            local desired=$(kubectl get deployment "$deployment" -n "$namespace" -o jsonpath='{.spec.replicas}')
            
            if [ "$ready" = "$desired" ] && [ "$ready" -gt 0 ]; then
                log_info "✓ $deployment: $ready/$desired replicas ready"
            else
                log_error "✗ $deployment: $ready/$desired replicas ready"
                failed=1
            fi
        else
            log_error "✗ Deployment $deployment not found"
            failed=1
        fi
    done
    
    return $failed
}

# Check services
check_services() {
    local namespace=$(get_namespace)
    local failed=0
    
    log_info "Checking services in namespace: $namespace"
    
    local services=("llm-platform-django" "llm-platform-fastapi")
    
    for service in "${services[@]}"; do
        if kubectl get service "$service" -n "$namespace" &> /dev/null; then
            local endpoints=$(kubectl get endpoints "$service" -n "$namespace" -o jsonpath='{.subsets[*].addresses[*].ip}' | wc -w)
            
            if [ "$endpoints" -gt 0 ]; then
                log_info "✓ $service: $endpoints endpoints"
            else
                log_error "✗ $service: no endpoints"
                failed=1
            fi
        else
            log_error "✗ Service $service not found"
            failed=1
        fi
    done
    
    return $failed
}

# Check pods
check_pods() {
    local namespace=$(get_namespace)
    local failed=0
    
    log_info "Checking pods in namespace: $namespace"
    
    # Get all pods with the app label
    local pods=$(kubectl get pods -n "$namespace" -l app.kubernetes.io/name=llm-platform -o jsonpath='{.items[*].metadata.name}')
    
    if [ -z "$pods" ]; then
        log_error "✗ No pods found"
        return 1
    fi
    
    for pod in $pods; do
        local status=$(kubectl get pod "$pod" -n "$namespace" -o jsonpath='{.status.phase}')
        local ready=$(kubectl get pod "$pod" -n "$namespace" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')
        
        if [ "$status" = "Running" ] && [ "$ready" = "True" ]; then
            log_info "✓ $pod: Running and Ready"
        else
            log_error "✗ $pod: $status (Ready: $ready)"
            failed=1
            
            # Show recent logs for failed pods
            log_info "Recent logs for $pod:"
            kubectl logs --tail=10 "$pod" -n "$namespace" || true
        fi
    done
    
    return $failed
}

# Check database connectivity
check_database() {
    local namespace=$(get_namespace)
    
    log_info "Checking database connectivity..."
    
    # Try to connect to database through Django
    if kubectl exec -n "$namespace" deployment/llm-platform-django -- \
        python manage.py check --database default &> /dev/null; then
        log_info "✓ Database connectivity OK"
        return 0
    else
        log_error "✗ Database connectivity failed"
        return 1
    fi
}

# Check Redis connectivity
check_redis() {
    local namespace=$(get_namespace)
    
    log_info "Checking Redis connectivity..."
    
    # Check if Redis service is available
    if kubectl exec -n "$namespace" deployment/llm-platform-django -- \
        python -c "import redis; r=redis.Redis(host='redis-service'); r.ping()" &> /dev/null; then
        log_info "✓ Redis connectivity OK"
        return 0
    else
        log_error "✗ Redis connectivity failed"
        return 1
    fi
}

# Check HTTP endpoints
check_http_endpoints() {
    local namespace=$(get_namespace)
    local failed=0
    
    log_info "Checking HTTP endpoints..."
    
    # Django health endpoint
    if kubectl run health-check-django --rm -i --restart=Never \
        --image=curlimages/curl:latest \
        --namespace="$namespace" \
        -- curl -f -s "http://llm-platform-django:8000/health/" &> /dev/null; then
        log_info "✓ Django health endpoint OK"
    else
        log_error "✗ Django health endpoint failed"
        failed=1
    fi
    
    # FastAPI health endpoint
    if kubectl run health-check-fastapi --rm -i --restart=Never \
        --image=curlimages/curl:latest \
        --namespace="$namespace" \
        -- curl -f -s "http://llm-platform-fastapi:8001/health" &> /dev/null; then
        log_info "✓ FastAPI health endpoint OK"
    else
        log_error "✗ FastAPI health endpoint failed"
        failed=1
    fi
    
    return $failed
}

# Check API functionality
check_api_functionality() {
    local namespace=$(get_namespace)
    local failed=0
    
    log_info "Checking API functionality..."
    
    # Test models endpoint
    if kubectl run api-check-models --rm -i --restart=Never \
        --image=curlimages/curl:latest \
        --namespace="$namespace" \
        -- curl -f -s "http://llm-platform-fastapi:8001/v1/models" &> /dev/null; then
        log_info "✓ Models endpoint OK"
    else
        log_warn "⚠ Models endpoint failed (may be initializing)"
    fi
    
    # Test chat completions endpoint
    if kubectl run api-check-chat --rm -i --restart=Never \
        --image=curlimages/curl:latest \
        --namespace="$namespace" \
        -- curl -f -s -X POST "http://llm-platform-fastapi:8001/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d '{"model":"test","messages":[{"role":"user","content":"ping"}],"max_tokens":1}' &> /dev/null; then
        log_info "✓ Chat completions endpoint OK"
    else
        log_warn "⚠ Chat completions endpoint failed (may be initializing)"
    fi
    
    return $failed
}

# Check resource usage
check_resource_usage() {
    local namespace=$(get_namespace)
    
    log_info "Checking resource usage..."
    
    # Get resource usage for pods
    log_info "Pod resource usage:"
    kubectl top pods -n "$namespace" --containers 2>/dev/null || log_warn "Metrics server not available"
    
    # Check for resource constraints
    local pods=$(kubectl get pods -n "$namespace" -l app.kubernetes.io/name=llm-platform -o jsonpath='{.items[*].metadata.name}')
    
    for pod in $pods; do
        local cpu_requests=$(kubectl get pod "$pod" -n "$namespace" -o jsonpath='{.spec.containers[*].resources.requests.cpu}')
        local memory_requests=$(kubectl get pod "$pod" -n "$namespace" -o jsonpath='{.spec.containers[*].resources.requests.memory}')
        local cpu_limits=$(kubectl get pod "$pod" -n "$namespace" -o jsonpath='{.spec.containers[*].resources.limits.cpu}')
        local memory_limits=$(kubectl get pod "$pod" -n "$namespace" -o jsonpath='{.spec.containers[*].resources.limits.memory}')
        
        log_info "$pod resources - CPU: $cpu_requests/$cpu_limits, Memory: $memory_requests/$memory_limits"
    done
}

# Generate health report
generate_report() {
    local failed_checks=0
    
    log_info "==================== HEALTH CHECK REPORT ===================="
    log_info "Environment: $ENVIRONMENT"
    log_info "Namespace: $(get_namespace)"
    log_info "Timestamp: $(date)"
    log_info "=============================================================="
    
    check_k8s_connectivity || ((failed_checks++))
    check_namespace || ((failed_checks++))
    check_deployments || ((failed_checks++))
    check_services || ((failed_checks++))
    check_pods || ((failed_checks++))
    check_database || ((failed_checks++))
    check_redis || ((failed_checks++))
    check_http_endpoints || ((failed_checks++))
    check_api_functionality || ((failed_checks++))
    check_resource_usage
    
    log_info "=============================================================="
    
    if [ $failed_checks -eq 0 ]; then
        log_info "✅ All health checks passed!"
        return 0
    else
        log_error "❌ $failed_checks health check(s) failed"
        return 1
    fi
}

# Show help
if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    cat << EOF
LLM Platform Health Check Script

Usage: $0 [environment]

Arguments:
  environment    Target environment (development|staging|production)

Examples:
  $0 staging
  $0 production

EOF
    exit 0
fi

# Main execution
generate_report