#!/bin/bash

# VyaparAI Hybrid Database Setup Script
# This script sets up the complete hybrid database architecture

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-dev}
REGION="ap-south-1"
STACK_NAME="vyaparai-hybrid-db-${ENVIRONMENT}"

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

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check AWS CLI configuration
check_aws_config() {
    print_status "Checking AWS CLI configuration..."
    
    if ! command_exists aws; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    if ! aws sts get-caller-identity >/dev/null 2>&1; then
        print_error "AWS CLI is not configured. Please run 'aws configure' first."
        exit 1
    fi
    
    print_success "AWS CLI is configured"
}

# Function to check required tools
check_requirements() {
    print_status "Checking requirements..."
    
    local missing_tools=()
    
    if ! command_exists aws; then
        missing_tools+=("aws-cli")
    fi
    
    if ! command_exists terraform; then
        missing_tools+=("terraform")
    fi
    
    if ! command_exists psql; then
        missing_tools+=("postgresql-client")
    fi
    
    if ! command_exists jq; then
        missing_tools+=("jq")
    fi
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        print_error "Missing required tools: ${missing_tools[*]}"
        print_status "Please install the missing tools and try again."
        exit 1
    fi
    
    print_success "All required tools are available"
}

# Function to create DynamoDB tables
create_dynamodb_tables() {
    print_status "Creating DynamoDB tables..."
    
    # Table names
    ORDERS_TABLE="vyaparai-orders-${ENVIRONMENT}"
    SESSIONS_TABLE="vyaparai-sessions-${ENVIRONMENT}"
    RATE_LIMITS_TABLE="vyaparai-rate-limits-${ENVIRONMENT}"
    STORES_TABLE="vyaparai-stores-${ENVIRONMENT}"
    PRODUCTS_TABLE="vyaparai-products-${ENVIRONMENT}"
    METRICS_TABLE="vyaparai-metrics-${ENVIRONMENT}"
    
    # Create Orders table with streams enabled
    print_status "Creating Orders table..."
    aws dynamodb create-table \
        --table-name "$ORDERS_TABLE" \
        --attribute-definitions \
            AttributeName=pk,AttributeType=S \
            AttributeName=sk,AttributeType=S \
            AttributeName=gsi1pk,AttributeType=S \
            AttributeName=gsi1sk,AttributeType=S \
            AttributeName=gsi2pk,AttributeType=S \
            AttributeName=gsi2sk,AttributeType=S \
            AttributeName=gsi3pk,AttributeType=S \
            AttributeName=gsi3sk,AttributeType=S \
        --key-schema \
            AttributeName=pk,KeyType=HASH \
            AttributeName=sk,KeyType=RANGE \
        --global-secondary-indexes \
            IndexName=GSI1,KeySchema=[{AttributeName=gsi1pk,KeyType=HASH},{AttributeName=gsi1sk,KeyType=RANGE}],Projection={ProjectionType=ALL} \
            IndexName=GSI2,KeySchema=[{AttributeName=gsi2pk,KeyType=HASH},{AttributeName=gsi2sk,KeyType=RANGE}],Projection={ProjectionType=ALL} \
            IndexName=GSI3,KeySchema=[{AttributeName=gsi3pk,KeyType=HASH},{AttributeName=gsi3sk,KeyType=RANGE}],Projection={ProjectionType=ALL} \
        --billing-mode PAY_PER_REQUEST \
        --stream-specification StreamEnabled=true,StreamViewType=NEW_AND_OLD_IMAGES \
        --region "$REGION"
    
    # Create Sessions table
    print_status "Creating Sessions table..."
    aws dynamodb create-table \
        --table-name "$SESSIONS_TABLE" \
        --attribute-definitions \
            AttributeName=pk,AttributeType=S \
            AttributeName=gsi1pk,AttributeType=S \
            AttributeName=gsi1sk,AttributeType=S \
        --key-schema \
            AttributeName=pk,KeyType=HASH \
        --global-secondary-indexes \
            IndexName=GSI1,KeySchema=[{AttributeName=gsi1pk,KeyType=HASH},{AttributeName=gsi1sk,KeyType=RANGE}],Projection={ProjectionType=ALL} \
        --billing-mode PAY_PER_REQUEST \
        --region "$REGION"
    
    # Create Rate Limits table
    print_status "Creating Rate Limits table..."
    aws dynamodb create-table \
        --table-name "$RATE_LIMITS_TABLE" \
        --attribute-definitions \
            AttributeName=pk,AttributeType=S \
            AttributeName=sk,AttributeType=S \
            AttributeName=gsi1pk,AttributeType=S \
            AttributeName=gsi1sk,AttributeType=S \
        --key-schema \
            AttributeName=pk,KeyType=HASH \
            AttributeName=sk,KeyType=RANGE \
        --global-secondary-indexes \
            IndexName=GSI1,KeySchema=[{AttributeName=gsi1pk,KeyType=HASH},{AttributeName=gsi1sk,KeyType=RANGE}],Projection={ProjectionType=ALL} \
        --billing-mode PAY_PER_REQUEST \
        --region "$REGION"
    
    # Create Stores table
    print_status "Creating Stores table..."
    aws dynamodb create-table \
        --table-name "$STORES_TABLE" \
        --attribute-definitions \
            AttributeName=pk,AttributeType=S \
            AttributeName=gsi1pk,AttributeType=S \
            AttributeName=gsi1sk,AttributeType=S \
            AttributeName=gsi2pk,AttributeType=S \
            AttributeName=gsi2sk,AttributeType=S \
        --key-schema \
            AttributeName=pk,KeyType=HASH \
        --global-secondary-indexes \
            IndexName=GSI1,KeySchema=[{AttributeName=gsi1pk,KeyType=HASH},{AttributeName=gsi1sk,KeyType=RANGE}],Projection={ProjectionType=ALL} \
            IndexName=GSI2,KeySchema=[{AttributeName=gsi2pk,KeyType=HASH},{AttributeName=gsi2sk,KeyType=RANGE}],Projection={ProjectionType=ALL} \
        --billing-mode PAY_PER_REQUEST \
        --region "$REGION"
    
    # Create Products table
    print_status "Creating Products table..."
    aws dynamodb create-table \
        --table-name "$PRODUCTS_TABLE" \
        --attribute-definitions \
            AttributeName=pk,AttributeType=S \
            AttributeName=sk,AttributeType=S \
            AttributeName=gsi1pk,AttributeType=S \
            AttributeName=gsi1sk,AttributeType=S \
            AttributeName=gsi2pk,AttributeType=S \
            AttributeName=gsi2sk,AttributeType=S \
            AttributeName=gsi3pk,AttributeType=S \
            AttributeName=gsi3sk,AttributeType=S \
        --key-schema \
            AttributeName=pk,KeyType=HASH \
            AttributeName=sk,KeyType=RANGE \
        --global-secondary-indexes \
            IndexName=GSI1,KeySchema=[{AttributeName=gsi1pk,KeyType=HASH},{AttributeName=gsi1sk,KeyType=RANGE}],Projection={ProjectionType=ALL} \
            IndexName=GSI2,KeySchema=[{AttributeName=gsi2pk,KeyType=HASH},{AttributeName=gsi2sk,KeyType=RANGE}],Projection={ProjectionType=ALL} \
            IndexName=GSI3,KeySchema=[{AttributeName=gsi3pk,KeyType=HASH},{AttributeName=gsi3sk,KeyType=RANGE}],Projection={ProjectionType=ALL} \
        --billing-mode PAY_PER_REQUEST \
        --region "$REGION"
    
    # Create Metrics table
    print_status "Creating Metrics table..."
    aws dynamodb create-table \
        --table-name "$METRICS_TABLE" \
        --attribute-definitions \
            AttributeName=pk,AttributeType=S \
            AttributeName=sk,AttributeType=S \
            AttributeName=gsi1pk,AttributeType=S \
            AttributeName=gsi1sk,AttributeType=S \
        --key-schema \
            AttributeName=pk,KeyType=HASH \
            AttributeName=sk,KeyType=RANGE \
        --global-secondary-indexes \
            IndexName=GSI1,KeySchema=[{AttributeName=gsi1pk,KeyType=HASH},{AttributeName=gsi1sk,KeyType=RANGE}],Projection={ProjectionType=ALL} \
        --billing-mode PAY_PER_REQUEST \
        --region "$REGION"
    
    print_success "DynamoDB tables created successfully"
}

