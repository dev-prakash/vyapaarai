#!/bin/bash

# VyaparAI Complete AWS Deployment Script
# Deploys frontend to S3 + CloudFront with vyapaarai.com domain

set -e

# Configuration
DOMAIN="vyapaarai.com"
WWW_DOMAIN="www.vyapaarai.com"
S3_BUCKET="vyapaarai.com"
S3_BUCKET_WWW="www.vyapaarai.com"
AWS_REGION="ap-south-1"
CLOUDFRONT_REGION="us-east-1"  # CloudFront certificates must be in us-east-1

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "=========================================="
echo "VyaparAI AWS Deployment"
echo "Domain: $DOMAIN"
echo "=========================================="

# Step 1: Create S3 buckets for website hosting
echo -e "\n${YELLOW}Step 1: Creating S3 buckets...${NC}"

# Create main domain bucket
aws s3api create-bucket \
    --bucket $S3_BUCKET \
    --region $AWS_REGION \
    --create-bucket-configuration LocationConstraint=$AWS_REGION 2>/dev/null || echo "Bucket $S3_BUCKET already exists"

# Create www redirect bucket
aws s3api create-bucket \
    --bucket $S3_BUCKET_WWW \
    --region $AWS_REGION \
    --create-bucket-configuration LocationConstraint=$AWS_REGION 2>/dev/null || echo "Bucket $S3_BUCKET_WWW already exists"

# Configure main bucket for static website hosting
echo -e "${YELLOW}Configuring static website hosting...${NC}"
aws s3 website s3://$S3_BUCKET/ \
    --index-document index.html \
    --error-document index.html

# Configure www bucket to redirect to main domain
cat > /tmp/redirect.json << EOF
{
    "RedirectAllRequestsTo": {
        "HostName": "$DOMAIN",
        "Protocol": "https"
    }
}
EOF

aws s3api put-bucket-website \
    --bucket $S3_BUCKET_WWW \
    --website-configuration file:///tmp/redirect.json

