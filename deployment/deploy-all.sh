#!/bin/bash

echo "🚀 Complete VyaparAI Deployment"
echo "================================"
echo ""

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Make scripts executable
chmod +x deployment/*.sh

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI not installed${NC}"
    echo "Install from: https://aws.amazon.com/cli/"
    exit 1
fi

# Check AWS credentials
aws sts get-caller-identity > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ AWS credentials not configured${NC}"
    echo "Run: aws configure"
    exit 1
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js not installed${NC}"
    echo "Install from: https://nodejs.org/"
    exit 1
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not installed${NC}"
    echo "Install from: https://python.org/"
    exit 1
fi

echo -e "${GREEN}✅ All prerequisites met${NC}"

# Step 1: Setup AWS Infrastructure
echo -e "\n${YELLOW}Step 1: Setting up AWS infrastructure...${NC}"
./deployment/setup-aws.sh
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Infrastructure setup failed${NC}"
    exit 1
fi

# Wait for RDS to be available
echo -e "\n${YELLOW}⏳ Waiting for RDS instance to be available (this may take 5-10 minutes)...${NC}"
aws rds wait db-instance-available --db-instance-identifier vyaparai-postgres-prod

# Get RDS endpoint
RDS_ENDPOINT=$(aws rds describe-db-instances \
    --db-instance-identifier vyaparai-postgres-prod \
    --query 'DBInstances[0].Endpoint.Address' \
    --output text)

echo -e "${GREEN}✅ RDS available at: $RDS_ENDPOINT${NC}"

# Step 2: Initialize database
echo -e "\n${YELLOW}Step 2: Initializing database...${NC}"

# Check if PostgreSQL client is available
if command -v psql &> /dev/null; then
    echo "Creating database..."
    PGPASSWORD=VyaparAI2024Secure! psql -h $RDS_ENDPOINT -U vyaparai_admin -d postgres -c "CREATE DATABASE vyaparai;" 2>/dev/null || true

    # Run migrations (if you have any SQL files)
    if [ -f backend/scripts/init-db.sql ]; then
        echo "Running database migrations..."
        PGPASSWORD=VyaparAI2024Secure! psql -h $RDS_ENDPOINT -U vyaparai_admin -d vyaparai < backend/scripts/init-db.sql
    fi
else
    echo -e "${YELLOW}⚠️ PostgreSQL client not found. Database initialization skipped.${NC}"
    echo "You can manually create the database later using:"
    echo "PGPASSWORD=VyaparAI2024Secure! psql -h $RDS_ENDPOINT -U vyaparai_admin -d postgres -c 'CREATE DATABASE vyaparai;'"
fi

# Step 3: Deploy Backend
echo -e "\n${YELLOW}Step 3: Deploying backend...${NC}"
./deployment/deploy-backend.sh
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Backend deployment failed${NC}"
    exit 1
fi

# Step 4: Deploy Frontend
echo -e "\n${YELLOW}Step 4: Deploying frontend...${NC}"
./deployment/deploy-frontend.sh
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Frontend deployment failed${NC}"
    exit 1
fi

# Step 5: Test deployment
echo -e "\n${YELLOW}Step 5: Testing deployment...${NC}"

# Load environment
if [ -f deployment/.env.production ]; then
    source deployment/.env.production
    
    # Test backend health
    echo "Testing backend API..."
    HEALTH_RESPONSE=$(curl -s "$VITE_API_BASE_URL/health" 2>/dev/null)
    if [[ $HEALTH_RESPONSE == *"status"* ]]; then
        echo -e "${GREEN}✅ Backend health check passed${NC}"
    else
        echo -e "${RED}❌ Backend health check failed${NC}"
        echo "Response: $HEALTH_RESPONSE"
    fi
    
    # Test order creation
    echo "Testing order creation..."
    ORDER_RESPONSE=$(curl -s -X POST "$VITE_API_BASE_URL/api/v1/orders/test/generate-order" \
        -H "Content-Type: application/json" \
        -d '{"store_id": "STORE-001"}' 2>/dev/null)
    if [[ $ORDER_RESPONSE == *"success"* ]]; then
        echo -e "${GREEN}✅ Order creation test passed${NC}"
    else
        echo -e "${RED}❌ Order creation test failed${NC}"
        echo "Response: $ORDER_RESPONSE"
    fi
else
    echo -e "${RED}❌ Environment file not found${NC}"
fi

# Get CloudFront domain for frontend test
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET_NAME="vyaparai-frontend-$ACCOUNT_ID"

DISTRIBUTION_ID=$(aws cloudfront list-distributions \
    --query "DistributionList.Items[?Origins.Items[0].DomainName=='$BUCKET_NAME.s3.amazonaws.com'].Id | [0]" \
    --output text)

if [ "$DISTRIBUTION_ID" != "None" ] && [ -n "$DISTRIBUTION_ID" ]; then
    CF_DOMAIN=$(aws cloudfront get-distribution \
        --id $DISTRIBUTION_ID \
        --query Distribution.DomainName \
        --output text)
    
    echo "Testing frontend..."
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://$CF_DOMAIN)
    if [ "$STATUS" == "200" ]; then
        echo -e "${GREEN}✅ Frontend accessible at https://$CF_DOMAIN${NC}"
    else
        echo -e "${RED}❌ Frontend returned status: $STATUS${NC}"
    fi
fi

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}🎉 VyaparAI Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "📱 Your app is live at:"
if [ -n "$CF_DOMAIN" ]; then
    echo "   Frontend: https://$CF_DOMAIN"
fi
if [ -n "$VITE_API_BASE_URL" ]; then
    echo "   Backend API: $VITE_API_BASE_URL"
fi
echo ""
echo "📝 Next steps:"
echo "1. Test the application functionality"
echo "2. Configure custom domain (optional)"
echo "3. Set up monitoring and alerts"
echo "4. Enable automated backups"
echo "5. Configure SSL certificates"
echo ""
echo "🛠️ Useful commands:"
echo "   Monitor logs: aws logs tail /aws/lambda/vyaparai-api-prod --follow"
echo "   Update backend: ./deployment/deploy-backend.sh"
echo "   Update frontend: ./deployment/deploy-frontend.sh"
echo "   Quick update: ./deployment/quick-update.sh [backend|frontend]"
echo ""
echo "📊 Monitor resources:"
echo "   Lambda: aws lambda get-function --function-name vyaparai-api-prod"
echo "   RDS: aws rds describe-db-instances --db-instance-identifier vyaparai-postgres-prod"
echo "   CloudFront: aws cloudfront get-distribution --id $DISTRIBUTION_ID"
echo ""
echo "🔧 Troubleshooting:"
echo "   Check CloudWatch logs for errors"
echo "   Verify environment variables in Lambda"
echo "   Test database connectivity"
echo "   Check S3 bucket permissions"