# Function to wait for DynamoDB tables to be active
wait_for_dynamodb_tables() {
    print_status "Waiting for DynamoDB tables to be active..."
    
    local tables=(
        "vyaparai-orders-${ENVIRONMENT}"
        "vyaparai-sessions-${ENVIRONMENT}"
        "vyaparai-rate-limits-${ENVIRONMENT}"
        "vyaparai-stores-${ENVIRONMENT}"
        "vyaparai-products-${ENVIRONMENT}"
        "vyaparai-metrics-${ENVIRONMENT}"
    )
    
    for table in "${tables[@]}"; do
        print_status "Waiting for table $table to be active..."
        aws dynamodb wait table-exists --table-name "$table" --region "$REGION"
        print_success "Table $table is active"
    done
}

# Function to create RDS instance using Terraform
create_rds_instance() {
    print_status "Creating RDS PostgreSQL instance using Terraform..."
    
    # Create Terraform configuration
    cat > terraform-rds.tf << EOF
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "$REGION"
}

# VPC and Networking
resource "aws_vpc" "vyaparai_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "vyaparai-vpc-${ENVIRONMENT}"
  }
}

resource "aws_subnet" "private_subnet_1" {
  vpc_id            = aws_vpc.vyaparai_vpc.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = data.aws_availability_zones.available.names[0]

  tags = {
    Name = "vyaparai-private-subnet-1-${ENVIRONMENT}"
  }
}

