# VyapaarAI AWS Deployment Analysis

**Generated:** January 24, 2025
**Author:** DevPrakash

---

## Executive Summary

VyapaarAI uses a **hybrid deployment approach** with multiple tools available:
- **Primary Method:** Manual Lambda deployments via ZIP packages
- **Infrastructure as Code:** Terraform (partially configured)
- **Alternative:** Serverless Framework + SAM (configured but not primary)

---

## Deployment Methods

| Method | Status | Files |
|--------|--------|-------|
| **Manual Lambda ZIP** | PRIMARY | `backend/lambda_*.zip`, deploy scripts |
| **Serverless Framework** | CONFIGURED | `serverless.yml` |
| **AWS SAM** | CONFIGURED | `samconfig.toml` |
| **Terraform** | PARTIAL | `infrastructure/terraform/` |
| **AWS CDK** | NOT USED | - |

### Current Primary Method: Manual Lambda Deployment

The project primarily uses manual ZIP package deployments:

```
backend/
├── lambda_function.zip          # Main deployment package (~37 MB)
├── lambda_deploy/               # Extracted Lambda code
├── lambda_deps/                 # Python dependencies
├── lambda_handler.py            # Lambda entry point
├── LAMBDA_DEPLOYMENT_STATUS.md  # Deployment documentation
└── scripts/deploy_lambda.sh     # Deploy script
```

---

## AWS Resources Identified

### Compute

| Resource | Name/ARN | Details |
|----------|----------|---------|
| **Lambda** | `vyaparai-api-prod` | Python 3.11, x86_64, 1024 MB, 30s timeout |
| **Lambda URL** | `https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws` | Function URL enabled |

### Storage

| Resource | Name | Purpose |
|----------|------|---------|
| **S3** | `vyapaarai.com` | Frontend static hosting |
| **S3** | `www.vyapaarai.com` | Frontend static hosting (www) |
| **S3** | `vyaparai-lambda-deployments` | Lambda deployment packages |
| **S3** | `vyaparai-terraform-state` | Terraform state (referenced in config) |

### Database

| Resource | Table Name | Purpose |
|----------|-----------|---------|
| **DynamoDB** | `vyaparai-orders-prod` | Order processing |
| **DynamoDB** | `vyaparai-stores-prod` | Store master data |
| **DynamoDB** | `vyaparai-products-prod` | Product catalog |
| **DynamoDB** | `vyaparai-sessions-prod` | User sessions |
| **DynamoDB** | `vyaparai-metrics-prod` | Analytics |
| **DynamoDB** | `vyaparai-khata-transactions-prod` | Credit ledger (Khata) |
| **DynamoDB** | `vyaparai-customer-balances-prod` | Customer balance cache |
| **DynamoDB** | `vyaparai-products-catalog-prod` | Global product catalog |
| **DynamoDB** | `vyaparai-translation-cache-prod` | Translation cache |
| **RDS** | PostgreSQL | Relational data (referenced) |
| **ElastiCache** | Redis | Session/cache (referenced) |

### Networking & CDN

| Resource | Details |
|----------|---------|
| **CloudFront** | Distribution ID: `E1UY93SVXV8QOF` |
| **Route53** | Domain: `vyapaarai.com` |
| **API Gateway** | `jxxi8dtx1f` (REST API) |

---

## Environments

| Environment | Region | Status | API URL |
|-------------|--------|--------|---------|
| **Production** | ap-south-1 | ACTIVE | `https://jxxi8dtx1f.execute-api.ap-south-1.amazonaws.com` |
| **Production** | ap-south-1 | ACTIVE | `https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws` (Function URL) |
| **Development** | ap-south-1 | Local | `http://localhost:8000` |
| **Test** | ap-south-1 | Mocked | Uses moto for DynamoDB mocking |

### Environment Naming Convention

```
Table: vyaparai-{resource}-{env}
Examples:
  - vyaparai-orders-prod
  - vyaparai-orders-dev
  - vyaparai-orders-test
```

---

## Current Deployment Process

### Backend (Lambda) Deployment

```bash
# 1. Build deployment package
cd backend
zip -r lambda_function.zip app/ lambda_handler.py -x "*.pyc" -x "*__pycache__*"

# 2. Upload to S3
aws s3 cp lambda_function.zip s3://vyaparai-lambda-deployments/backend/

# 3. Update Lambda function
aws lambda update-function-code \
    --function-name vyaparai-api-prod \
    --s3-bucket vyaparai-lambda-deployments \
    --s3-key backend/lambda_function.zip \
    --region ap-south-1
```

### Frontend Deployment

```bash
# 1. Build production bundle
cd frontend-pwa
npm run build

# 2. Sync to S3
aws s3 sync dist/ s3://www.vyapaarai.com/ --delete

# 3. Invalidate CloudFront cache
aws cloudfront create-invalidation \
    --distribution-id E1UY93SVXV8QOF \
    --paths "/*"
```

---

## Existing Scripts & Configurations

### Deployment Scripts

