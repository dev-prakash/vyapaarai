#!/bin/bash

# VyaparAI AWS Deployment Script
# Handles complete deployment pipeline for serverless architecture

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
AWS_REGION="ap-south-1"
ECR_REPOSITORY="vyaparai-api"
DOCKER_IMAGE_TAG="latest"

# Default values
ENVIRONMENT="dev"
STAGE="dev"
SKIP_TESTS=false
SKIP_BUILD=false
SKIP_INFRASTRUCTURE=false
FORCE_DEPLOY=false

# Function to print colored output
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

# Function to show usage
show_usage() {
    cat << EOF
VyaparAI AWS Deployment Script

Usage: $0 [OPTIONS]

Options:
    -e, --environment ENV     Environment to deploy (dev, staging, prod) [default: dev]
    -s, --stage STAGE         Serverless stage [default: dev]
    -r, --region REGION       AWS region [default: ap-south-1]
    -t, --tag TAG             Docker image tag [default: latest]
    --skip-tests              Skip running tests before deployment
    --skip-build              Skip building Docker image
    --skip-infrastructure     Skip infrastructure deployment
    --force                   Force deployment without confirmation
    -h, --help                Show this help message

Examples:
    $0 -e dev -s dev                    # Deploy to development
    $0 -e staging -s staging            # Deploy to staging
    $0 -e prod -s prod --force          # Deploy to production
    $0 --skip-tests --skip-build        # Deploy without tests and build

EOF
}

# Function to parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -s|--stage)
                STAGE="$2"
                shift 2
                ;;
            -r|--region)
                AWS_REGION="$2"
                shift 2
                ;;
            -t|--tag)
                DOCKER_IMAGE_TAG="$2"
                shift 2
                ;;
            --skip-tests)
                SKIP_TESTS=true
                shift
                ;;
            --skip-build)
                SKIP_BUILD=true
                shift
                ;;
            --skip-infrastructure)
                SKIP_INFRASTRUCTURE=true
                shift
                ;;
            --force)
                FORCE_DEPLOY=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check if required tools are installed
    local missing_tools=()
    
    command -v aws >/dev/null 2>&1 || missing_tools+=("aws-cli")
    command -v docker >/dev/null 2>&1 || missing_tools+=("docker")
    command -v serverless >/dev/null 2>&1 || missing_tools+=("serverless")
    command -v terraform >/dev/null 2>&1 || missing_tools+=("terraform")
    command -v jq >/dev/null 2>&1 || missing_tools+=("jq")
    
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        print_error "Missing required tools: ${missing_tools[*]}"
        print_status "Please install the missing tools and try again."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity >/dev/null 2>&1; then
        print_error "AWS credentials not configured or invalid"
        print_status "Please run 'aws configure' and try again."
        exit 1
    fi
    
    # Check if we're in the right directory
    if [[ ! -f "$PROJECT_ROOT/serverless.yml" ]]; then
        print_error "serverless.yml not found. Please run this script from the project root."
        exit 1
    fi
    
    print_success "Prerequisites check passed"
}

# Function to run tests
run_tests() {
    if [[ "$SKIP_TESTS" == true ]]; then
        print_warning "Skipping tests"
        return 0
    fi
    
    print_status "Running tests..."
    cd "$PROJECT_ROOT"
    
    # Run Python tests
    if [[ -f "test_fastapi_app.py" ]]; then
        print_status "Running FastAPI tests..."
        python3 test_fastapi_app.py || {
            print_error "FastAPI tests failed"
            exit 1
        }
    fi
    
    # Run unified service tests
    if [[ -f "test_unified_order_service.py" ]]; then
        print_status "Running unified service tests..."
        python3 test_unified_order_service.py || {
            print_error "Unified service tests failed"
            exit 1
        }
    fi
    
    # Run NLP component tests
    if [[ -f "test_nlp_components.py" ]]; then
        print_status "Running NLP component tests..."
        python3 test_nlp_components.py || {
            print_error "NLP component tests failed"
            exit 1
        }
    fi
    
    print_success "All tests passed"
}

