#!/bin/bash

echo "⚡ Quick Update Deployment"

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Get AWS account info
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=${AWS_REGION:-ap-south-1}

if [ "$1" == "backend" ]; then
    echo -e "\n${YELLOW}Updating backend...${NC}"
    
    cd backend
    
    # Create minimal deployment package
    echo "Creating deployment package..."
    rm -rf lambda-deploy
    mkdir -p lambda-deploy
    
    # Copy only the app directory (no dependencies)
    cp -r app lambda-deploy/
    
    # Create Lambda handler
    cat > lambda-deploy/lambda_handler.py <<'EOF'
import os
import sys
sys.path.insert(0, '/var/task')

from mangum import Mangum
from app.main import app

os.environ['ENVIRONMENT'] = os.environ.get('ENVIRONMENT', 'production')
handler = Mangum(app, lifespan="off")
EOF
    
    # Create zip
    cd lambda-deploy
    zip -r ../vyaparai-backend-quick.zip . -q
    cd ..
    
    # Update Lambda function
    echo "Updating Lambda function..."
    aws lambda update-function-code \
        --function-name vyaparai-api-prod \
        --zip-file fileb://vyaparai-backend-quick.zip \
        --region $REGION
    
    # Clean up
    rm -rf lambda-deploy
    rm -f vyaparai-backend-quick.zip
    
    cd ..
    
    echo -e "${GREEN}✅ Backend updated${NC}"
    echo "Monitor logs: aws logs tail /aws/lambda/vyaparai-api-prod --follow"
    
elif [ "$1" == "frontend" ]; then
    echo -e "\n${YELLOW}Updating frontend...${NC}"
    
    cd frontend-pwa
    
    # Quick build
    echo "Building frontend..."
    npm run build
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Build failed${NC}"
        exit 1
    fi
    
    # Upload to S3
    echo "Uploading to S3..."
    BUCKET_NAME="vyaparai-frontend-$ACCOUNT_ID"
    
    # Upload with cache invalidation
    aws s3 sync dist/ s3://$BUCKET_NAME/ \
        --cache-control "public, max-age=31536000" \
        --exclude "*.html" \
        --exclude "*.json" \
        --exclude "*.xml" \
        --quiet
    
    aws s3 sync dist/ s3://$BUCKET_NAME/ \
        --cache-control "no-cache" \
        --exclude "*" \
        --include "*.html" \
        --include "*.json" \
        --include "*.xml" \
        --quiet
    
    # Invalidate CloudFront cache
    echo "Invalidating CloudFront cache..."
    DISTRIBUTION_ID=$(aws cloudfront list-distributions \
        --query "DistributionList.Items[?Origins.Items[0].DomainName=='$BUCKET_NAME.s3.amazonaws.com'].Id | [0]" \
        --output text)
    
    if [ "$DISTRIBUTION_ID" != "None" ] && [ -n "$DISTRIBUTION_ID" ]; then
        aws cloudfront create-invalidation \
            --distribution-id $DISTRIBUTION_ID \
            --paths "/*" \
            --quiet
        
        echo -e "${GREEN}✅ Frontend updated and cache invalidated${NC}"
    else
        echo -e "${GREEN}✅ Frontend updated${NC}"
    fi
    
    cd ..
    
else
    echo -e "${RED}Usage: ./quick-update.sh [backend|frontend]${NC}"
    echo ""
    echo "Examples:"
    echo "  ./quick-update.sh backend   # Update backend code only"
    echo "  ./quick-update.sh frontend  # Update frontend code only"
    echo ""
    echo "Note: This is for quick code updates only."
    echo "For full deployments with dependencies, use:"
    echo "  ./deployment/deploy-backend.sh"
    echo "  ./deployment/deploy-frontend.sh"
fi



