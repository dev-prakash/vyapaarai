#!/bin/bash
# Deploy Custom Products Feature to AWS Lambda
# Run from: /Users/devprakash/MyProjects/VyaparAI/vyaparai

set -e  # Exit on error

echo "🚀 Deploying Custom Products Feature"
echo "====================================="

cd /Users/devprakash/MyProjects/VyaparAI/vyaparai/backend

# Clean up any previous deployment artifacts
echo "📦 Cleaning up..."
rm -rf lambda-deploy
rm -f update.zip

# Create deployment directory
echo "📁 Creating deployment package..."
mkdir -p lambda-deploy

# Copy the entire app directory (this ensures all updated files are included)
cp -r app lambda-deploy/

# Create Lambda handler
cat > lambda-deploy/lambda_handler.py << 'EOF'
import os
import sys
sys.path.insert(0, '/var/task')

from mangum import Mangum
from app.main import app

os.environ['ENVIRONMENT'] = os.environ.get('ENVIRONMENT', 'production')
handler = Mangum(app, lifespan="off")
EOF

# Create the zip file
echo "🗜️  Creating zip file..."
cd lambda-deploy
zip -r ../update.zip . -q
cd ..

# Get zip size
ZIP_SIZE=$(du -h update.zip | cut -f1)
echo "📦 Package size: $ZIP_SIZE"

# Deploy to Lambda
echo "☁️  Uploading to AWS Lambda..."
aws lambda update-function-code \
    --function-name vyaparai-api-prod \
    --zip-file fileb://update.zip \
    --region ap-south-1

# Wait for update to complete
echo "⏳ Waiting for Lambda to update..."
aws lambda wait function-updated \
    --function-name vyaparai-api-prod \
    --region ap-south-1

# Clean up
echo "🧹 Cleaning up..."
rm -rf lambda-deploy
rm -f update.zip

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Test the endpoint with:"
echo "curl -X POST 'https://jxxi8dtx1f.execute-api.ap-south-1.amazonaws.com/api/v1/inventory/products/custom?store_id=YOUR_STORE_ID' \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -H 'Authorization: Bearer YOUR_TOKEN' \\"
echo "  -d '{\"product_name\": \"Test Product\", \"selling_price\": 100}'"