# Function to build Docker image
build_docker_image() {
    if [[ "$SKIP_BUILD" == true ]]; then
        print_warning "Skipping Docker build"
        return 0
    fi
    
    print_status "Building Docker image..."
    cd "$PROJECT_ROOT"
    
    # Get AWS account ID
    local aws_account_id=$(aws sts get-caller-identity --query Account --output text)
    local ecr_uri="${aws_account_id}.dkr.ecr.${AWS_REGION}.amazonaws.com"
    local image_name="${ecr_uri}/${ECR_REPOSITORY}:${DOCKER_IMAGE_TAG}"
    
    # Create ECR repository if it doesn't exist
    aws ecr describe-repositories --repository-names "$ECR_REPOSITORY" --region "$AWS_REGION" >/dev/null 2>&1 || {
        print_status "Creating ECR repository: $ECR_REPOSITORY"
        aws ecr create-repository --repository-name "$ECR_REPOSITORY" --region "$AWS_REGION"
    }
    
    # Get ECR login token
    print_status "Logging in to ECR..."
    aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ecr_uri"
    
    # Build Docker image
    print_status "Building image: $image_name"
    docker build -f Dockerfile.lambda -t "$image_name" . || {
        print_error "Docker build failed"
        exit 1
    }
    
    # Push Docker image
    print_status "Pushing image to ECR..."
    docker push "$image_name" || {
        print_error "Docker push failed"
        exit 1
    }
    
    print_success "Docker image built and pushed successfully"
}

# Function to deploy infrastructure
deploy_infrastructure() {
    if [[ "$SKIP_INFRASTRUCTURE" == true ]]; then
        print_warning "Skipping infrastructure deployment"
        return 0
    fi
    
    print_status "Deploying infrastructure with Terraform..."
    cd "$PROJECT_ROOT/infrastructure/terraform"
    
    # Initialize Terraform
    print_status "Initializing Terraform..."
    terraform init || {
        print_error "Terraform initialization failed"
        exit 1
    }
    
    # Plan Terraform changes
    print_status "Planning Terraform changes..."
    terraform plan -var="environment=$ENVIRONMENT" -var="aws_region=$AWS_REGION" || {
        print_error "Terraform plan failed"
        exit 1
    }
    
    # Apply Terraform changes
    print_status "Applying Terraform changes..."
    terraform apply -var="environment=$ENVIRONMENT" -var="aws_region=$AWS_REGION" -auto-approve || {
        print_error "Terraform apply failed"
        exit 1
    }
    
    # Get outputs
    print_status "Getting Terraform outputs..."
    local redis_endpoint=$(terraform output -raw redis_endpoint)
    local dynamodb_orders_table=$(terraform output -raw dynamodb_orders_table)
    local secrets_arn=$(terraform output -raw secrets_arn)
    
    # Export outputs for Serverless
    export REDIS_ENDPOINT="$redis_endpoint"
    export DYNAMODB_ORDERS_TABLE="$dynamodb_orders_table"
    export SECRETS_ARN="$secrets_arn"
    
    print_success "Infrastructure deployed successfully"
}

# Function to deploy with Serverless Framework
deploy_serverless() {
    print_status "Deploying with Serverless Framework..."
    cd "$PROJECT_ROOT"
    
    # Set environment variables
    export AWS_REGION="$AWS_REGION"
    export STAGE="$STAGE"
    
    # Deploy with Serverless
    print_status "Deploying to stage: $STAGE"
    serverless deploy --stage "$STAGE" --region "$AWS_REGION" --verbose || {
        print_error "Serverless deployment failed"
        exit 1
    }
    
    # Get deployment outputs
    local api_url=$(serverless info --stage "$STAGE" --region "$AWS_REGION" | grep "endpoints:" | awk '{print $2}')
    
    print_success "Serverless deployment completed"
    print_status "API URL: $api_url"
}

# Function to run database migrations
run_migrations() {
    print_status "Running database migrations..."
    cd "$PROJECT_ROOT"
    
    # Create migration script if it doesn't exist
    if [[ ! -f "scripts/migrate.py" ]]; then
        print_warning "Migration script not found, skipping migrations"
        return 0
    fi
    
    # Run migrations
    python3 scripts/migrate.py --environment "$ENVIRONMENT" || {
        print_error "Database migrations failed"
        exit 1
    }
    
    print_success "Database migrations completed"
}

