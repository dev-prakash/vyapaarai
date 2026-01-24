#!/bin/bash
set -e

echo "🚀 Building Lambda deployment package for VyaparAI..."
echo "=================================================="

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf lambda_deploy/
rm -f lambda_function.zip

# Create deployment directory
echo "📁 Creating deployment directory..."
mkdir -p lambda_deploy

# Copy application code
echo "📦 Copying application code..."
mkdir -p lambda_deploy/app
cp -r app/* lambda_deploy/app/
cp lambda_handler.py lambda_deploy/
cp requirements.txt lambda_deploy/

# Install dependencies for Linux ARM64 (Lambda runtime)
echo "📥 Installing dependencies for Linux ARM64..."
cd lambda_deploy

# Install dependencies with ARM64 Linux platform (Lambda uses arm64)
# Use Docker to build for the correct platform
if command -v docker &> /dev/null; then
    echo "🐳 Using Docker to build ARM64 dependencies..."
    cd ..
    docker run --rm -v "$(pwd)/lambda_deploy:/var/task" \
        --platform linux/arm64 \
        public.ecr.aws/sam/build-python3.11:latest \
        pip install -r /var/task/requirements.txt -t /var/task --quiet
    cd lambda_deploy
else
    echo "⚠️  Docker not available, using pip with platform flags..."
    # First try to install platform-specific binaries for ARM64
    pip install -r requirements.txt -t . --upgrade --quiet \
      --platform manylinux2014_aarch64 \
      --implementation cp \
      --python-version 3.11 \
      --only-binary=:all: \
      --no-deps 2>/dev/null || true

    # Then install again normally to get all dependencies
    pip install -r requirements.txt -t . --quiet
fi

# Remove unnecessary files to reduce package size
echo "🗑️  Removing unnecessary files..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
# Don't remove .dist-info - some packages need metadata at runtime (e.g. email-validator)
# find . -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete
find . -type f -name "*.pyo" -delete
# Don't remove .so files - they contain compiled C extensions needed by packages like pydantic_core

# Remove boto3 and botocore (Lambda provides these)
echo "🔧 Removing AWS SDK (Lambda provides these)..."
rm -rf boto3/ botocore/ boto3-*.dist-info/ botocore-*.dist-info/ 2>/dev/null || true

# Fix annotated-doc metadata issue by reinstalling it
echo "🔧 Fixing annotated-doc metadata..."
rm -rf annotated_doc/ annotated-doc/ annotated_doc-*.dist-info/ 2>/dev/null || true
pip install annotated-doc==0.0.3 --no-deps -t . --quiet

# Remove test files (but preserve framework internals like anyio/abc/_testing.py)
echo "🧪 Removing test files..."
find . -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
# Only remove test files from app directory, not from dependencies
find ./app -type f -name "*test*.py" -delete 2>/dev/null || true

# Create ZIP file
echo "📦 Creating ZIP archive..."
zip -r ../lambda_function.zip . -q -x "*.git*" "*.DS_Store" "*venv*"

cd ..

echo ""
echo "✅ Deployment package created successfully!"
echo "=================================================="
echo "📦 Package: lambda_function.zip"
echo "📏 Size: $(du -h lambda_function.zip | cut -f1)"

# Check if package is under Lambda limit (250MB unzipped, 50MB zipped)
ZIPPED_SIZE_BYTES=$(stat -f%z lambda_function.zip 2>/dev/null || stat -c%s lambda_function.zip 2>/dev/null)
ZIPPED_SIZE_MB=$((ZIPPED_SIZE_BYTES / 1024 / 1024))

echo "📊 Zipped size: ${ZIPPED_SIZE_MB}MB"

if [ $ZIPPED_SIZE_MB -gt 50 ]; then
    echo "⚠️  WARNING: Package is larger than 50MB (Lambda direct upload limit)"
    echo "   You'll need to upload via S3"
else
    echo "✅ Package size is within Lambda limits"
fi

UNZIPPED_SIZE=$(unzip -l lambda_function.zip | tail -1 | awk '{print $1}')
UNZIPPED_SIZE_MB=$((UNZIPPED_SIZE / 1024 / 1024))

echo "📊 Unzipped size: ${UNZIPPED_SIZE_MB}MB"

if [ $UNZIPPED_SIZE_MB -gt 250 ]; then
    echo "❌ ERROR: Package is too large for Lambda (>250MB unzipped)"
    exit 1
fi

echo ""
echo "🎯 Ready to deploy to AWS Lambda!"
echo "=================================================="
echo "Next steps:"
echo "  1. Deploy: aws lambda update-function-code --function-name vyapaarai-marketplace-prod --zip-file fileb://lambda_function.zip"
echo "  2. Or upload to S3 if size > 50MB"
echo ""
