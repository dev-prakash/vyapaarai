#!/bin/bash
set -e

echo "🐳 Building Lambda package using Docker..."

# Clean previous builds
rm -rf lambda_docker_build/
rm -f lambda_function.zip

# Create build directory
mkdir -p lambda_docker_build

# Copy application code
cp -r app lambda_docker_build/
cp lambda_handler.py lambda_docker_build/
cp requirements.txt lambda_docker_build/

# Ensure all __init__.py files exist
find lambda_docker_build/app -type d -exec touch {}/__init__.py \; 2>/dev/null || true

# Use AWS Lambda Python 3.11 image to install dependencies
echo "📦 Installing dependencies in Lambda environment..."
docker run --rm \
  --platform linux/amd64 \
  --entrypoint /bin/bash \
  -v "$PWD/lambda_docker_build":/var/task \
  -w /var/task \
  public.ecr.aws/lambda/python:3.11 \
  -c "pip install --upgrade pip && pip install -r requirements.txt -t . --prefer-binary --no-cache-dir"

# Create deployment package
cd lambda_docker_build
echo "📦 Creating ZIP package..."
zip -r ../lambda_function.zip . -x "*.pyc" "*.pyo" "*.git*" "__pycache__/*" "*.DS_Store"

cd ..
echo "✅ Package created: lambda_function.zip"
echo "📊 Package size: $(du -h lambda_function.zip | cut -f1)"

# Verify package contents
echo "📋 Verifying package contents..."
unzip -l lambda_function.zip | grep -E "(lambda_handler|app/__init__|anyio|pydantic)" | head -20

echo "✅ Docker build complete!"
