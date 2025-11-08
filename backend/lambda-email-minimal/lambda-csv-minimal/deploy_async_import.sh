#!/bin/bash

# VyapaarAI Async Import System Deployment Script
# This script sets up the infrastructure and deploys the async import system

set -e

echo "🚀 Starting VyapaarAI Async Import System Deployment..."

# Configuration
REGION="ap-south-1"
STACK_NAME="vyapaarai-async-import"
LAMBDA_FUNCTION_NAME="vyapaarai-process-import-job"
LAMBDA_HANDLER="workers.process_import_job.lambda_handler"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Please install AWS CLI."
        exit 1
    fi
    
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 not found. Please install Python 3."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Create S3 buckets
create_s3_buckets() {
    log_info "Creating S3 buckets..."
    
    # Bulk uploads bucket
    BULK_BUCKET="vyapaarai-bulk-uploads-prod"
    if ! aws s3 ls "s3://$BULK_BUCKET" 2>/dev/null; then
        aws s3 mb "s3://$BULK_BUCKET" --region $REGION
        aws s3api put-bucket-versioning --bucket $BULK_BUCKET --versioning-configuration Status=Enabled
        aws s3api put-bucket-lifecycle-configuration --bucket $BULK_BUCKET --lifecycle-configuration '{
            "Rules": [{
                "ID": "DeleteOldUploads",
                "Status": "Enabled",
                "Expiration": {
                    "Days": 30
                }
            }]
        }'
        log_success "Created bulk uploads bucket: $BULK_BUCKET"
    else
        log_info "Bulk uploads bucket already exists: $BULK_BUCKET"
    fi
    
    # Product images bucket
    IMAGES_BUCKET="vyapaarai-product-images-prod"
    if ! aws s3 ls "s3://$IMAGES_BUCKET" 2>/dev/null; then
        aws s3 mb "s3://$IMAGES_BUCKET" --region $REGION
        aws s3api put-bucket-versioning --bucket $IMAGES_BUCKET --versioning-configuration Status=Enabled
        aws s3api put-bucket-cors --bucket $IMAGES_BUCKET --cors-configuration '{
            "CORSRules": [{
                "AllowedHeaders": ["*"],
                "AllowedMethods": ["GET", "HEAD"],
                "AllowedOrigins": ["*"],
                "MaxAgeSeconds": 3000
            }]
        }'
        log_success "Created product images bucket: $IMAGES_BUCKET"
    else
        log_info "Product images bucket already exists: $IMAGES_BUCKET"
    fi
}

# Create DynamoDB table for import jobs
create_import_jobs_table() {
    log_info "Creating import jobs table..."
    
    TABLE_NAME="vyaparai-import-jobs-prod"
    
    if ! aws dynamodb describe-table --table-name $TABLE_NAME --region $REGION 2>/dev/null; then
        aws dynamodb create-table \
            --table-name $TABLE_NAME \
            --attribute-definitions \
                AttributeName=job_id,AttributeType=S \
                AttributeName=created_by_user_id_gsi,AttributeType=S \
                AttributeName=created_at_gsi,AttributeType=S \
                AttributeName=status_gsi,AttributeType=S \
                AttributeName=job_type_gsi,AttributeType=S \
            --key-schema \
                AttributeName=job_id,KeyType=HASH \
            --global-secondary-indexes \
                IndexName=created_by_user_id_gsi-index,KeySchema=[{AttributeName=created_by_user_id_gsi,KeyType=HASH},{AttributeName=created_at_gsi,KeyType=RANGE}],Projection={ProjectionType=ALL},ProvisionedThroughput={ReadCapacityUnits=5,WriteCapacityUnits=5} \
                IndexName=status_gsi-index,KeySchema=[{AttributeName=status_gsi,KeyType=HASH},{AttributeName=created_at_gsi,KeyType=RANGE}],Projection={ProjectionType=ALL},ProvisionedThroughput={ReadCapacityUnits=5,WriteCapacityUnits=5} \
                IndexName=job_type_gsi-index,KeySchema=[{AttributeName=job_type_gsi,KeyType=HASH},{AttributeName=created_at_gsi,KeyType=RANGE}],Projection={ProjectionType=ALL},ProvisionedThroughput={ReadCapacityUnits=5,WriteCapacityUnits=5} \
            --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
            --region $REGION
        
        log_success "Created import jobs table: $TABLE_NAME"
    else
        log_info "Import jobs table already exists: $TABLE_NAME"
    fi
}

# Add GSI to global products table
add_name_brand_gsi() {
    log_info "Adding name-brand GSI to global products table..."
    
    TABLE_NAME="vyaparai-global-products-prod"
    
    # Check if GSI already exists
    if ! aws dynamodb describe-table --table-name $TABLE_NAME --region $REGION | grep -q "name-brand-index"; then
        aws dynamodb update-table \
            --table-name $TABLE_NAME \
            --attribute-definitions \
                AttributeName=name_brand_key,AttributeType=S \
            --global-secondary-index-updates \
                '[{
                    "Create": {
                        "IndexName": "name-brand-index",
                        "KeySchema": [{"AttributeName": "name_brand_key", "KeyType": "HASH"}],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
                    }
                }]' \
            --region $REGION
        
        log_success "Added name-brand GSI to global products table"
    else
        log_info "Name-brand GSI already exists on global products table"
    fi
}

