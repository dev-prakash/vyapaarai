#!/bin/bash

echo "📦 Deploying VyaparAI Backend to AWS Lambda"
echo "=========================================="

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Get AWS account info
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=${AWS_REGION:-ap-south-1}

echo -e "${GREEN}✓ AWS Account: $ACCOUNT_ID${NC}"
echo -e "${GREEN}✓ Region: $REGION${NC}"

# Create deployment package
echo -e "\n${YELLOW}📦 Creating deployment package...${NC}"

cd backend

# Create a temporary directory for deployment
rm -rf lambda-deploy
mkdir -p lambda-deploy

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt -t lambda-deploy/ --platform manylinux2014_x86_64 --only-binary=:all: --quiet

# Install additional Lambda-specific dependencies
pip install mangum -t lambda-deploy/ --platform manylinux2014_x86_64 --only-binary=:all: --quiet

# Copy application code
echo "Copying application code..."
cp -r app lambda-deploy/

# Create Lambda handler file
cat > lambda-deploy/lambda_handler.py <<'EOF'
import os
import sys
sys.path.insert(0, '/var/task')

from mangum import Mangum
from app.main import app

# Configure environment
os.environ['ENVIRONMENT'] = os.environ.get('ENVIRONMENT', 'production')

# Create Lambda handler
handler = Mangum(app, lifespan="off")
EOF

# Create deployment zip
echo "Creating deployment package..."
cd lambda-deploy
zip -r ../vyaparai-backend.zip . -q
cd ..

echo -e "${GREEN}✅ Deployment package created ($(du -h vyaparai-backend.zip | cut -f1))${NC}"

# Get RDS endpoint
echo -e "\n${YELLOW}🔍 Getting RDS endpoint...${NC}"
RDS_ENDPOINT=$(aws rds describe-db-instances \
    --db-instance-identifier vyaparai-postgres-prod \
    --query 'DBInstances[0].Endpoint.Address' \
    --output text 2>/dev/null)

if [ "$RDS_ENDPOINT" == "None" ] || [ -z "$RDS_ENDPOINT" ]; then
    echo -e "${RED}❌ RDS endpoint not found. Make sure RDS is running.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ RDS Endpoint: $RDS_ENDPOINT${NC}"

# Create Lambda function
echo -e "\n${YELLOW}🚀 Deploying to Lambda...${NC}"

# Check if function exists
aws lambda get-function --function-name vyaparai-api-prod 2>/dev/null
if [ $? -eq 0 ]; then
    # Update existing function
    echo "Updating existing Lambda function..."
    aws lambda update-function-code \
        --function-name vyaparai-api-prod \
        --zip-file fileb://vyaparai-backend.zip \
        --region $REGION
    
    # Update environment variables
    aws lambda update-function-configuration \
        --function-name vyaparai-api-prod \
        --environment Variables="{
            ENVIRONMENT=production,
            DATABASE_URL=postgresql://vyaparai_admin:VyaparAI2024Secure!@$RDS_ENDPOINT/vyaparai,
            DYNAMODB_ORDERS_TABLE=vyaparai-orders-prod,
            DYNAMODB_SESSIONS_TABLE=vyaparai-sessions-prod,
            JWT_SECRET=vyaparai-jwt-secret-2024-secure,
            GOOGLE_API_KEY=${GOOGLE_API_KEY:-your-google-api-key},
            REDIS_URL=redis://vyaparai-redis-prod.xxxxx.cache.amazonaws.com:6379
        }" \
        --region $REGION
else
    # Create new function
    echo "Creating new Lambda function..."
    aws lambda create-function \
        --function-name vyaparai-api-prod \
        --runtime python3.11 \
        --role arn:aws:iam::$ACCOUNT_ID:role/vyaparai-lambda-role \
        --handler lambda_handler.handler \
        --zip-file fileb://vyaparai-backend.zip \
        --timeout 30 \
        --memory-size 512 \
        --environment Variables="{
            ENVIRONMENT=production,
            DATABASE_URL=postgresql://vyaparai_admin:VyaparAI2024Secure!@$RDS_ENDPOINT/vyaparai,
            DYNAMODB_ORDERS_TABLE=vyaparai-orders-prod,
            DYNAMODB_SESSIONS_TABLE=vyaparai-sessions-prod,
            JWT_SECRET=vyaparai-jwt-secret-2024-secure,
            GOOGLE_API_KEY=${GOOGLE_API_KEY:-your-google-api-key},
            REDIS_URL=redis://vyaparai-redis-prod.xxxxx.cache.amazonaws.com:6379
        }" \
        --region $REGION
fi

# Create Lambda function URL
echo -e "\n${YELLOW}🔗 Creating function URL...${NC}"

FUNCTION_URL=$(aws lambda create-function-url-config \
    --function-name vyaparai-api-prod \
    --auth-type NONE \
    --cors '{
        "AllowOrigins": ["*"],
        "AllowMethods": ["*"],
        "AllowHeaders": ["*"],
        "MaxAge": 86400
    }' \
    --query FunctionUrl \
    --output text \
    --region $REGION 2>/dev/null)

if [ -z "$FUNCTION_URL" ]; then
    FUNCTION_URL=$(aws lambda get-function-url-config \
        --function-name vyaparai-api-prod \
        --query FunctionUrl \
        --output text \
        --region $REGION)
fi

echo -e "${GREEN}✅ Backend deployed!${NC}"
echo -e "${GREEN}🔗 API URL: $FUNCTION_URL${NC}"

# Save URL for frontend deployment
mkdir -p ../deployment
echo "VITE_API_BASE_URL=$FUNCTION_URL" > ../deployment/.env.production

# Test the deployment
echo -e "\n${YELLOW}🧪 Testing deployment...${NC}"
sleep 10  # Wait for function to be ready

HEALTH_RESPONSE=$(curl -s "$FUNCTION_URL/health" 2>/dev/null)
if [[ $HEALTH_RESPONSE == *"status"* ]]; then
    echo -e "${GREEN}✅ Health check passed${NC}"
else
    echo -e "${RED}❌ Health check failed${NC}"
    echo "Response: $HEALTH_RESPONSE"
fi

# Clean up
rm -rf lambda-deploy
rm -f vyaparai-backend.zip

cd ..

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Backend Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "🔗 API URL: $FUNCTION_URL"
echo "📊 Monitor logs: aws logs tail /aws/lambda/vyaparai-api-prod --follow"
echo ""
echo "Next step: Run ./deployment/deploy-frontend.sh"