# Set bucket policy for public access
echo -e "${YELLOW}Setting bucket policies...${NC}"
cat > /tmp/bucket-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::$S3_BUCKET/*"
        }
    ]
}
EOF

aws s3api put-bucket-policy \
    --bucket $S3_BUCKET \
    --policy file:///tmp/bucket-policy.json

# Disable block public access
aws s3api put-public-access-block \
    --bucket $S3_BUCKET \
    --public-access-block-configuration \
    "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

echo -e "${GREEN}✓ S3 buckets configured${NC}"

# Step 2: Build the frontend
echo -e "\n${YELLOW}Step 2: Building frontend...${NC}"
cd frontend-pwa

# Update environment for production
cat > .env.production << EOF
VITE_API_BASE_URL=https://jxxi8dtx1f.execute-api.ap-south-1.amazonaws.com
VITE_WS_URL=wss://jxxi8dtx1f.execute-api.ap-south-1.amazonaws.com
VITE_VAPID_PUBLIC_KEY=BKd0EoJ1XDLH1y3UPCQhWZxkPBvHH1cxcVVc_1234567890
VITE_ENV=production
VITE_ENABLE_MOCK_DATA=false
VITE_USE_AWS_DB=true
VITE_DOMAIN=https://vyapaarai.com
EOF

# Build the production bundle
npm run build

echo -e "${GREEN}✓ Frontend built${NC}"

# Step 3: Deploy to S3
echo -e "\n${YELLOW}Step 3: Deploying to S3...${NC}"

# Sync build files to S3
aws s3 sync dist/ s3://$S3_BUCKET/ \
    --delete \
    --cache-control "public, max-age=31536000" \
    --exclude "index.html" \
    --exclude "*.json"

# Upload index.html and JSON files with no cache
aws s3 cp dist/index.html s3://$S3_BUCKET/index.html \
    --cache-control "no-cache, no-store, must-revalidate" \
    --content-type "text/html"

aws s3 sync dist/ s3://$S3_BUCKET/ \
    --exclude "*" \
    --include "*.json" \
    --cache-control "no-cache, no-store, must-revalidate"

echo -e "${GREEN}✓ Frontend deployed to S3${NC}"

# Step 4: Request SSL Certificate
echo -e "\n${YELLOW}Step 4: Requesting SSL certificate...${NC}"

# Request certificate (must be in us-east-1 for CloudFront)
CERT_ARN=$(aws acm request-certificate \
    --domain-name $DOMAIN \
    --subject-alternative-names $WWW_DOMAIN \
    --validation-method DNS \
    --region $CLOUDFRONT_REGION \
    --query CertificateArn \
    --output text)

echo "Certificate ARN: $CERT_ARN"
echo -e "${YELLOW}Please validate the certificate in AWS Console before proceeding${NC}"
echo "Go to: https://console.aws.amazon.com/acm/home?region=us-east-1"

# Step 5: Create CloudFront distribution
echo -e "\n${YELLOW}Step 5: Creating CloudFront distribution...${NC}"

cat > /tmp/cloudfront-config.json << EOF
{
    "CallerReference": "vyaparai-$(date +%s)",
    "Aliases": {
        "Quantity": 2,
        "Items": ["$DOMAIN", "$WWW_DOMAIN"]
    },
    "DefaultRootObject": "index.html",
    "Origins": {
        "Quantity": 1,
        "Items": [
            {
                "Id": "S3-$S3_BUCKET",
                "DomainName": "$S3_BUCKET.s3-website.$AWS_REGION.amazonaws.com",
                "CustomOriginConfig": {
                    "HTTPPort": 80,
                    "HTTPSPort": 443,
                    "OriginProtocolPolicy": "http-only"
                }
            }
        ]
    },
    "DefaultCacheBehavior": {
        "TargetOriginId": "S3-$S3_BUCKET",
        "ViewerProtocolPolicy": "redirect-to-https",
        "TrustedSigners": {
            "Enabled": false,
            "Quantity": 0
        },
        "ForwardedValues": {
            "QueryString": false,
            "Cookies": { "Forward": "none" }
        },
        "MinTTL": 0,
        "Compress": true
    },
    "CustomErrorResponses": {
        "Quantity": 1,
        "Items": [
            {
                "ErrorCode": 404,
                "ResponsePagePath": "/index.html",
                "ResponseCode": "200",
                "ErrorCachingMinTTL": 300
            }
        ]
    },
    "Comment": "VyaparAI Production",
    "Enabled": true,
    "ViewerCertificate": {
        "ACMCertificateArn": "$CERT_ARN",
        "SSLSupportMethod": "sni-only",
        "MinimumProtocolVersion": "TLSv1.2_2021"
    }
}
EOF

# Create distribution
DISTRIBUTION_ID=$(aws cloudfront create-distribution \
    --distribution-config file:///tmp/cloudfront-config.json \
    --query Distribution.Id \
    --output text)

echo "CloudFront Distribution ID: $DISTRIBUTION_ID"

# Get CloudFront domain
CF_DOMAIN=$(aws cloudfront get-distribution \
    --id $DISTRIBUTION_ID \
    --query Distribution.DomainName \
    --output text)

echo -e "${GREEN}✓ CloudFront distribution created: $CF_DOMAIN${NC}"

# Step 6: Configure Route53
echo -e "\n${YELLOW}Step 6: Configuring Route53...${NC}"

# Get hosted zone ID
ZONE_ID=$(aws route53 list-hosted-zones-by-name \
    --query "HostedZones[?Name=='$DOMAIN.'].Id" \
    --output text | cut -d'/' -f3)

if [ -z "$ZONE_ID" ]; then
    echo -e "${RED}Error: No hosted zone found for $DOMAIN${NC}"
    echo "Please create a hosted zone in Route53 first"
    exit 1
fi

echo "Hosted Zone ID: $ZONE_ID"

# Create Route53 records
cat > /tmp/route53-records.json << EOF
{
    "Changes": [
        {
            "Action": "UPSERT",
            "ResourceRecordSet": {
                "Name": "$DOMAIN",
                "Type": "A",
                "AliasTarget": {
                    "HostedZoneId": "Z2FDTNDATAQYW2",
                    "DNSName": "$CF_DOMAIN",
                    "EvaluateTargetHealth": false
                }
            }
        },
        {
            "Action": "UPSERT",
            "ResourceRecordSet": {
                "Name": "$WWW_DOMAIN",
                "Type": "A",
                "AliasTarget": {
                    "HostedZoneId": "Z2FDTNDATAQYW2",
                    "DNSName": "$CF_DOMAIN",
                    "EvaluateTargetHealth": false
                }
            }
        }
    ]
}
EOF

aws route53 change-resource-record-sets \
    --hosted-zone-id $ZONE_ID \
    --change-batch file:///tmp/route53-records.json

echo -e "${GREEN}✓ Route53 DNS configured${NC}"

# Cleanup temp files
rm -f /tmp/redirect.json /tmp/bucket-policy.json /tmp/cloudfront-config.json /tmp/route53-records.json

# Summary
echo -e "\n${GREEN}=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "Website URLs:"
echo "  Main: https://$DOMAIN"
echo "  WWW: https://$WWW_DOMAIN"
echo "  CloudFront: https://$CF_DOMAIN"
echo ""
echo "S3 Buckets:"
echo "  Main: s3://$S3_BUCKET"
echo "  WWW: s3://$S3_BUCKET_WWW"
echo ""
echo "CloudFront Distribution: $DISTRIBUTION_ID"
echo ""
echo "Next Steps:"
echo "1. Validate SSL certificate in ACM Console (us-east-1)"
echo "2. Wait 15-30 minutes for DNS propagation"
echo "3. Test at https://$DOMAIN"
echo "==========================================="
echo ""
echo "To update the site later, run:"
echo "  npm run build"
echo "  aws s3 sync dist/ s3://$S3_BUCKET/ --delete"
echo "  aws cloudfront create-invalidation --distribution-id $DISTRIBUTION_ID --paths '/*'"
echo "=========================================="${NC}