# Function to update CloudFront cache
update_cloudfront_cache() {
    print_status "Updating CloudFront cache..."
    
    # Get CloudFront distribution ID from Terraform output
    cd "$PROJECT_ROOT/infrastructure/terraform"
    local distribution_id=$(terraform output -raw cloudfront_distribution_id 2>/dev/null || echo "")
    
    if [[ -n "$distribution_id" ]]; then
        print_status "Invalidating CloudFront cache for distribution: $distribution_id"
        aws cloudfront create-invalidation --distribution-id "$distribution_id" --paths "/*" --region "$AWS_REGION" || {
            print_warning "CloudFront cache invalidation failed"
        }
    else
        print_warning "CloudFront distribution ID not found, skipping cache invalidation"
    fi
}

# Function to run health checks
run_health_checks() {
    print_status "Running health checks..."
    
    # Get API URL from Serverless output
    cd "$PROJECT_ROOT"
    local api_url=$(serverless info --stage "$STAGE" --region "$AWS_REGION" | grep "endpoints:" | awk '{print $2}')
    
    if [[ -n "$api_url" ]]; then
        # Wait for deployment to be ready
        print_status "Waiting for deployment to be ready..."
        sleep 30
        
        # Test health endpoint
        print_status "Testing health endpoint..."
        local health_response=$(curl -s -o /dev/null -w "%{http_code}" "${api_url}/health" || echo "000")
        
        if [[ "$health_response" == "200" ]]; then
            print_success "Health check passed"
        else
            print_error "Health check failed (HTTP $health_response)"
            exit 1
        fi
        
        # Test API endpoint
        print_status "Testing API endpoint..."
        local api_response=$(curl -s -o /dev/null -w "%{http_code}" "${api_url}/api" || echo "000")
        
        if [[ "$api_response" == "200" ]]; then
            print_success "API check passed"
        else
            print_error "API check failed (HTTP $api_response)"
            exit 1
        fi
    else
        print_warning "API URL not found, skipping health checks"
    fi
}

# Function to show deployment summary
show_deployment_summary() {
    print_status "Deployment Summary"
    echo "=================="
    echo "Environment: $ENVIRONMENT"
    echo "Stage: $STAGE"
    echo "Region: $AWS_REGION"
    echo "Docker Tag: $DOCKER_IMAGE_TAG"
    echo "Timestamp: $(date)"
    
    # Get API URL
    cd "$PROJECT_ROOT"
    local api_url=$(serverless info --stage "$STAGE" --region "$AWS_REGION" | grep "endpoints:" | awk '{print $2}')
    
    if [[ -n "$api_url" ]]; then
        echo "API URL: $api_url"
        echo "Health Check: ${api_url}/health"
        echo "API Documentation: ${api_url}/docs"
    fi
    
    print_success "Deployment completed successfully!"
}

# Function to handle cleanup on exit
cleanup() {
    print_status "Cleaning up..."
    # Add any cleanup tasks here
}

# Main deployment function
main() {
    # Set up trap for cleanup
    trap cleanup EXIT
    
    # Parse command line arguments
    parse_arguments "$@"
    
    # Show deployment configuration
    print_status "Deployment Configuration"
    echo "Environment: $ENVIRONMENT"
    echo "Stage: $STAGE"
    echo "Region: $AWS_REGION"
    echo "Docker Tag: $DOCKER_IMAGE_TAG"
    echo ""
    
    # Confirm deployment (unless forced)
    if [[ "$FORCE_DEPLOY" != true ]]; then
        read -p "Do you want to proceed with the deployment? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_status "Deployment cancelled"
            exit 0
        fi
    fi
    
    # Start deployment
    print_status "Starting VyaparAI deployment..."
    
    # Check prerequisites
    check_prerequisites
    
    # Run tests
    run_tests
    
    # Build Docker image
    build_docker_image
    
    # Deploy infrastructure
    deploy_infrastructure
    
    # Deploy with Serverless
    deploy_serverless
    
    # Run migrations
    run_migrations
    
    # Update CloudFront cache
    update_cloudfront_cache
    
    # Run health checks
    run_health_checks
    
    # Show deployment summary
    show_deployment_summary
}

# Run main function with all arguments
main "$@"
