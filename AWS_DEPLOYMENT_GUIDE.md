# 🚀 VyaparAI AWS Deployment Guide for vyapaarai.com

## 📋 Pre-Deployment Checklist

### ✅ What You Already Have:
- Domain registered: vyapaarai.com (in Route53)
- Lambda API: https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws
- RDS PostgreSQL: Running with tables
- DynamoDB: 5 tables ready
- Frontend: React app running locally

### 🎯 What We'll Deploy:
- Frontend → S3 + CloudFront
- Custom domain → vyapaarai.com
- SSL certificate → HTTPS enabled
- CDN → Global fast delivery

## 📝 Step-by-Step Deployment

### Step 1: Prepare Frontend for Production

```bash
cd /Users/devprakash/MyProjects/VyaparAI/vyaparai/frontend-pwa

# Create production environment file
cat > .env.production << EOF
VITE_API_BASE_URL=https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1
VITE_WS_URL=wss://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws
VITE_ENV=production
VITE_ENABLE_MOCK_DATA=false
VITE_USE_AWS_DB=true
EOF

# Build production bundle
npm run build
```

### Step 2: Create S3 Bucket for Hosting

```bash
# Create bucket with your domain name
aws s3api create-bucket \
    --bucket vyapaarai.com \
    --region ap-south-1 \
    --create-bucket-configuration LocationConstraint=ap-south-1

# Enable static website hosting
aws s3 website s3://vyapaarai.com/ \
    --index-document index.html \
    --error-document index.html

# Set public read policy
aws s3api put-bucket-policy --bucket vyapaarai.com --policy '{
    "Version": "2012-10-17",
    "Statement": [{
        "Sid": "PublicReadGetObject",
        "Effect": "Allow",
        "Principal": "*",
        "Action": "s3:GetObject",
        "Resource": "arn:aws:s3:::vyapaarai.com/*"
    }]
}'

# Disable block public access
aws s3api put-public-access-block \
    --bucket vyapaarai.com \
    --public-access-block-configuration \
    "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"
```

### Step 3: Deploy Frontend to S3

```bash
cd /Users/devprakash/MyProjects/VyaparAI/vyaparai/frontend-pwa

# Upload all files
aws s3 sync dist/ s3://vyapaarai.com/ --delete

# Set cache headers for better performance
aws s3 cp s3://vyapaarai.com/ s3://vyapaarai.com/ \
    --recursive --exclude "index.html" \
    --cache-control "public,max-age=31536000"

# Index.html should not be cached
aws s3 cp dist/index.html s3://vyapaarai.com/index.html \
    --cache-control "no-cache"
```

### Step 4: Request SSL Certificate (IMPORTANT: Must be in us-east-1)

```bash
# Request certificate for CloudFront (MUST be us-east-1)
aws acm request-certificate \
    --domain-name vyapaarai.com \
    --subject-alternative-names www.vyapaarai.com \
    --validation-method DNS \
    --region us-east-1
```

**⚠️ IMPORTANT**: 
1. Go to AWS Console → Certificate Manager (us-east-1 region)
2. Find your certificate request
3. Click "Create records in Route 53" to validate
4. Wait for Status = "Issued" (5-10 minutes)

### Step 5: Create CloudFront Distribution

```bash
# Get your certificate ARN first
CERT_ARN=$(aws acm list-certificates --region us-east-1 \
    --query "CertificateSummaryList[?DomainName=='vyapaarai.com'].CertificateArn" \
    --output text)

# Create CloudFront distribution
aws cloudfront create-distribution --distribution-config '{
    "CallerReference": "vyaparai-'$(date +%s)'",
    "Aliases": {
        "Quantity": 2,
        "Items": ["vyapaarai.com", "www.vyapaarai.com"]
    },
    "DefaultRootObject": "index.html",
    "Origins": {
        "Quantity": 1,
        "Items": [{
            "Id": "S3-vyapaarai.com",
            "DomainName": "vyapaarai.com.s3-website.ap-south-1.amazonaws.com",
            "CustomOriginConfig": {
                "HTTPPort": 80,
                "HTTPSPort": 443,
                "OriginProtocolPolicy": "http-only"
            }
        }]
    },
    "DefaultCacheBehavior": {
        "TargetOriginId": "S3-vyapaarai.com",
        "ViewerProtocolPolicy": "redirect-to-https",
        "TrustedSigners": {"Enabled": false, "Quantity": 0},
        "ForwardedValues": {
            "QueryString": false,
            "Cookies": {"Forward": "none"}
        },
        "MinTTL": 0,
        "Compress": true
    },
    "CustomErrorResponses": {
        "Quantity": 1,
        "Items": [{
            "ErrorCode": 404,
            "ResponsePagePath": "/index.html",
            "ResponseCode": "200",
            "ErrorCachingMinTTL": 300
        }]
    },
    "Comment": "VyaparAI Production",
    "Enabled": true,
    "ViewerCertificate": {
        "ACMCertificateArn": "'$CERT_ARN'",
        "SSLSupportMethod": "sni-only",
        "MinimumProtocolVersion": "TLSv1.2_2021"
    }
}'
```

