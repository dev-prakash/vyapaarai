#!/bin/bash
set -e

echo "🔧 Building Lambda Layer for image dependencies..."

# Clean previous builds
rm -rf lambda_layer_build/
rm -f image_layer.zip

# Create layer directory structure
mkdir -p lambda_layer_build/python/lib/python3.11/site-packages

# Use AWS Lambda Python 3.11 image to install dependencies
echo "📦 Installing dependencies in Lambda environment..."
docker run --rm \
  --platform linux/amd64 \
  --entrypoint /bin/bash \
  -v "$PWD/lambda_layer_build/python/lib/python3.11/site-packages":/var/task \
  -v "$PWD/layer_requirements.txt":/requirements.txt \
  -w /var/task \
  public.ecr.aws/lambda/python:3.11 \
  -c "pip install --upgrade pip && pip install -r /requirements.txt -t . --prefer-binary --no-cache-dir"

# Create layer ZIP
cd lambda_layer_build
echo "📦 Creating layer ZIP package..."
zip -r ../image_layer.zip python -x "*.pyc" "*.pyo" "*.git*" "__pycache__/*" "*.DS_Store"

cd ..
echo "✅ Layer created: image_layer.zip"
echo "📊 Layer size: $(du -h image_layer.zip | cut -f1)"
