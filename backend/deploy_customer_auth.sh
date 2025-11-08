#!/bin/bash
set -e

echo "🚀 Deploying Customer Authentication Lambda..."

# Configuration
LAMBDA_NAME="vyaparai-api-prod"
REGION="ap-south-1"
DEPLOYMENT_DIR="lambda_customer_auth_deployment"

# Clean previous deployment
echo "📦 Cleaning previous deployment..."
rm -rf $DEPLOYMENT_DIR
mkdir -p $DEPLOYMENT_DIR

# Copy application code
echo "📁 Copying application code..."
cp -r app $DEPLOYMENT_DIR/
cp customer_auth_requirements.txt $DEPLOYMENT_DIR/requirements.txt

# Install dependencies
echo "📥 Installing dependencies..."
cd $DEPLOYMENT_DIR
pip install -r requirements.txt -t . --platform manylinux2014_x86_64 --only-binary=:all: --python-version 3.12

# Create lambda handler
echo "⚙️  Creating Lambda handler..."
cat > lambda_handler.py << 'EOF'
from mangum import Mangum
from app.main import app

# Create Lambda handler
handler = Mangum(app, lifespan="off")
EOF

# Create deployment package
echo "📦 Creating deployment package..."
zip -r ../lambda-customer-auth-deployment.zip . -x "*.pyc" -x "*__pycache__*" -x "*.git*"

cd ..

# Get current Lambda configuration
echo "🔍 Checking Lambda function..."
if aws lambda get-function --function-name $LAMBDA_NAME --region $REGION > /dev/null 2>&1; then
    echo "✅ Lambda function exists, updating code..."

    # Update Lambda code
    aws lambda update-function-code \
        --function-name $LAMBDA_NAME \
        --zip-file fileb://lambda-customer-auth-deployment.zip \
        --region $REGION \
        --no-cli-pager

    echo "⏳ Waiting for update to complete..."
    aws lambda wait function-updated \
        --function-name $LAMBDA_NAME \
        --region $REGION

    echo "✅ Lambda code updated successfully!"
else
    echo "❌ Lambda function not found. Please create it first or update LAMBDA_NAME."
    exit 1
fi

# Clean up
echo "🧹 Cleaning up..."
rm -rf $DEPLOYMENT_DIR

echo "✅ Deployment complete!"
echo "📊 Deployment package size:"
ls -lh lambda-customer-auth-deployment.zip
echo ""
echo "🔗 New endpoints available:"
echo "  POST /api/v1/customer/auth/google"
echo "  POST /api/v1/customer/auth/facebook"
echo "  POST /api/v1/customer/auth/register"
echo "  POST /api/v1/customer/auth/login"
echo "  POST /api/v1/customer/auth/send-otp"
echo "  POST /api/v1/customer/auth/verify-otp"
