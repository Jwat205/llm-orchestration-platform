#!/bin/bash

# LLM Platform Backup Script
# Usage: ./backup.sh [environment] [backup-type]

set -euo pipefail

# Configuration
ENVIRONMENT="${1:-staging}"
BACKUP_TYPE="${2:-full}"  # full, database, config
NAMESPACE_PREFIX="llm-platform"
BACKUP_DIR="${BACKUP_DIR:-/tmp/llm-platform-backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

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

# Create backup directory
create_backup_directory() {
    local timestamp=$(date +%Y%m%d-%H%M%S)
    local backup_path="$BACKUP_DIR/$ENVIRONMENT/$timestamp"
    
    mkdir -p "$backup_path"
    echo "$backup_path"
}

# Backup database
backup_database() {
    local backup_path="$1"
    local namespace=$(get_namespace)
    
    log_info "Backing up database..."
    
    # Create database dump
    kubectl exec -n "$namespace" deployment/llm-platform-django -- \
        python manage.py dumpdata --natural-foreign --natural-primary \
        --exclude auth.permission --exclude contenttypes \
        --exclude sessions --exclude admin.logentry \
        --output /tmp/db-backup.json
    
    # Copy database dump to backup directory
    kubectl cp "$namespace/$(kubectl get pods -n "$namespace" -l app=django -o jsonpath='{.items[0].metadata.name}'):/tmp/db-backup.json" \
        "$backup_path/database-dump.json"
    
    # Backup PostgreSQL using pg_dump if available
    if kubectl exec -n "$namespace" deployment/postgres-deployment -- which pg_dump &> /dev/null; then
        kubectl exec -n "$namespace" deployment/postgres-deployment -- \
            pg_dump -U "$DATABASE_USER" "$DATABASE_NAME" > "$backup_path/postgres-dump.sql"
    fi
    
    log_info "✓ Database backup completed"
}

# Backup configuration
backup_configuration() {
    local backup_path="$1"
    local namespace=$(get_namespace)
    
    log_info "Backing up configuration..."
    
    mkdir -p "$backup_path/config"
    
    # Backup ConfigMaps
    kubectl get configmaps -n "$namespace" -o yaml > "$backup_path/config/configmaps.yaml"
    
    # Backup Secrets (without sensitive data)
    kubectl get secrets -n "$namespace" -o yaml | \
        sed 's/data:/data: # REDACTED/' > "$backup_path/config/secrets-metadata.yaml"
    
    # Backup Helm values
    if helm get values llm-platform -n "$namespace" &> /dev/null; then
        helm get values llm-platform -n "$namespace" > "$backup_path/config/helm-values.yaml"
        helm get manifest llm-platform -n "$namespace" > "$backup_path/config/helm-manifest.yaml"
    fi
    
    # Backup Kubernetes manifests
    kubectl get deployments -n "$namespace" -o yaml > "$backup_path/config/deployments.yaml"
    kubectl get services -n "$namespace" -o yaml > "$backup_path/config/services.yaml"
    kubectl get ingress -n "$namespace" -o yaml > "$backup_path/config/ingress.yaml"
    kubectl get hpa -n "$namespace" -o yaml > "$backup_path/config/hpa.yaml"
    
    log_info "✓ Configuration backup completed"
}