# Create Lambda deployment package
create_lambda_package() {
    log_info "Creating Lambda deployment package..."
    
    # Create deployment directory
    DEPLOY_DIR="lambda_deployment_async"
    rm -rf $DEPLOY_DIR
    mkdir -p $DEPLOY_DIR
    
    # Copy source files
    cp -r services $DEPLOY_DIR/
    cp -r utils $DEPLOY_DIR/
    cp -r workers $DEPLOY_DIR/
    cp requirements.txt $DEPLOY_DIR/
    
    # Install dependencies
    cd $DEPLOY_DIR
    pip install -r requirements.txt -t .
    cd ..
    
    # Create deployment zip
    cd $DEPLOY_DIR
    zip -r ../async_import_lambda.zip .
    cd ..
    
    log_success "Created Lambda deployment package: async_import_lambda.zip"
}

# Deploy Lambda function
deploy_lambda_function() {
    log_info "Deploying Lambda function..."
    
    # Check if function exists
    if aws lambda get-function --function-name $LAMBDA_FUNCTION_NAME --region $REGION 2>/dev/null; then
        log_info "Updating existing Lambda function..."
        aws lambda update-function-code \
            --function-name $LAMBDA_FUNCTION_NAME \
            --zip-file fileb://async_import_lambda.zip \
            --region $REGION
    else
        log_info "Creating new Lambda function..."
        
        # Get the main Lambda function's role
        MAIN_LAMBDA_ROLE=$(aws lambda get-function --function-name vyapaarai-lambda-csv-minimal --region $REGION --query 'Configuration.Role' --output text)
        
        aws lambda create-function \
            --function-name $LAMBDA_FUNCTION_NAME \
            --runtime python3.9 \
            --role $MAIN_LAMBDA_ROLE \
            --handler $LAMBDA_HANDLER \
            --zip-file fileb://async_import_lambda.zip \
            --timeout 900 \
            --memory-size 1024 \
            --region $REGION
        
        log_success "Created Lambda function: $LAMBDA_FUNCTION_NAME"
    fi
    
    # Update environment variables
    aws lambda update-function-configuration \
        --function-name $LAMBDA_FUNCTION_NAME \
        --environment Variables='{
            "GLOBAL_PRODUCTS_TABLE": "vyaparai-global-products-prod",
            "STORE_INVENTORY_TABLE": "vyaparai-store-inventory-prod",
            "BULK_UPLOADS_BUCKET": "vyapaarai-bulk-uploads-prod",
            "PRODUCT_IMAGES_BUCKET": "vyapaarai-product-images-prod"
        }' \
        --region $REGION
    
    log_success "Lambda function deployed and configured"
}

# Update main Lambda function
update_main_lambda() {
    log_info "Updating main Lambda function with async import endpoints..."
    
    # Deploy the updated lambda_handler.py
    cd lambda-csv-minimal
    zip -r ../main_lambda_update.zip .
    cd ..
    
    aws lambda update-function-code \
        --function-name vyapaarai-lambda-csv-minimal \
        --zip-file fileb://main_lambda_update.zip \
        --region $REGION
    
    log_success "Main Lambda function updated with async import endpoints"
}

# Create CloudWatch alarms
create_monitoring() {
    log_info "Creating CloudWatch alarms..."
    
    # Lambda duration alarm
    aws cloudwatch put-metric-alarm \
        --alarm-name "vyapaarai-import-lambda-duration" \
        --alarm-description "Alert when import Lambda takes too long" \
        --metric-name Duration \
        --namespace AWS/Lambda \
        --statistic Average \
        --period 300 \
        --threshold 600000 \
        --comparison-operator GreaterThanThreshold \
        --dimensions Name=FunctionName,Value=$LAMBDA_FUNCTION_NAME \
        --evaluation-periods 2 \
        --region $REGION || true
    
    # Lambda error rate alarm
    aws cloudwatch put-metric-alarm \
        --alarm-name "vyapaarai-import-lambda-errors" \
        --alarm-description "Alert when import Lambda has high error rate" \
        --metric-name Errors \
        --namespace AWS/Lambda \
        --statistic Sum \
        --period 300 \
        --threshold 5 \
        --comparison-operator GreaterThanThreshold \
        --dimensions Name=FunctionName,Value=$LAMBDA_FUNCTION_NAME \
        --evaluation-periods 1 \
        --region $REGION || true
    
    log_success "CloudWatch alarms created"
}

# Main deployment function
main() {
    log_info "Starting VyapaarAI Async Import System Deployment"
    
    check_prerequisites
    create_s3_buckets
    create_import_jobs_table
    add_name_brand_gsi
    create_lambda_package
    deploy_lambda_function
    update_main_lambda
    create_monitoring
    
    log_success "🎉 Async Import System Deployment Complete!"
    
    echo ""
    log_info "Next Steps:"
    echo "1. Test the new async import endpoints"
    echo "2. Update frontend to use the new async flow"
    echo "3. Monitor CloudWatch logs for any issues"
    echo "4. Consider setting up SNS notifications for job completion"
    
    echo ""
    log_info "New Endpoints Available:"
    echo "- GET /api/v1/admin/products/import/upload-url"
    echo "- POST /api/v1/admin/products/import/process"
    echo "- GET /api/v1/admin/products/import/{job_id}/status"
    
    echo ""
    log_info "Infrastructure Created:"
    echo "- S3 Bucket: vyapaarai-bulk-uploads-prod"
    echo "- S3 Bucket: vyapaarai-product-images-prod"
    echo "- DynamoDB Table: vyaparai-import-jobs-prod"
    echo "- Lambda Function: $LAMBDA_FUNCTION_NAME"
    echo "- GSI: name-brand-index on global products table"
}

# Run main function
main "$@"