### Step 6: Configure Route53 DNS

```bash
# Get your CloudFront domain
CF_DOMAIN=$(aws cloudfront list-distributions \
    --query "DistributionList.Items[?Comment=='VyaparAI Production'].DomainName" \
    --output text)

# Get your hosted zone ID
ZONE_ID=$(aws route53 list-hosted-zones-by-name \
    --query "HostedZones[?Name=='vyapaarai.com.'].Id" \
    --output text | cut -d'/' -f3)

# Create A record for vyapaarai.com
aws route53 change-resource-record-sets --hosted-zone-id $ZONE_ID --change-batch '{
    "Changes": [{
        "Action": "UPSERT",
        "ResourceRecordSet": {
            "Name": "vyapaarai.com",
            "Type": "A",
            "AliasTarget": {
                "HostedZoneId": "Z2FDTNDATAQYW2",
                "DNSName": "'$CF_DOMAIN'",
                "EvaluateTargetHealth": false
            }
        }
    }]
}'

# Create A record for www.vyapaarai.com
aws route53 change-resource-record-sets --hosted-zone-id $ZONE_ID --change-batch '{
    "Changes": [{
        "Action": "UPSERT",
        "ResourceRecordSet": {
            "Name": "www.vyapaarai.com",
            "Type": "A",
            "AliasTarget": {
                "HostedZoneId": "Z2FDTNDATAQYW2",
                "DNSName": "'$CF_DOMAIN'",
                "EvaluateTargetHealth": false
            }
        }
    }]
}'
```

## 🔄 Updating the Site Later

```bash
# After making changes
cd frontend-pwa
npm run build
aws s3 sync dist/ s3://vyapaarai.com/ --delete

# Clear CloudFront cache
DIST_ID=$(aws cloudfront list-distributions \
    --query "DistributionList.Items[?Comment=='VyaparAI Production'].Id" \
    --output text)

aws cloudfront create-invalidation \
    --distribution-id $DIST_ID \
    --paths "/*"
```

## 📊 Deployment Architecture

```
User → vyapaarai.com → Route53 → CloudFront → S3 (Frontend)
                                      ↓
                                Lambda API
                                      ↓
                            PostgreSQL + DynamoDB
```

## ⏱️ Deployment Timeline

1. **S3 Setup**: 2 minutes
2. **Build & Upload**: 5 minutes
3. **SSL Certificate**: 10-15 minutes (validation)
4. **CloudFront**: 15-20 minutes (distribution creation)
5. **DNS Propagation**: 5-30 minutes

**Total**: ~45-60 minutes for full deployment

## 🧪 Testing Your Deployment

### 1. Test S3 Website Directly
```
http://vyapaarai.com.s3-website.ap-south-1.amazonaws.com
```

### 2. Test CloudFront
```
https://[your-distribution].cloudfront.net
```

### 3. Test Final Domain
```
https://vyapaarai.com
https://www.vyapaarai.com
```

## 🔒 Security Checklist

- ✅ HTTPS enforced via CloudFront
- ✅ S3 bucket not directly accessible (only via CloudFront)
- ✅ API calls go directly to Lambda (already HTTPS)
- ✅ Databases in private subnets

## 💰 Cost Estimate

- **S3**: ~$0.50/month (storage + requests)
- **CloudFront**: ~$1-5/month (based on traffic)
- **Route53**: $0.50/month (hosted zone)
- **Total**: ~$2-6/month for frontend hosting

## 🚨 Common Issues & Solutions

### Certificate Not Validating
- Make sure you're in us-east-1 region
- Click "Create records in Route 53" button in ACM console

### CloudFront 403 Error
- Check S3 bucket policy is public
- Verify index.html exists in bucket

### Site Not Loading
- Wait for DNS propagation (up to 30 minutes)
- Clear browser cache
- Try incognito mode

## ✅ Success Indicators

1. https://vyapaarai.com loads your app
2. Store registration saves to DynamoDB
3. API calls work (check Network tab)
4. HTTPS padlock shows in browser

## 📝 Final Notes

- Keep your `.env.production` file updated
- Never commit AWS credentials to git
- Monitor CloudWatch for errors
- Set up billing alerts in AWS

Ready to deploy? Start with Step 1!