# VyaparAI AWS Deployment Guide

This guide covers the complete deployment of VyaparAI to AWS infrastructure, including backend, frontend, and all supporting services.

## 🚀 Quick Start

### Prerequisites

1. **AWS CLI** installed and configured
   ```bash
   # Install AWS CLI
   curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
   unzip awscliv2.zip
   sudo ./aws/install
   
   # Configure AWS credentials
   aws configure
   ```

2. **Node.js 18+** installed
   ```bash
   # Install Node.js
   curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
   sudo apt-get install -y nodejs
   ```

3. **Python 3.11+** installed
   ```bash
   # Install Python
   sudo apt-get update
   sudo apt-get install python3.11 python3.11-pip
   ```

4. **PostgreSQL client** (optional, for database setup)
   ```bash
   # Install PostgreSQL client
   sudo apt-get install postgresql-client
   ```

### One-Command Deployment

Run the complete deployment:
```bash
./deployment/deploy-all.sh
```

This will:
- ✅ Create AWS infrastructure (S3, DynamoDB, RDS, Lambda, CloudFront)
- ✅ Deploy backend to AWS Lambda
- ✅ Deploy frontend to S3/CloudFront
- ✅ Configure everything automatically
- ✅ Test the deployment

## 📁 Deployment Scripts

### Core Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `setup-aws.sh` | Create AWS infrastructure | `./deployment/setup-aws.sh` |
| `deploy-backend.sh` | Deploy backend to Lambda | `./deployment/deploy-backend.sh` |
| `deploy-frontend.sh` | Deploy frontend to S3/CloudFront | `./deployment/deploy-frontend.sh` |
| `deploy-all.sh` | Complete deployment | `./deployment/deploy-all.sh` |
| `test-deployment.sh` | Test all components | `./deployment/test-deployment.sh` |

### Utility Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `quick-update.sh` | Rapid code updates | `./deployment/quick-update.sh [backend\|frontend]` |

## 🏗️ AWS Infrastructure

### Created Resources

- **S3 Buckets**
  - `vyaparai-frontend-{account-id}` - Frontend hosting
  - `vyaparai-deployment-{account-id}` - Deployment artifacts

- **DynamoDB Tables**
  - `vyaparai-orders-prod` - Order data with GSI
  - `vyaparai-sessions-prod` - User sessions

- **RDS PostgreSQL**
  - `vyaparai-postgres-prod` - Main database
  - Instance: db.t3.micro
  - Storage: 20GB GP3

- **Lambda Function**
  - `vyaparai-api-prod` - Backend API
  - Runtime: Python 3.11
  - Memory: 512MB
  - Timeout: 30s

- **CloudFront Distribution**
  - CDN for frontend
  - HTTPS enabled
  - SPA routing support

- **IAM Roles & Policies**
  - `vyaparai-lambda-role` - Lambda execution role
  - Full access to DynamoDB, RDS, S3

### Estimated Costs (ap-south-1)

| Service | Monthly Cost |
|---------|-------------|
| Lambda | ~$5-10 |
| RDS | ~$15-20 |
| DynamoDB | ~$5-10 |
| CloudFront | ~$5-10 |
| S3 | ~$1-2 |
| **Total** | **~$30-50** |

## 🔧 Manual Deployment Steps

### Step 1: Setup AWS Infrastructure

```bash
# Create all AWS resources
./deployment/setup-aws.sh
```

### Step 2: Initialize Database

```bash
# Get RDS endpoint
RDS_ENDPOINT=$(aws rds describe-db-instances \
    --db-instance-identifier vyaparai-postgres-prod \
    --query 'DBInstances[0].Endpoint.Address' \
    --output text)

# Create database
PGPASSWORD=VyaparAI2024Secure! psql -h $RDS_ENDPOINT -U vyaparai_admin -d postgres -c "CREATE DATABASE vyaparai;"
```

### Step 3: Deploy Backend

```bash
# Deploy to Lambda
./deployment/deploy-backend.sh
```

### Step 4: Deploy Frontend

```bash
# Deploy to S3/CloudFront
./deployment/deploy-frontend.sh
```

### Step 5: Test Deployment

```bash
# Run comprehensive tests
./deployment/test-deployment.sh
```

## 🔄 Updates and Maintenance

### Quick Updates

For code changes only (no dependency updates):

```bash
# Update backend code
./deployment/quick-update.sh backend

# Update frontend code
./deployment/quick-update.sh frontend
```

### Full Updates

For dependency updates or major changes:

```bash
# Update backend with dependencies
./deployment/deploy-backend.sh

# Update frontend with dependencies
./deployment/deploy-frontend.sh
```

### Monitoring

