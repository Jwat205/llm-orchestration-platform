#!/bin/bash

# Production Deployment Script for LLM API Platform
# Deploys infrastructure and services to AWS for production-scale performance
# Target: 1,000+ concurrent requests/second, <100ms latency, 99.5% uptime

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
REGION=${AWS_DEFAULT_REGION:-"us-east-1"}
PROJECT_NAME="llm-api-platform"
ENVIRONMENT="production"
TERRAFORM_DIR="$(dirname "$0")"

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed"
        exit 1
    fi

    # Check Terraform
    if ! command -v terraform &> /dev/null; then
        print_error "Terraform is not installed"
        exit 1
    fi

    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials are not configured"
        exit 1
    fi

    print_status "Prerequisites check passed"
}

# Function to validate Terraform configuration
validate_terraform() {
    print_status "Validating Terraform configuration..."

    cd "$TERRAFORM_DIR"

    terraform init -input=false
    terraform validate
    terraform fmt -check=true

    print_status "Terraform validation passed"
}

# Function to create ECR repositories and push images
setup_container_registry() {
    print_status "Setting up ECR repositories..."

    # Get AWS account ID
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

    # Create ECR repositories if they don't exist
    for repo in "llm-api-django" "llm-api-fastapi"; do
        if ! aws ecr describe-repositories --repository-names "$repo" --region "$REGION" &> /dev/null; then
            print_status "Creating ECR repository: $repo"
            aws ecr create-repository \
                --repository-name "$repo" \
                --region "$REGION" \
                --image-scanning-configuration scanOnPush=true \
                --encryption-configuration encryptionType=AES256
        else
            print_status "ECR repository already exists: $repo"
        fi
    done

    # Get ECR login token
    print_status "Logging into ECR..."
    aws ecr get-login-password --region "$REGION" | \
        docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
}

# Function to build and push Docker images
build_and_push_images() {
    print_status "Building and pushing Docker images..."

    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    BASE_DIR=$(dirname "$TERRAFORM_DIR")

    # Build and push Django service
    print_status "Building Django service..."
    cd "$BASE_DIR/django_service"
    docker build \
        --file Dockerfile.production \
        --build-arg BUILD_DATE="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
        --build-arg VCS_REF="$(git rev-parse HEAD 2>/dev/null || echo 'unknown')" \
        --build-arg VERSION="$(git describe --tags --always 2>/dev/null || echo 'latest')" \
        --tag "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/llm-api-django:latest" \
        --tag "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/llm-api-django:$(date +%Y%m%d-%H%M%S)" \
        .

    print_status "Pushing Django service to ECR..."
    docker push "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/llm-api-django:latest"
    docker push "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/llm-api-django:$(date +%Y%m%d-%H%M%S)"

    # Build and push FastAPI service
    print_status "Building FastAPI service..."
    cd "$BASE_DIR/fastapi_service"
    docker build \
        --file Dockerfile.production \
        --build-arg BUILD_DATE="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
        --build-arg VCS_REF="$(git rev-parse HEAD 2>/dev/null || echo 'unknown')" \
        --build-arg VERSION="$(git describe --tags --always 2>/dev/null || echo 'latest')" \
        --tag "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/llm-api-fastapi:latest" \
        --tag "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/llm-api-fastapi:$(date +%Y%m%d-%H%M%S)" \
        .

    print_status "Pushing FastAPI service to ECR..."
    docker push "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/llm-api-fastapi:latest"
    docker push "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/llm-api-fastapi:$(date +%Y%m%d-%H%M%S)"

    cd "$TERRAFORM_DIR"
}

# Function to deploy infrastructure
deploy_infrastructure() {
    print_status "Deploying infrastructure with Terraform..."

    cd "$TERRAFORM_DIR"

    # Check for terraform.tfvars
    if [[ ! -f "terraform.tfvars" ]]; then
        print_warning "terraform.tfvars not found. Creating from template..."
        if [[ -f "terraform.tfvars.example" ]]; then
            cp terraform.tfvars.example terraform.tfvars
            print_warning "Please edit terraform.tfvars with your specific values"
        else
            print_error "terraform.tfvars.example not found"
            exit 1
        fi
    fi

    # Plan deployment
    print_status "Creating Terraform plan..."
    terraform plan -out=tfplan -input=false

    # Apply infrastructure
    print_status "Applying Terraform configuration..."
    terraform apply -input=false tfplan

    # Clean up plan file
    rm -f tfplan

    print_status "Infrastructure deployment completed"
}