resource "aws_subnet" "private_subnet_2" {
  vpc_id            = aws_vpc.vyaparai_vpc.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = data.aws_availability_zones.available.names[1]

  tags = {
    Name = "vyaparai-private-subnet-2-${ENVIRONMENT}"
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

# RDS Subnet Group
resource "aws_db_subnet_group" "vyaparai_rds_subnet_group" {
  name       = "vyaparai-rds-subnet-group-${ENVIRONMENT}"
  subnet_ids = [aws_subnet.private_subnet_1.id, aws_subnet.private_subnet_2.id]

  tags = {
    Name = "vyaparai-rds-subnet-group-${ENVIRONMENT}"
  }
}

# Security Group for RDS
resource "aws_security_group" "vyaparai_rds_sg" {
  name        = "vyaparai-rds-sg-${ENVIRONMENT}"
  description = "Security group for VyaparAI RDS"
  vpc_id      = aws_vpc.vyaparai_vpc.id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "vyaparai-rds-sg-${ENVIRONMENT}"
  }
}

# RDS Instance
resource "aws_db_instance" "vyaparai_analytics" {
  identifier = "vyaparai-analytics-${ENVIRONMENT}"
  
  engine         = "postgres"
  engine_version = "15.4"
  instance_class = "${ENVIRONMENT == 'prod' ? 'db.t3.medium' : 'db.t3.micro'}"
  
  allocated_storage     = ${ENVIRONMENT == 'prod' ? '100' : '20'}
  max_allocated_storage = ${ENVIRONMENT == 'prod' ? '500' : '100'}
  storage_type          = "gp3"
  storage_encrypted     = true
  
  db_name  = "vyaparai"
  username = "vyaparai_admin"
  password = random_password.rds_password.result
  
  vpc_security_group_ids = [aws_security_group.vyaparai_rds_sg.id]
  db_subnet_group_name   = aws_db_subnet_group.vyaparai_rds_subnet_group.name
  
  publicly_accessible    = false
  multi_az              = ${ENVIRONMENT == 'prod' ? 'true' : 'false'}
  
  backup_retention_period = ${ENVIRONMENT == 'prod' ? '30' : '7'}
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"
  
  enable_cloudwatch_logs_exports = ["postgresql"]
  monitoring_interval            = 60
  monitoring_role_arn            = aws_iam_role.rds_monitoring_role.arn
  
  performance_insights_enabled          = true
  performance_insights_retention_period = ${ENVIRONMENT == 'prod' ? '7' : '3'}
  
  deletion_protection = ${ENVIRONMENT == 'prod' ? 'true' : 'false'}
  skip_final_snapshot = ${ENVIRONMENT == 'prod' ? 'false' : 'true'}
  
  tags = {
    Environment = "${ENVIRONMENT}"
    Service     = "vyaparai-analytics"
  }
}

# Random password for RDS
resource "random_password" "rds_password" {
  length  = 16
  special = true
}

# IAM Role for RDS Monitoring
resource "aws_iam_role" "rds_monitoring_role" {
  name = "vyaparai-rds-monitoring-${ENVIRONMENT}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring_policy" {
  role       = aws_iam_role.rds_monitoring_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# Outputs
output "rds_endpoint" {
  value = aws_db_instance.vyaparai_analytics.endpoint
}

output "rds_port" {
  value = aws_db_instance.vyaparai_analytics.port
}

output "rds_username" {
  value = aws_db_instance.vyaparai_analytics.username
}

output "rds_password" {
  value     = random_password.rds_password.result
  sensitive = true
}
EOF
    
    # Initialize and apply Terraform
    terraform init
    terraform apply -auto-approve
    
    # Get RDS endpoint
    RDS_ENDPOINT=$(terraform output -raw rds_endpoint)
    RDS_PASSWORD=$(terraform output -raw rds_password)
    
    print_success "RDS instance created successfully"
    print_status "RDS Endpoint: $RDS_ENDPOINT"
}

# Function to run PostgreSQL migrations
run_postgresql_migrations() {
    print_status "Running PostgreSQL migrations..."
    
    # Get RDS endpoint from Terraform output
    RDS_ENDPOINT=$(terraform output -raw rds_endpoint)
    RDS_PASSWORD=$(terraform output -raw rds_password)
    
    # Wait for RDS to be available
    print_status "Waiting for RDS to be available..."
    until pg_isready -h "$RDS_ENDPOINT" -p 5432 -U vyaparai_admin; do
        print_status "Waiting for RDS to be ready..."
        sleep 30
    done
    
    # Run migrations
    print_status "Running database migrations..."
    PGPASSWORD="$RDS_PASSWORD" psql -h "$RDS_ENDPOINT" -U vyaparai_admin -d vyaparai -f ../backend/app/migrations/001_create_tables.sql
    
    print_success "PostgreSQL migrations completed successfully"
}

# Function to set up DynamoDB Streams
setup_dynamodb_streams() {
    print_status "Setting up DynamoDB Streams..."
    
    # Get the stream ARN for the orders table
    ORDERS_TABLE="vyaparai-orders-${ENVIRONMENT}"
    STREAM_ARN=$(aws dynamodb describe-table --table-name "$ORDERS_TABLE" --region "$REGION" --query 'Table.LatestStreamArn' --output text)
    
    print_status "Orders table stream ARN: $STREAM_ARN"
    
    # Note: The actual Lambda function setup would be done through Serverless Framework
    # This is just for reference
    print_warning "DynamoDB Streams are enabled. Lambda function setup should be done through Serverless Framework."
    
    print_success "DynamoDB Streams setup completed"
}

# Function to create sample data
create_sample_data() {
    print_status "Creating sample data..."
    
    # Get RDS endpoint
    RDS_ENDPOINT=$(terraform output -raw rds_endpoint)
    RDS_PASSWORD=$(terraform output -raw rds_password)
    
    # Create sample data SQL
    cat > sample_data.sql << EOF
-- Insert sample stores
INSERT INTO stores (store_id, name, owner_id, address, contact_info, settings) VALUES
('store_001', 'Mumbai Grocery Store', 'owner_001', 
 '{"street": "123 Main Street", "city": "Mumbai", "state": "Maharashtra", "pincode": "400001"}',
 '{"phone": "+91-9876543210", "email": "store@mumbaigrocery.com"}',
 '{"delivery_radius": 5, "min_order_amount": 100, "delivery_fee": 20}'),
('store_002', 'Delhi Grocery Store', 'owner_002',
 '{"street": "456 Central Avenue", "city": "Delhi", "state": "Delhi", "pincode": "110001"}',
 '{"phone": "+91-9876543211", "email": "store@delhigrocery.com"}',
 '{"delivery_radius": 3, "min_order_amount": 150, "delivery_fee": 25}');

-- Insert sample products
INSERT INTO products (store_id, name, category, brand, price, unit, stock_quantity) VALUES
('store_001', 'Basmati Rice', 'Grains', 'India Gate', 120.00, 'kg', 50),
('store_001', 'Refined Oil', 'Cooking Oil', 'Fortune', 150.00, 'liter', 30),
('store_001', 'Milk', 'Dairy', 'Amul', 60.00, 'liter', 100),
('store_001', 'Bread', 'Bakery', 'Britannia', 35.00, 'pack', 25),
('store_001', 'Sugar', 'Essentials', 'Local', 45.00, 'kg', 40),
('store_002', 'Basmati Rice', 'Grains', 'India Gate', 125.00, 'kg', 40),
('store_002', 'Refined Oil', 'Cooking Oil', 'Fortune', 155.00, 'liter', 25),
('store_002', 'Milk', 'Dairy', 'Amul', 62.00, 'liter', 80);

-- Insert sample inventory
INSERT INTO inventory (store_id, product_id, quantity, min_stock_level, max_stock_level)
SELECT store_id, product_id, stock_quantity, 10, stock_quantity * 2
FROM products;
EOF
    
    # Execute sample data
    PGPASSWORD="$RDS_PASSWORD" psql -h "$RDS_ENDPOINT" -U vyaparai_admin -d vyaparai -f sample_data.sql
    
    print_success "Sample data created successfully"
}

# Function to create environment file
create_env_file() {
    print_status "Creating environment file..."
    
    # Get RDS details
    RDS_ENDPOINT=$(terraform output -raw rds_endpoint)
    RDS_PASSWORD=$(terraform output -raw rds_password)
    
    # Create .env file
    cat > .env.hybrid << EOF
# Hybrid Database Configuration
ENVIRONMENT=${ENVIRONMENT}
AWS_REGION=${REGION}

# DynamoDB Tables
DYNAMODB_ORDERS_TABLE=vyaparai-orders-${ENVIRONMENT}
DYNAMODB_SESSIONS_TABLE=vyaparai-sessions-${ENVIRONMENT}
DYNAMODB_RATE_LIMITS_TABLE=vyaparai-rate-limits-${ENVIRONMENT}
DYNAMODB_STORES_TABLE=vyaparai-stores-${ENVIRONMENT}
DYNAMODB_PRODUCTS_TABLE=vyaparai-products-${ENVIRONMENT}
DYNAMODB_METRICS_TABLE=vyaparai-metrics-${ENVIRONMENT}

# RDS Configuration
RDS_HOSTNAME=${RDS_ENDPOINT}
RDS_PORT=5432
RDS_DATABASE=vyaparai
RDS_USERNAME=vyaparai_admin
RDS_PASSWORD=${RDS_PASSWORD}

# Redis Configuration (if using ElastiCache)
REDIS_ENDPOINT=localhost
REDIS_PORT=6379

# API Keys (update with your actual keys)
GOOGLE_API_KEY=your_google_api_key_here
GOOGLE_GENERATIVE_AI_API_KEY=your_google_generative_ai_key_here
GOOGLE_TRANSLATE_API_KEY=your_google_translate_key_here

# WhatsApp Configuration
WHATSAPP_ACCESS_TOKEN=your_whatsapp_token_here
WHATSAPP_VERIFY_TOKEN=your_whatsapp_verify_token_here

# Other Configuration
LOG_LEVEL=INFO
POWERTOOLS_SERVICE_NAME=vyaparai-api
POWERTOOLS_METRICS_NAMESPACE=VyaparAI
EOF
    
    print_success "Environment file created: .env.hybrid"
    print_warning "Please update the API keys in .env.hybrid with your actual keys"
}

# Function to display setup summary
display_summary() {
    print_status "Hybrid Database Setup Summary"
    echo "=================================="
    echo "Environment: $ENVIRONMENT"
    echo "Region: $REGION"
    echo ""
    echo "DynamoDB Tables Created:"
    echo "- vyaparai-orders-${ENVIRONMENT}"
    echo "- vyaparai-sessions-${ENVIRONMENT}"
    echo "- vyaparai-rate-limits-${ENVIRONMENT}"
    echo "- vyaparai-stores-${ENVIRONMENT}"
    echo "- vyaparai-products-${ENVIRONMENT}"
    echo "- vyaparai-metrics-${ENVIRONMENT}"
    echo ""
    echo "RDS PostgreSQL Instance:"
    RDS_ENDPOINT=$(terraform output -raw rds_endpoint)
    echo "- Endpoint: $RDS_ENDPOINT"
    echo "- Database: vyaparai"
    echo "- Username: vyaparai_admin"
    echo ""
    echo "Next Steps:"
    echo "1. Update API keys in .env.hybrid"
    echo "2. Deploy the application using Serverless Framework"
    echo "3. Test the hybrid database integration"
    echo ""
    print_success "Hybrid database setup completed successfully!"
}

# Main execution
main() {
    print_status "Starting VyaparAI Hybrid Database Setup"
    print_status "Environment: $ENVIRONMENT"
    print_status "Region: $REGION"
    echo ""
    
    # Check requirements
    check_requirements
    check_aws_config
    
    # Create DynamoDB tables
    create_dynamodb_tables
    wait_for_dynamodb_tables
    
    # Create RDS instance
    create_rds_instance
    
    # Run PostgreSQL migrations
    run_postgresql_migrations
    
    # Set up DynamoDB Streams
    setup_dynamodb_streams
    
    # Create sample data
    create_sample_data
    
    # Create environment file
    create_env_file
    
    # Display summary
    display_summary
}

# Handle script arguments
case "${1:-}" in
    "dev"|"staging"|"prod")
        main
        ;;
    *)
        print_error "Usage: $0 {dev|staging|prod}"
        print_status "Example: $0 dev"
        exit 1
        ;;
esac