```bash
# Monitor Lambda logs
aws logs tail /aws/lambda/vyaparai-api-prod --follow

# Check Lambda function status
aws lambda get-function --function-name vyaparai-api-prod

# Check RDS status
aws rds describe-db-instances --db-instance-identifier vyaparai-postgres-prod

# Check CloudFront distribution
aws cloudfront list-distributions
```

## 🚨 Troubleshooting

### Common Issues

#### 1. AWS Credentials Not Configured
```bash
# Configure AWS credentials
aws configure
# Enter your Access Key ID, Secret Access Key, Region (ap-south-1), and output format (json)
```

#### 2. RDS Not Available
```bash
# Wait for RDS to be available
aws rds wait db-instance-available --db-instance-identifier vyaparai-postgres-prod

# Check RDS status
aws rds describe-db-instances --db-instance-identifier vyaparai-postgres-prod
```

#### 3. Lambda Deployment Failed
```bash
# Check Lambda logs
aws logs tail /aws/lambda/vyaparai-api-prod --follow

# Check function configuration
aws lambda get-function --function-name vyaparai-api-prod
```

#### 4. Frontend Not Accessible
```bash
# Check S3 bucket
aws s3 ls s3://vyaparai-frontend-{account-id}/

# Check CloudFront distribution
aws cloudfront list-distributions

# Invalidate CloudFront cache
aws cloudfront create-invalidation --distribution-id {distribution-id} --paths "/*"
```

#### 5. Database Connection Issues
```bash
# Test database connection
PGPASSWORD=VyaparAI2024Secure! psql -h {rds-endpoint} -U vyaparai_admin -d vyaparai -c "SELECT 1;"

# Check security groups
aws rds describe-db-instances --db-instance-identifier vyaparai-postgres-prod --query 'DBInstances[0].VpcSecurityGroups'
```

### Environment Variables

Key environment variables for Lambda:

```bash
ENVIRONMENT=production
DATABASE_URL=postgresql://vyaparai_admin:VyaparAI2024Secure!@{rds-endpoint}/vyaparai
DYNAMODB_ORDERS_TABLE=vyaparai-orders-prod
DYNAMODB_SESSIONS_TABLE=vyaparai-sessions-prod
JWT_SECRET=vyaparai-jwt-secret-2024-secure
GOOGLE_API_KEY=your-google-api-key
REDIS_URL=redis://{redis-endpoint}:6379
```

## 🔐 Security Considerations

### Production Security Checklist

- [ ] Change default passwords
- [ ] Enable RDS encryption
- [ ] Configure VPC for RDS
- [ ] Set up CloudWatch alarms
- [ ] Enable AWS CloudTrail
- [ ] Configure backup retention
- [ ] Set up monitoring and alerting
- [ ] Review IAM permissions
- [ ] Enable AWS Config
- [ ] Set up AWS Shield (if needed)

### Custom Domain Setup

1. **Register domain** in Route 53 or external provider
2. **Create SSL certificate** in AWS Certificate Manager
3. **Update CloudFront distribution** with custom domain
4. **Configure DNS** to point to CloudFront
5. **Update environment variables** with new domain

## 📊 Monitoring and Logging

### CloudWatch Logs

```bash
# View Lambda logs
aws logs tail /aws/lambda/vyaparai-api-prod --follow

# View specific log stream
aws logs get-log-events --log-group-name /aws/lambda/vyaparai-api-prod --log-stream-name {stream-name}
```

### CloudWatch Metrics

- Lambda: Invocations, duration, errors
- RDS: CPU, memory, connections
- DynamoDB: Read/write capacity, throttling
- CloudFront: Requests, cache hit ratio

### Setting Up Alarms

```bash
# Create Lambda error alarm
aws cloudwatch put-metric-alarm \
    --alarm-name "VyaparAI-Lambda-Errors" \
    --alarm-description "Lambda function errors" \
    --metric-name Errors \
    --namespace AWS/Lambda \
    --statistic Sum \
    --period 300 \
    --threshold 1 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1
```

## 🔄 CI/CD with GitHub Actions

### Setup

1. **Add secrets** to GitHub repository:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `GOOGLE_API_KEY`

2. **Push to main branch** to trigger deployment

### Manual Deployment

```bash
# Trigger manual deployment
gh workflow run deploy.yml -f environment=production
```

## 📞 Support

For deployment issues:

1. Check the troubleshooting section above
2. Review CloudWatch logs
3. Verify AWS service status
4. Check environment variables
5. Test individual components

## 📝 Notes

- All scripts are idempotent (safe to run multiple times)
- Resources are created with unique names using AWS account ID
- Default region is `ap-south-1` (Mumbai)
- Database password is hardcoded for simplicity (change in production)
- JWT secret is hardcoded (change in production)