| Script | Path | Purpose |
|--------|------|---------|
| `deploy-production.sh` | `scripts/` | Full production deployment with validation |
| `deploy-aws.sh` | `scripts/` | AWS deployment automation |
| `deploy_lambda.sh` | `backend/scripts/` | Lambda-specific deployment |
| `deploy-all.sh` | `deployment/` | Full stack deployment |
| `deploy-backend.sh` | `deployment/` | Backend-only deployment |
| `deploy-frontend.sh` | `deployment/` | Frontend-only deployment |
| `quick-update.sh` | `deployment/` | Quick code update |
| `deploy_customer_auth.sh` | `backend/` | Customer auth Lambda deployment |

### Configuration Files

| File | Purpose |
|------|---------|
| `serverless.yml` | Serverless Framework configuration |
| `samconfig.toml` | AWS SAM configuration |
| `infrastructure/terraform/main.tf` | Terraform infrastructure |
| `deployment/production-config.yml` | Production settings |
| `backend/LAMBDA_DEPLOYMENT_STATUS.md` | Deployment documentation |

---

## Infrastructure as Code Status

### Terraform (`infrastructure/terraform/`)

**Status:** Partially configured

**Files:**
- `main.tf` - VPC, ElastiCache, DynamoDB configuration
- `monitoring.tf` - CloudWatch monitoring

**Resources Defined:**
- VPC with public/private subnets
- NAT Gateway
- ElastiCache Redis cluster
- DynamoDB tables (referenced)
- S3 buckets (referenced)

**State Backend:**
```hcl
backend "s3" {
  bucket = "vyaparai-terraform-state"
  key    = "infrastructure/terraform.tfstate"
  region = "ap-south-1"
}
```

### Serverless Framework (`serverless.yml`)

**Status:** Configured but not primary deployment method

**Services Defined:**
- Lambda function with Python 3.11
- DynamoDB tables (Orders, Sessions, RateLimits, Stores, Products, Metrics)
- S3 bucket for static assets
- IAM roles with fine-grained permissions

### AWS SAM (`samconfig.toml`)

**Status:** Configured as alternative deployment method

**Environments:**
- `default` (dev)
- `dev` (development)

---

## Recommendations for /deploy Command

Based on this analysis, the `/deploy` command should support multiple deployment targets:

### Proposed /deploy Command Structure

```bash
# Deploy everything
/deploy all

# Deploy backend only
/deploy backend [--env prod|dev]

# Deploy frontend only
/deploy frontend [--env prod|dev]

# Deploy Lambda function code only (quick update)
/deploy lambda

# Deploy infrastructure (Terraform)
/deploy infra [--plan|--apply]
```

### Implementation Approach

1. **Use existing scripts** as foundation:
   - `scripts/deploy-production.sh` for full deployment
   - `deployment/quick-update.sh` for quick Lambda updates
   - `deployment/deploy-frontend.sh` for frontend

2. **Add pre-deployment checks:**
   - Run tests before deployment
   - Validate AWS credentials
   - Check for uncommitted changes

3. **Add post-deployment verification:**
   - Health check endpoints
   - CloudWatch log monitoring
   - Automatic rollback on failure

4. **Environment handling:**
   - Default to production with confirmation
   - Support `--env dev` for development
   - Never deploy to prod without tests passing

### Suggested /deploy Workflow

```
Phase 1: Pre-flight checks
├── Verify AWS credentials
├── Check git status (warn if uncommitted changes)
├── Run regression tests
└── Ask for confirmation

Phase 2: Deployment
├── Backend: Build and deploy Lambda
├── Frontend: Build and sync to S3
└── Infrastructure: Terraform apply (if changes)

Phase 3: Post-deployment
├── Health check API endpoints
├── Invalidate CloudFront cache
├── Verify deployment success
└── Generate deployment report
```

---

## Security Considerations

1. **Credentials:** Never commit AWS credentials; use IAM roles
2. **Secrets:** Use AWS Secrets Manager for sensitive data
3. **S3:** Frontend bucket has public read; ensure no sensitive data
4. **Lambda:** Uses IAM role with least-privilege permissions
5. **DynamoDB:** Encryption at rest enabled (AWS default)

---

## Monitoring & Observability

| Service | Configuration |
|---------|--------------|
| **CloudWatch Logs** | `/aws/lambda/vyaparai-production` |
| **CloudWatch Metrics** | Custom namespace: `VyaparAI` |
| **Powertools** | Enabled for Lambda (structured logging) |

---

## Action Items

1. [ ] Consolidate deployment scripts into unified `/deploy` command
2. [ ] Complete Terraform configuration for all resources
3. [ ] Add staging environment between dev and prod
4. [ ] Implement automated rollback mechanism
5. [ ] Add deployment notifications (Slack/email)
6. [ ] Create CI/CD pipeline (GitHub Actions recommended)

---

## Quick Reference

### Production URLs

| Service | URL |
|---------|-----|
| Frontend | https://www.vyapaarai.com |
| API (Gateway) | https://jxxi8dtx1f.execute-api.ap-south-1.amazonaws.com |
| API (Lambda URL) | https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws |

### AWS Region

All resources are deployed in **ap-south-1 (Mumbai)**.

### Key Commands

```bash
# Check Lambda status
aws lambda get-function --function-name vyaparai-api-prod --region ap-south-1

# View recent logs
aws logs tail /aws/lambda/vyaparai-api-prod --follow

# Check DynamoDB tables
aws dynamodb list-tables --region ap-south-1 | grep vyaparai
```