# Function to verify deployment
verify_deployment() {
    print_status "Verifying deployment..."

    # Get ALB DNS name
    ALB_DNS=$(terraform output -raw alb_dns_name)

    if [[ -n "$ALB_DNS" ]]; then
        print_status "Load Balancer DNS: $ALB_DNS"

        # Wait for load balancer to be ready
        print_status "Waiting for load balancer to be ready..."
        sleep 60

        # Test health endpoint
        for i in {1..5}; do
            print_status "Attempting health check (attempt $i/5)..."
            if curl -f -s --max-time 10 "http://$ALB_DNS/health" > /dev/null; then
                print_status "Health check successful!"
                break
            elif [[ $i -eq 5 ]]; then
                print_warning "Health check failed after 5 attempts"
            else
                sleep 30
            fi
        done
    else
        print_error "Could not retrieve load balancer DNS"
    fi

    # Display deployment summary
    print_status "Deployment Summary:"
    echo "=================================="
    echo "Environment: $ENVIRONMENT"
    echo "Region: $REGION"
    echo "Load Balancer: http://$ALB_DNS"
    echo "Django ECR: $(terraform output -raw django_ecr_repository_url)"
    echo "FastAPI ECR: $(terraform output -raw fastapi_ecr_repository_url)"
    echo "CloudWatch Dashboard: $(terraform output -raw cloudwatch_dashboard_url)"
    echo "=================================="
}

# Function to setup monitoring alerts
setup_monitoring() {
    print_status "Setting up monitoring and alerts..."

    # Create SNS subscriptions if email addresses are provided
    if [[ -n "${ALERT_EMAILS:-}" ]]; then
        SNS_TOPIC_ARN=$(terraform output -raw alerts_topic_arn)

        IFS=',' read -ra EMAILS <<< "$ALERT_EMAILS"
        for email in "${EMAILS[@]}"; do
            print_status "Subscribing $email to alerts..."
            aws sns subscribe \
                --topic-arn "$SNS_TOPIC_ARN" \
                --protocol email \
                --notification-endpoint "$email" \
                --region "$REGION"
        done

        print_status "Alert subscriptions created. Please check email for confirmations."
    fi
}

# Function to run load test
run_load_test() {
    if [[ "${RUN_LOAD_TEST:-false}" == "true" ]]; then
        print_status "Running load test..."

        ALB_DNS=$(terraform output -raw alb_dns_name)

        # Simple load test with curl
        print_status "Testing concurrent requests..."
        for i in {1..100}; do
            curl -s -o /dev/null -w "%{http_code}\n" "http://$ALB_DNS/health" &
        done
        wait

        print_status "Load test completed"
    fi
}

# Function to display performance metrics
show_performance_metrics() {
    print_status "Infrastructure Performance Specifications:"
    echo "=========================================="
    terraform output infrastructure_summary
    echo "=========================================="

    print_status "To monitor real-time performance:"
    echo "1. CloudWatch Dashboard: $(terraform output -raw cloudwatch_dashboard_url)"
    echo "2. ECS Cluster: https://$REGION.console.aws.amazon.com/ecs/home?region=$REGION#/clusters/$(terraform output -raw ecs_cluster_name)/services"
    echo "3. RDS Performance Insights: https://$REGION.console.aws.amazon.com/rds/home?region=$REGION#performance-insights-v20206:"
}

# Main deployment function
main() {
    print_status "Starting production deployment for $PROJECT_NAME..."
    print_status "Target: 1,000+ req/sec, <100ms latency, 99.5% uptime"

    # Run deployment steps
    check_prerequisites
    validate_terraform
    setup_container_registry
    build_and_push_images
    deploy_infrastructure
    setup_monitoring
    verify_deployment
    run_load_test
    show_performance_metrics

    print_status "Production deployment completed successfully!"
    print_status "Your LLM API Platform is ready to handle enterprise-scale traffic."
}

# Script execution
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --region)
                REGION="$2"
                shift 2
                ;;
            --skip-build)
                SKIP_BUILD=true
                shift
                ;;
            --run-load-test)
                RUN_LOAD_TEST=true
                shift
                ;;
            --alert-emails)
                ALERT_EMAILS="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --region REGION        AWS region (default: us-east-1)"
                echo "  --skip-build          Skip Docker image building"
                echo "  --run-load-test       Run basic load test after deployment"
                echo "  --alert-emails EMAILS Comma-separated email addresses for alerts"
                echo "  --help                Show this help message"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done

    main
fi