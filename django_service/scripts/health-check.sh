#!/bin/bash

# Health Check Script for Django EKS Deployment
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="django-app"
SERVICE_NAME="django-service"

echo -e "${GREEN}Running health checks for Django EKS deployment...${NC}"

# Check if kubectl is configured
if ! kubectl cluster-info >/dev/null 2>&1; then
    echo -e "${RED}Error: kubectl is not configured or cluster is not accessible${NC}"
    exit 1
fi

# Function to check resource status
check_resource() {
    local resource_type=$1
    local resource_name=$2
    local namespace=$3
    
    echo -e "${YELLOW}Checking ${resource_type}/${resource_name}...${NC}"
    
    if kubectl get ${resource_type} ${resource_name} -n ${namespace} >/dev/null 2>&1; then
        echo -e "${GREEN}✓ ${resource_type}/${resource_name} exists${NC}"
        
        # Get status based on resource type
        case ${resource_type} in
            "deployment")
                local ready=$(kubectl get deployment ${resource_name} -n ${namespace} -o jsonpath='{.status.readyReplicas}')
                local desired=$(kubectl get deployment ${resource_name} -n ${namespace} -o jsonpath='{.spec.replicas}')
                if [ "${ready}" == "${desired}" ]; then
                    echo -e "${GREEN}✓ Deployment is ready (${ready}/${desired} replicas)${NC}"
                else
                    echo -e "${RED}✗ Deployment not ready (${ready}/${desired} replicas)${NC}"
                    return 1
                fi
                ;;
            "service")
                local cluster_ip=$(kubectl get service ${resource_name} -n ${namespace} -o jsonpath='{.spec.clusterIP}')
                echo -e "${GREEN}✓ Service cluster IP: ${cluster_ip}${NC}"
                ;;
            "ingress")
                local ingress_ip=$(kubectl get ingress ${resource_name} -n ${namespace} -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
                if [ ! -z "${ingress_ip}" ]; then
                    echo -e "${GREEN}✓ Ingress load balancer: ${ingress_ip}${NC}"
                else
                    echo -e "${YELLOW}⚠ Ingress load balancer not yet assigned${NC}"
                fi
                ;;
        esac
    else
        echo -e "${RED}✗ ${resource_type}/${resource_name} not found${NC}"
        return 1
    fi
}

# Check namespace
echo -e "${YELLOW}Checking namespace...${NC}"
if kubectl get namespace ${NAMESPACE} >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Namespace ${NAMESPACE} exists${NC}"
else
    echo -e "${RED}✗ Namespace ${NAMESPACE} not found${NC}"
    exit 1
fi

# Check deployments
check_resource "deployment" "django-deployment" ${NAMESPACE}

# Check services
check_resource "service" "django-service" ${NAMESPACE}

# Check ingress
check_resource "ingress" "django-ingress" ${NAMESPACE}

# Check HPA
check_resource "hpa" "django-hpa" ${NAMESPACE}

# Check pods
echo -e "${YELLOW}Checking pods...${NC}"
pod_status=$(kubectl get pods -n ${NAMESPACE} -l app=django --no-headers)
if [ ! -z "${pod_status}" ]; then
    echo -e "${GREEN}✓ Django pods:${NC}"
    kubectl get pods -n ${NAMESPACE} -l app=django
    
    # Check if all pods are running
    running_pods=$(kubectl get pods -n ${NAMESPACE} -l app=django --field-selector=status.phase=Running --no-headers | wc -l)
    total_pods=$(kubectl get pods -n ${NAMESPACE} -l app=django --no-headers | wc -l)
    
    if [ "${running_pods}" == "${total_pods}" ]; then
        echo -e "${GREEN}✓ All pods are running (${running_pods}/${total_pods})${NC}"
    else
        echo -e "${RED}✗ Not all pods are running (${running_pods}/${total_pods})${NC}"
        echo -e "${YELLOW}Pod details:${NC}"
        kubectl describe pods -n ${NAMESPACE} -l app=django
    fi
else
    echo -e "${RED}✗ No Django pods found${NC}"
    exit 1
fi

# Check configmaps and secrets
echo -e "${YELLOW}Checking configuration...${NC}"
if kubectl get configmap django-config -n ${NAMESPACE} >/dev/null 2>&1; then
    echo -e "${GREEN}✓ ConfigMap django-config exists${NC}"
else
    echo -e "${RED}✗ ConfigMap django-config not found${NC}"
fi

if kubectl get secret django-secrets -n ${NAMESPACE} >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Secret django-secrets exists${NC}"
else
    echo -e "${RED}✗ Secret django-secrets not found${NC}"
fi

# Test service connectivity
echo -e "${YELLOW}Testing service connectivity...${NC}"
service_ip=$(kubectl get service ${SERVICE_NAME} -n ${NAMESPACE} -o jsonpath='{.spec.clusterIP}')
service_port=$(kubectl get service ${SERVICE_NAME} -n ${NAMESPACE} -o jsonpath='{.spec.ports[0].port}')

# Port forward to test the service
echo -e "${YELLOW}Testing health endpoint...${NC}"
kubectl port-forward service/${SERVICE_NAME} 8080:${service_port} -n ${NAMESPACE} &
PF_PID=$!
sleep 5

# Test health endpoint
if curl -f http://localhost:8080/health/ >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Health endpoint is responding${NC}"
else
    echo -e "${RED}✗ Health endpoint is not responding${NC}"
fi

# Kill port-forward
kill $PF_PID 2>/dev/null || true

# Check ingress controller
echo -e "${YELLOW}Checking ingress controller...${NC}"
if kubectl get pods -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx >/dev/null 2>&1; then
    nginx_pods=$(kubectl get pods -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --field-selector=status.phase=Running --no-headers | wc -l)
    if [ "${nginx_pods}" -gt 0 ]; then
        echo -e "${GREEN}✓ Nginx ingress controller is running${NC}"
    else
        echo -e "${RED}✗ Nginx ingress controller is not running${NC}"
    fi
else
    echo -e "${RED}✗ Nginx ingress controller not found${NC}"
fi

# Check load balancer
echo -e "${YELLOW}Checking load balancer...${NC}"
lb_hostname=$(kubectl get ingress django-ingress -n ${NAMESPACE} -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)
if [ ! -z "${lb_hostname}" ]; then
    echo -e "${GREEN}✓ Load balancer hostname: ${lb_hostname}${NC}"
    
    # Test external connectivity
    echo -e "${YELLOW}Testing external connectivity...${NC}"
    if curl -f -k https://${lb_hostname}/health/ >/dev/null 2>&1; then
        echo -e "${GREEN}✓ External health endpoint is responding${NC}"
    else
        echo -e "${YELLOW}⚠ External health endpoint is not responding (might need time to propagate)${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Load balancer hostname not yet assigned${NC}"
fi

# Resource usage
echo -e "${YELLOW}Checking resource usage...${NC}"
kubectl top pods -n ${NAMESPACE} 2>/dev/null || echo -e "${YELLOW}⚠ Metrics server not available${NC}"

# Recent events
echo -e "${YELLOW}Recent events in namespace:${NC}"
kubectl get events -n ${NAMESPACE} --sort-by='.lastTimestamp' | tail -10

echo -e "${GREEN}Health check completed!${NC}"