# Backup persistent volumes
backup_persistent_volumes() {
    local backup_path="$1"
    local namespace=$(get_namespace)
    
    log_info "Backing up persistent volumes..."
    
    mkdir -p "$backup_path/volumes"
    
    # Get list of PVCs
    local pvcs=$(kubectl get pvc -n "$namespace" -o jsonpath='{.items[*].metadata.name}')
    
    for pvc in $pvcs; do
        log_info "Backing up PVC: $pvc"
        
        # Create a backup pod to copy data
        kubectl run "backup-$pvc" --rm -i --restart=Never \
            --image=busybox:latest \
            --namespace="$namespace" \
            --overrides='
            {
                "spec": {
                    "containers": [
                        {
                            "name": "backup",
                            "image": "busybox:latest",
                            "command": ["tar", "czf", "/backup/'$pvc'.tar.gz", "-C", "/data", "."],
                            "volumeMounts": [
                                {
                                    "name": "data",
                                    "mountPath": "/data"
                                },
                                {
                                    "name": "backup",
                                    "mountPath": "/backup"
                                }
                            ]
                        }
                    ],
                    "volumes": [
                        {
                            "name": "data",
                            "persistentVolumeClaim": {
                                "claimName": "'$pvc'"
                            }
                        },
                        {
                            "name": "backup",
                            "emptyDir": {}
                        }
                    ]
                }
            }' -- /bin/sh -c "sleep 300"
        
        # Copy the backup file
        kubectl cp "$namespace/backup-$pvc:/backup/$pvc.tar.gz" "$backup_path/volumes/$pvc.tar.gz"
    done
    
    log_info "✓ Persistent volumes backup completed"
}

# Backup model files
backup_models() {
    local backup_path="$1"
    local namespace=$(get_namespace)
    
    log_info "Backing up model files..."
    
    mkdir -p "$backup_path/models"
    
    # Get FastAPI pod for model access
    local fastapi_pod=$(kubectl get pods -n "$namespace" -l app=fastapi -o jsonpath='{.items[0].metadata.name}')
    
    if [ -n "$fastapi_pod" ]; then
        # Create tar archive of models directory
        kubectl exec -n "$namespace" "$fastapi_pod" -- \
            tar czf /tmp/models-backup.tar.gz -C /app/models . 2>/dev/null || log_warn "No models found to backup"
        
        # Copy models backup
        kubectl cp "$namespace/$fastapi_pod:/tmp/models-backup.tar.gz" \
            "$backup_path/models/models-backup.tar.gz" 2>/dev/null || log_warn "Could not copy models backup"
    fi
    
    log_info "✓ Model files backup completed"
}

# Backup monitoring data
backup_monitoring() {
    local backup_path="$1"
    local namespace="$NAMESPACE_PREFIX-monitoring"
    
    log_info "Backing up monitoring configuration..."
    
    mkdir -p "$backup_path/monitoring"
    
    # Backup Prometheus configuration
    if kubectl get configmap prometheus-config -n "$namespace" &> /dev/null; then
        kubectl get configmap prometheus-config -n "$namespace" -o yaml > \
            "$backup_path/monitoring/prometheus-config.yaml"
    fi
    
    # Backup Grafana configuration
    if kubectl get configmap grafana-config -n "$namespace" &> /dev/null; then
        kubectl get configmap grafana-config -n "$namespace" -o yaml > \
            "$backup_path/monitoring/grafana-config.yaml"
    fi
    
    # Backup alerting rules
    if kubectl get configmap alert-rules -n "$namespace" &> /dev/null; then
        kubectl get configmap alert-rules -n "$namespace" -o yaml > \
            "$backup_path/monitoring/alert-rules.yaml"
    fi
    
    log_info "✓ Monitoring backup completed"
}

# Create backup manifest
create_backup_manifest() {
    local backup_path="$1"
    
    cat > "$backup_path/backup-manifest.yaml" << EOF
apiVersion: backup.llm-platform.com/v1
kind: BackupManifest
metadata:
  name: $(basename "$backup_path")
  timestamp: $(date -Iseconds)
spec:
  environment: $ENVIRONMENT
  namespace: $(get_namespace)
  backupType: $BACKUP_TYPE
  components:
    database: $([ "$BACKUP_TYPE" = "full" ] || [ "$BACKUP_TYPE" = "database" ] && echo "true" || echo "false")
    configuration: $([ "$BACKUP_TYPE" = "full" ] || [ "$BACKUP_TYPE" = "config" ] && echo "true" || echo "false")
    persistentVolumes: $([ "$BACKUP_TYPE" = "full" ] && echo "true" || echo "false")
    models: $([ "$BACKUP_TYPE" = "full" ] && echo "true" || echo "false")
    monitoring: $([ "$BACKUP_TYPE" = "full" ] && echo "true" || echo "false")
  version:
    kubernetes: $(kubectl version --client -o json | jq -r .clientVersion.gitVersion)
    helm: $(helm version --short)
status:
  phase: Completed
  size: $(du -sh "$backup_path" | cut -f1)
EOF
    
    log_info "✓ Backup manifest created"
}

