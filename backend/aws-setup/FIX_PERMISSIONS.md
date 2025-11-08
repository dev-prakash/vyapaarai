# Fix AWS IAM Permissions for VyaparAI Deployment

## The Problem
Your `vyaparai-deploy` IAM user lacks EC2 permissions needed to create security groups for RDS setup.

## Quick Fix (2 Methods)

### Method 1: Using AWS Console (Recommended)
1. Login to AWS Console as root/admin user
2. Go to IAM → Users → vyaparai-deploy
3. Click "Add permissions" → "Attach policies directly"
4. Search and attach these AWS managed policies:
   - `AmazonRDSFullAccess`
   - `AmazonDynamoDBFullAccess`
   - `AmazonEC2FullAccess` (or create custom policy below for minimal permissions)
   - `AWSLambda_FullAccess`

### Method 2: Using AWS CLI (If you have admin credentials)
```bash
# Create custom policy with minimal required permissions
aws iam create-policy \
  --policy-name VyaparAIDeploymentPolicy \
  --policy-document file://iam-policy-vyaparai-deploy.json \
  --description "Permissions for VyaparAI database deployment"

# Get the policy ARN from output, then attach to user
aws iam attach-user-policy \
  --user-name vyaparai-deploy \
  --policy-arn arn:aws:iam::491065739648:policy/VyaparAIDeploymentPolicy
```

## Alternative: Use Default VPC Security Group (No EC2 Permissions Needed)

If you cannot get EC2 permissions, run this modified setup script:

```bash
cd /Users/devprakash/MyProjects/VyaparAI/vyaparai/backend/aws-setup
./setup-aws-databases-no-sg.sh
```

This script uses the default VPC security group instead of creating a new one.

## After Fixing Permissions

Run the original setup script:
```bash
cd /Users/devprakash/MyProjects/VyaparAI/vyaparai/backend/aws-setup
./setup-aws-databases.sh
```

## Verify Permissions
```bash
# Check if you can now create security groups
aws ec2 describe-security-groups --region ap-south-1

# If this works, you're ready to deploy!
```

## Notes
- The custom policy in `iam-policy-vyaparai-deploy.json` has minimal required permissions
- For production, consider using more restrictive Resource ARNs instead of "*"
- The deployment will cost approximately $15-30/month for RDS after free tier