#!/bin/bash

echo "🔄 Updating Lambda Function..."

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
REGION=${AWS_REGION:-ap-south-1}
FUNCTION_NAME="vyaparai-api-prod"

echo -e "${YELLOW}Creating deployment package...${NC}"

# Create new zip file
zip -r lambda_handler_new.zip lambda_handler.py

echo -e "${YELLOW}Updating Lambda function: $FUNCTION_NAME${NC}"

# Update Lambda function code
aws lambda update-function-code \
    --function-name $FUNCTION_NAME \
    --zip-file fileb://lambda_handler_new.zip \
    --region $REGION

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Lambda function updated successfully!${NC}"
    echo -e "${YELLOW}Testing the updated function...${NC}"
    
    # Test the health endpoint
    sleep 5  # Wait for update to propagate
    
    echo "Testing health endpoint..."
    curl -X GET "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/health"
    
    echo -e "\n${GREEN}✅ Update complete!${NC}"
    echo "Monitor logs: aws logs tail /aws/lambda/$FUNCTION_NAME --follow"
else
    echo -e "${RED}❌ Failed to update Lambda function${NC}"
    exit 1
fi

# Clean up
rm -f lambda_handler_new.zip
