#!/bin/bash

# Rollback Script for Django EKS Deployment
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="django-app"
DEPLOYMENT_NAME="django-deployment"

echo -e "${GREEN}Django EKS Rollback Script${NC}"

# Check if kubectl is configured
if ! kubectl cluster-info >/dev/null 2>&1; then
    echo -e "${RED}Error: kubectl is not configured or cluster is not accessible${NC}"
    exit 1
fi

# Function to show rollout history
show_history() {
    echo -e "${YELLOW}Deployment rollout history:${NC}"
    kubectl rollout history deployment/${DEPLOYMENT_NAME} -n ${NAMESPACE}
}

# Function to rollback to previous version
rollback_previous() {
    echo -e "${YELLOW}Rolling back to previous version...${NC}"
    kubectl rollout undo deployment/${DEPLOYMENT_NAME} -n ${NAMESPACE}
    
    echo -e "${YELLOW}Waiting for rollback to complete...${NC}"
    kubectl rollout status deployment/${DEPLOYMENT_NAME} -n ${NAMESPACE} --timeout=300s
    
    echo -e "${GREEN}Rollback to previous version completed!${NC}"
}

# Function to rollback to specific revision
rollback_revision() {
    local revision=$1
    echo -e "${YELLOW}Rolling back to revision ${revision}...${NC}"
    kubectl rollout undo deployment/${DEPLOYMENT_NAME} -n ${NAMESPACE} --to-revision=${revision}
    
    echo -e "${YELLOW}Waiting for rollback to complete...${NC}"
    kubectl rollout status deployment/${DEPLOYMENT_NAME} -n ${NAMESPACE} --timeout=300s
    
    echo -e "${GREEN}Rollback to revision ${revision} completed!${NC}"
}

# Function to get current status
show_status() {
    echo -e "${YELLOW}Current deployment status:${NC}"
    kubectl get deployment ${DEPLOYMENT_NAME} -n ${NAMESPACE}
    echo
    kubectl get pods -n ${NAMESPACE} -l app=django
    echo
    kubectl rollout status deployment/${DEPLOYMENT_NAME} -n ${NAMESPACE}
}

# Main menu
case "${1:-menu}" in
    "menu")
        echo "Usage: $0 [command]"
        echo
        echo "Commands:"
        echo "  history     - Show rollout history"
        echo "  previous    - Rollback to previous version"
        echo "  revision N  - Rollback to specific revision N"
        echo "  status      - Show current deployment status"
        echo
        
        show_history
        echo
        show_status
        echo
        
        read -p "Enter revision number to rollback to (or 'p' for previous, 'q' to quit): " choice
        
        case $choice in
            [Qq])
                echo -e "${YELLOW}Rollback cancelled${NC}"
                exit 0
                ;;
            [Pp])
                rollback_previous
                ;;
            [0-9]*)
                rollback_revision $choice
                ;;
            *)
                echo -e "${RED}Invalid choice${NC}"
                exit 1
                ;;
        esac
        ;;
    "history")
        show_history
        ;;
    "previous")
        rollback_previous
        ;;
    "revision")
        if [ -z "$2" ]; then
            echo -e "${RED}Error: Please specify revision number${NC}"
            exit 1
        fi
        rollback_revision $2
        ;;
    "status")
        show_status
        ;;
    *)
        echo -e "${RED}Error: Unknown command $1${NC}"
        echo "Run '$0' without arguments to see available commands"
        exit 1
        ;;
esac

# Show final status
echo
echo -e "${YELLOW}Final status after operation:${NC}"
show_status

# Run health check
if [ -f "./scripts/health-check.sh" ]; then
    echo
    echo -e "${YELLOW}Running health check...${NC}"
    ./scripts/health-check.sh
fi