#!/bin/bash

echo "🎨 Deploying VyaparAI Frontend to S3/CloudFront"
echo "=============================================="

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Get AWS account info
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=${AWS_REGION:-ap-south-1}
BUCKET_NAME="vyaparai-frontend-$ACCOUNT_ID"

echo -e "${GREEN}✓ AWS Account: $ACCOUNT_ID${NC}"
echo -e "${GREEN}✓ Region: $REGION${NC}"
echo -e "${GREEN}✓ S3 Bucket: $BUCKET_NAME${NC}"

# Load backend URL from previous deployment
if [ ! -f deployment/.env.production ]; then
    echo -e "${RED}❌ Backend deployment file not found. Run deploy-backend.sh first.${NC}"
    exit 1
fi

source deployment/.env.production

if [ -z "$VITE_API_BASE_URL" ]; then
    echo -e "${RED}❌ Backend URL not found. Run deploy-backend.sh first.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Backend URL: $VITE_API_BASE_URL${NC}"

# Build frontend
echo -e "\n${YELLOW}🔨 Building frontend...${NC}"

cd frontend-pwa

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js not installed${NC}"
    exit 1
fi

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo -e "${RED}❌ npm not installed${NC}"
    exit 1
fi

# Create production env file
cat > .env.production <<EOF
VITE_API_BASE_URL=$VITE_API_BASE_URL/api/v1
VITE_WS_URL=wss://not-configured-yet
VITE_ENV=production
VITE_ENABLE_MOCK_DATA=false
VITE_VAPID_PUBLIC_KEY=BKd0EoJ1XDLH1y3UPCQhWZxkPBvHH1cxcVVc_1234567890
EOF

echo "Production environment configured:"
cat .env.production

# Install dependencies
echo "Installing npm dependencies..."
npm install --silent

# Build the application
echo "Building application..."
npm run build

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Build failed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Frontend built successfully${NC}"

# Upload to S3
echo -e "\n${YELLOW}📤 Uploading to S3...${NC}"

# Clear existing files
echo "Clearing existing files..."
aws s3 rm s3://$BUCKET_NAME/ --recursive --quiet

# Upload new build with proper cache headers
echo "Uploading static assets with cache headers..."
aws s3 sync dist/ s3://$BUCKET_NAME/ \
    --cache-control "public, max-age=31536000" \
    --exclude "*.html" \
    --exclude "*.json" \
    --exclude "*.xml" \
    --quiet

# Upload HTML files with no-cache
echo "Uploading HTML files with no-cache..."
aws s3 sync dist/ s3://$BUCKET_NAME/ \
    --cache-control "no-cache" \
    --exclude "*" \
    --include "*.html" \
    --include "*.json" \
    --include "*.xml" \
    --quiet

# Upload service worker with no-cache
echo "Uploading service worker..."
aws s3 cp dist/sw.js s3://$BUCKET_NAME/sw.js \
    --cache-control "no-cache" \
    --quiet

echo -e "${GREEN}✅ Frontend deployed to S3${NC}"

# Create CloudFront distribution
echo -e "\n${YELLOW}☁️ Setting up CloudFront CDN...${NC}"

# Check if distribution exists
DISTRIBUTION_ID=$(aws cloudfront list-distributions \
    --query "DistributionList.Items[?Origins.Items[0].DomainName=='$BUCKET_NAME.s3.amazonaws.com'].Id | [0]" \
    --output text)

if [ "$DISTRIBUTION_ID" == "None" ] || [ -z "$DISTRIBUTION_ID" ]; then
    # Create new distribution
    echo "Creating new CloudFront distribution..."
    
    cat > /tmp/cf-config.json <<EOF
{
    "CallerReference": "vyaparai-$(date +%s)",
    "Comment": "VyaparAI PWA Distribution",
    "DefaultRootObject": "index.html",
    "Enabled": true,
    "Origins": {
        "Quantity": 1,
        "Items": [
            {
                "Id": "S3-$BUCKET_NAME",
                "DomainName": "$BUCKET_NAME.s3-website.$REGION.amazonaws.com",
                "CustomOriginConfig": {
                    "HTTPPort": 80,
                    "HTTPSPort": 443,
                    "OriginProtocolPolicy": "http-only"
                }
            }
        ]
    },
    "DefaultCacheBehavior": {
        "TargetOriginId": "S3-$BUCKET_NAME",
        "ViewerProtocolPolicy": "redirect-to-https",
        "AllowedMethods": {
            "Quantity": 7,
            "Items": ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"],
            "CachedMethods": {
                "Quantity": 2,
                "Items": ["GET", "HEAD"]
            }
        },
        "Compress": true,
        "ForwardedValues": {
            "QueryString": false,
            "Cookies": { "Forward": "none" }
        },
        "TrustedSigners": {
            "Enabled": false,
            "Quantity": 0
        },
        "MinTTL": 0,
        "DefaultTTL": 86400,
        "MaxTTL": 31536000
    },
    "CustomErrorResponses": {
        "Quantity": 1,
        "Items": [
            {
                "ErrorCode": 404,
                "ResponseCode": "200",
                "ResponsePagePath": "/index.html",
                "ErrorCachingMinTTL": 0
            }
        ]
    },
    "PriceClass": "PriceClass_100"
}
EOF

    DISTRIBUTION_ID=$(aws cloudfront create-distribution \
        --distribution-config file:///tmp/cf-config.json \
        --query Distribution.Id \
        --output text)
    
    echo -e "${GREEN}✅ CloudFront distribution created: $DISTRIBUTION_ID${NC}"
    
    # Wait for distribution to be deployed
    echo "Waiting for CloudFront distribution to be deployed..."
    aws cloudfront wait distribution-deployed --id $DISTRIBUTION_ID
    
else
    # Invalidate existing distribution
    echo "Invalidating existing CloudFront cache..."
    aws cloudfront create-invalidation \
        --distribution-id $DISTRIBUTION_ID \
        --paths "/*" \
        --quiet
    
    echo -e "${GREEN}✅ CloudFront cache invalidated${NC}"
fi

# Get CloudFront domain
CF_DOMAIN=$(aws cloudfront get-distribution \
    --id $DISTRIBUTION_ID \
    --query Distribution.DomainName \
    --output text)

# Test the deployment
echo -e "\n${YELLOW}🧪 Testing frontend deployment...${NC}"
sleep 30  # Wait for CloudFront to propagate

STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://$CF_DOMAIN)
if [ "$STATUS" == "200" ]; then
    echo -e "${GREEN}✅ Frontend accessible at https://$CF_DOMAIN${NC}"
else
    echo -e "${RED}❌ Frontend returned status: $STATUS${NC}"
    echo "Trying S3 website directly..."
    S3_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://$BUCKET_NAME.s3-website.$REGION.amazonaws.com)
    if [ "$S3_STATUS" == "200" ]; then
        echo -e "${GREEN}✅ S3 website accessible${NC}"
    else
        echo -e "${RED}❌ S3 website returned status: $S3_STATUS${NC}"
    fi
fi

# Clean up
rm -f /tmp/cf-config.json

cd ..

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Frontend Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "📱 Access your app at:"
echo "   https://$CF_DOMAIN"
echo ""
echo "🌐 S3 Website:"
echo "   http://$BUCKET_NAME.s3-website.$REGION.amazonaws.com"
echo ""
echo "📊 Monitor CloudFront:"
echo "   aws cloudfront get-distribution --id $DISTRIBUTION_ID"
echo ""
echo "Next step: Run ./deployment/test-deployment.sh"



