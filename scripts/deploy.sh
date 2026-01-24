#!/bin/bash
#
# VyapaarAI Unified Deployment Script
# Author: DevPrakash
# Usage: ./scripts/deploy.sh <command> [options]
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
AWS_REGION="ap-south-1"
LAMBDA_FUNCTION="vyaparai-api-prod"
S3_FRONTEND="www.vyapaarai.com"
S3_DEPLOYMENTS="vyaparai-lambda-deployments"
CLOUDFRONT_DIST="E1UY93SVXV8QOF"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not installed. Install: https://aws.amazon.com/cli/"
        exit 1
    fi
}

check_aws_credentials() {
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Run: aws configure"
        exit 1
    fi
    log_info "AWS credentials verified"
}

check_git_status() {
    cd "$PROJECT_ROOT"
    if [[ -n $(git status --porcelain) ]]; then
        log_warn "Uncommitted changes detected!"
        git status --short
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

run_tests() {
    log_info "Running regression tests..."
    cd "$PROJECT_ROOT/backend"
    if poetry run pytest tests/ -m regression -v --tb=short; then
        log_success "All regression tests passed"
    else
        log_error "Tests failed! Deployment aborted."
        exit 1
    fi
}

deploy_backend() {
    local skip_tests=${1:-false}

    log_info "=== Backend Deployment ==="
    cd "$PROJECT_ROOT/backend"

    # Run tests unless skipped
    if [[ "$skip_tests" != "true" ]]; then
        run_tests
    fi

    # Build Lambda package
    log_info "Building Lambda deployment package..."
    rm -rf lambda_deploy lambda_function.zip
    mkdir -p lambda_deploy

    # Copy application code
    cp -r app lambda_deploy/
    cp lambda_handler.py lambda_deploy/

    # Install dependencies
    log_info "Installing dependencies..."
    pip install -r requirements.txt -t lambda_deploy/ --quiet

    # Create ZIP
    cd lambda_deploy
    zip -r ../lambda_function.zip . -x "*.pyc" -x "*__pycache__*" -x "*.dist-info/*" > /dev/null
    cd ..

    log_info "Package size: $(du -h lambda_function.zip | cut -f1)"

    # Upload to S3
    log_info "Uploading to S3..."
    aws s3 cp lambda_function.zip "s3://${S3_DEPLOYMENTS}/backend/lambda_function.zip" --region "$AWS_REGION"

    # Update Lambda
    log_info "Updating Lambda function..."
    aws lambda update-function-code \
        --function-name "$LAMBDA_FUNCTION" \
        --s3-bucket "$S3_DEPLOYMENTS" \
        --s3-key "backend/lambda_function.zip" \
        --region "$AWS_REGION" > /dev/null

    # Wait for update
    log_info "Waiting for Lambda update..."
    aws lambda wait function-updated --function-name "$LAMBDA_FUNCTION" --region "$AWS_REGION"

    log_success "Backend deployed successfully!"
}

deploy_frontend() {
    log_info "=== Frontend Deployment ==="
    cd "$PROJECT_ROOT/frontend-pwa"

    # Build
    log_info "Building frontend..."
    npm run build

    # Sync to S3
    log_info "Syncing to S3..."
    aws s3 sync dist/ "s3://${S3_FRONTEND}/" --delete --region "$AWS_REGION"

    # Invalidate CloudFront
    log_info "Invalidating CloudFront cache..."
    aws cloudfront create-invalidation \
        --distribution-id "$CLOUDFRONT_DIST" \
        --paths "/*" \
        --region "$AWS_REGION" > /dev/null

    log_success "Frontend deployed successfully!"
}

deploy_all() {
    log_info "=== Full Stack Deployment ==="

    read -p "Deploy to PRODUCTION? This will affect live users. (yes/no) " confirm
    if [[ "$confirm" != "yes" ]]; then
        log_info "Deployment cancelled"
        exit 0
    fi

    deploy_backend
    deploy_frontend

    log_success "=== Full deployment complete! ==="
}

deploy_lambda_quick() {
    log_info "=== Quick Lambda Update (skip tests) ==="

    read -p "Skip tests and deploy directly? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        deploy_backend
    else
        deploy_backend true
    fi
}

show_status() {
    log_info "=== Deployment Status ==="

    # Lambda status
    echo -e "\n${BLUE}Lambda Function:${NC}"
    aws lambda get-function --function-name "$LAMBDA_FUNCTION" --region "$AWS_REGION" \
        --query '{State: Configuration.State, LastModified: Configuration.LastModified, Runtime: Configuration.Runtime, MemorySize: Configuration.MemorySize}' \
        --output table

    # Frontend
    echo -e "\n${BLUE}Frontend (S3):${NC}"
    aws s3 ls "s3://${S3_FRONTEND}/" --summarize | tail -2

    # Recent CloudFront invalidations
    echo -e "\n${BLUE}CloudFront:${NC}"
    aws cloudfront list-invalidations --distribution-id "$CLOUDFRONT_DIST" \
        --query 'InvalidationList.Items[0:3].{Id:Id,Status:Status,CreateTime:CreateTime}' \
        --output table 2>/dev/null || echo "No recent invalidations"
}

rollback() {
    log_warn "=== Rollback ==="

    # List recent deployments
    log_info "Recent Lambda deployments in S3:"
    aws s3 ls "s3://${S3_DEPLOYMENTS}/backend/" --recursive | tail -5

    read -p "Enter S3 key to rollback to (or 'cancel'): " s3_key
    if [[ "$s3_key" == "cancel" ]]; then
        exit 0
    fi

    log_info "Rolling back to: $s3_key"
    aws lambda update-function-code \
        --function-name "$LAMBDA_FUNCTION" \
        --s3-bucket "$S3_DEPLOYMENTS" \
        --s3-key "$s3_key" \
        --region "$AWS_REGION"

    log_success "Rollback complete!"
}

show_help() {
    echo "VyapaarAI Deployment Script"
    echo ""
    echo "Usage: ./scripts/deploy.sh <command>"
    echo ""
    echo "Commands:"
    echo "  backend     Deploy backend (Lambda) with tests"
    echo "  frontend    Deploy frontend (S3 + CloudFront)"
    echo "  all         Deploy full stack (backend + frontend)"
    echo "  lambda      Quick Lambda update (option to skip tests)"
    echo "  status      Show deployment status"
    echo "  rollback    Rollback to previous version"
    echo "  help        Show this help"
    echo ""
    echo "Examples:"
    echo "  ./scripts/deploy.sh backend    # Deploy backend with tests"
    echo "  ./scripts/deploy.sh frontend   # Deploy frontend only"
    echo "  ./scripts/deploy.sh all        # Full deployment"
    echo "  ./scripts/deploy.sh status     # Check current status"
}

# Main
main() {
    local command=${1:-help}

    case $command in
        backend)
            check_aws_cli
            check_aws_credentials
            check_git_status
            deploy_backend
            ;;
        frontend)
            check_aws_cli
            check_aws_credentials
            check_git_status
            deploy_frontend
            ;;
        all)
            check_aws_cli
            check_aws_credentials
            check_git_status
            deploy_all
            ;;
        lambda)
            check_aws_cli
            check_aws_credentials
            deploy_lambda_quick
            ;;
        status)
            check_aws_cli
            check_aws_credentials
            show_status
            ;;
        rollback)
            check_aws_cli
            check_aws_credentials
            rollback
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