# Cleanup old backups
cleanup_old_backups() {
    log_info "Cleaning up backups older than $RETENTION_DAYS days..."
    
    find "$BACKUP_DIR/$ENVIRONMENT" -type d -mtime +$RETENTION_DAYS -exec rm -rf {} \; 2>/dev/null || true
    
    log_info "✓ Old backups cleaned up"
}

# Verify backup integrity
verify_backup() {
    local backup_path="$1"
    local failed=0
    
    log_info "Verifying backup integrity..."
    
    # Check if backup directory exists and is not empty
    if [ ! -d "$backup_path" ] || [ -z "$(ls -A "$backup_path")" ]; then
        log_error "Backup directory is empty or does not exist"
        return 1
    fi
    
    # Verify database backup
    if [ -f "$backup_path/database-dump.json" ]; then
        if jq empty "$backup_path/database-dump.json" 2>/dev/null; then
            log_info "✓ Database backup is valid JSON"
        else
            log_error "✗ Database backup is invalid JSON"
            failed=1
        fi
    fi
    
    # Verify configuration files
    if [ -d "$backup_path/config" ]; then
        for yaml_file in "$backup_path/config"/*.yaml; do
            if [ -f "$yaml_file" ]; then
                if kubectl --dry-run=client apply -f "$yaml_file" &> /dev/null; then
                    log_info "✓ $(basename "$yaml_file") is valid"
                else
                    log_warn "⚠ $(basename "$yaml_file") may have issues"
                fi
            fi
        done
    fi
    
    # Verify tar archives
    for tar_file in $(find "$backup_path" -name "*.tar.gz"); do
        if tar -tzf "$tar_file" &> /dev/null; then
            log_info "✓ $(basename "$tar_file") is a valid archive"
        else
            log_error "✗ $(basename "$tar_file") is corrupted"
            failed=1
        fi
    done
    
    return $failed
}

# Main backup function
main() {
    log_info "Starting LLM Platform backup"
    log_info "Environment: $ENVIRONMENT"
    log_info "Backup type: $BACKUP_TYPE"
    
    # Check prerequisites
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    # Create backup directory
    local backup_path=$(create_backup_directory)
    log_info "Backup directory: $backup_path"
    
    # Perform backup based on type
    case "$BACKUP_TYPE" in
        "full")
            backup_database "$backup_path"
            backup_configuration "$backup_path"
            backup_persistent_volumes "$backup_path"
            backup_models "$backup_path"
            backup_monitoring "$backup_path"
            ;;
        "database")
            backup_database "$backup_path"
            ;;
        "config")
            backup_configuration "$backup_path"
            ;;
        *)
            log_error "Invalid backup type: $BACKUP_TYPE"
            log_error "Valid types: full, database, config"
            exit 1
            ;;
    esac
    
    # Create backup manifest
    create_backup_manifest "$backup_path"
    
    # Verify backup
    if verify_backup "$backup_path"; then
        log_info "✅ Backup verification passed"
    else
        log_error "❌ Backup verification failed"
        exit 1
    fi
    
    # Cleanup old backups
    cleanup_old_backups
    
    local backup_size=$(du -sh "$backup_path" | cut -f1)
    log_info "✅ Backup completed successfully!"
    log_info "Backup location: $backup_path"
    log_info "Backup size: $backup_size"
}

# Show help
if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    cat << EOF
LLM Platform Backup Script

Usage: $0 [environment] [backup-type]

Arguments:
  environment    Target environment (development|staging|production)
  backup-type    Type of backup (full|database|config)

Environment Variables:
  BACKUP_DIR     Backup directory (default: /tmp/llm-platform-backups)
  RETENTION_DAYS Days to retain backups (default: 7)

Examples:
  $0 production full
  $0 staging database
  BACKUP_DIR=/backups $0 production full

EOF
    exit 0
fi

# Run main function
main "$@"