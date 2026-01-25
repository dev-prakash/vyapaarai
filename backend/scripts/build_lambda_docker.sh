#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}VyaparAI Lambda Package Builder (Docker)${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
PACKAGE_NAME="lambda_package_linux.zip"
LAMBDA_FUNCTION_NAME="vyaparai-api-prod"
AWS_REGION="ap-south-1"

cd "$BACKEND_DIR"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running. Please start Docker and try again.${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 1: Cleaning previous builds...${NC}"
rm -rf lambda_docker_build/ 2>/dev/null || true
rm -f "$PACKAGE_NAME" 2>/dev/null || true
mkdir -p lambda_docker_build

echo -e "${YELLOW}Step 2: Copying application code...${NC}"
# Copy app code
cp -r app lambda_docker_build/
cp lambda_handler.py lambda_docker_build/

# Create minimal requirements for Lambda (exclude dev dependencies)
cat > lambda_docker_build/requirements_lambda.txt << 'EOF'
# Core FastAPI
fastapi==0.121.0
mangum==0.19.0
starlette==0.49.3
pydantic==2.12.4
pydantic-settings==2.11.0
pydantic_core==2.41.5

# Auth & Security
PyJWT==2.10.1
python-jose==3.5.0
bcrypt==5.0.0
passlib==1.7.4
cryptography==46.0.3

# Google Auth (for OAuth)
google-auth==2.41.1
google-auth-oauthlib==1.2.3

# HTTP & Async
httpx>=0.25.0
anyio==4.11.0
sniffio==1.3.1
h11==0.16.0

# Utils
python-dateutil==2.9.0.post0
python-dotenv==1.2.1
python-multipart==0.0.20
python-ulid==3.1.0
email-validator==2.3.0
rapidfuzz==3.10.0

# Rate limiting
slowapi==0.1.9
limits==5.6.0

# Requests (for external API calls)
requests==2.32.5
urllib3==2.5.0
certifi==2025.10.5
charset-normalizer==3.4.4
idna==3.11

# Redis (optional, for caching)
redis==7.0.1

# Razorpay (payments)
razorpay==2.0.0

# Type hints
typing_extensions==4.15.0
annotated-types==0.7.0

# Other required
cachetools==6.2.1
packaging==25.0
MarkupSafe==3.0.3
wrapt==2.0.1
six==1.17.0
EOF

echo -e "${YELLOW}Step 3: Building Docker image for Lambda runtime...${NC}"

# Create Dockerfile for building
cat > lambda_docker_build/Dockerfile << 'EOF'
FROM public.ecr.aws/lambda/python:3.11

# Install build dependencies
RUN yum install -y gcc python3-devel

# Copy requirements
COPY requirements_lambda.txt /tmp/requirements.txt

# Install dependencies to /var/task (Lambda's working directory)
RUN pip install --no-cache-dir -r /tmp/requirements.txt -t /var/task/

# Copy application code
COPY app/ /var/task/app/
COPY lambda_handler.py /var/task/

# Clean up unnecessary files
RUN find /var/task -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
RUN find /var/task -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
RUN find /var/task -type f -name "*.pyc" -delete 2>/dev/null || true
RUN find /var/task -type f -name "*.pyo" -delete 2>/dev/null || true

# Remove boto3/botocore (Lambda provides these)
RUN rm -rf /var/task/boto3* /var/task/botocore* /var/task/s3transfer* 2>/dev/null || true

# Remove test directories
RUN find /var/task -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true

WORKDIR /var/task
EOF

# Build Docker image
docker build -t vyaparai-lambda-builder lambda_docker_build/

echo -e "${YELLOW}Step 4: Extracting built package from Docker...${NC}"

# Create a container and copy the built files out
CONTAINER_ID=$(docker create vyaparai-lambda-builder)
docker cp "$CONTAINER_ID:/var/task/." lambda_docker_build/package/
docker rm "$CONTAINER_ID"

echo -e "${YELLOW}Step 5: Creating deployment ZIP...${NC}"

cd lambda_docker_build/package

# Create the ZIP file
zip -r "../../$PACKAGE_NAME" . -q -x "*.git*" "*.DS_Store" "*__pycache__*"

cd "$BACKEND_DIR"

# Get package info
ZIPPED_SIZE=$(du -h "$PACKAGE_NAME" | cut -f1)
ZIPPED_SIZE_BYTES=$(stat -f%z "$PACKAGE_NAME" 2>/dev/null || stat -c%s "$PACKAGE_NAME" 2>/dev/null)
ZIPPED_SIZE_MB=$((ZIPPED_SIZE_BYTES / 1024 / 1024))

UNZIPPED_SIZE=$(unzip -l "$PACKAGE_NAME" | tail -1 | awk '{print $1}')
UNZIPPED_SIZE_MB=$((UNZIPPED_SIZE / 1024 / 1024))

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Build Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "Package: ${YELLOW}$PACKAGE_NAME${NC}"
echo -e "Zipped size: ${YELLOW}$ZIPPED_SIZE (${ZIPPED_SIZE_MB}MB)${NC}"
echo -e "Unzipped size: ${YELLOW}${UNZIPPED_SIZE_MB}MB${NC}"

# Check Lambda limits
if [ $ZIPPED_SIZE_MB -gt 50 ]; then
    echo -e "${YELLOW}Warning: Package > 50MB - will need S3 upload${NC}"
fi

if [ $UNZIPPED_SIZE_MB -gt 250 ]; then
    echo -e "${RED}Error: Package > 250MB - too large for Lambda!${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}Verifying pydantic_core binary...${NC}"
unzip -l "$PACKAGE_NAME" | grep pydantic_core | head -5

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Next Steps:${NC}"
echo -e "${GREEN}========================================${NC}"

if [ $ZIPPED_SIZE_MB -gt 50 ]; then
    echo "Package is > 50MB, uploading via S3..."
    echo ""
    echo "Run these commands:"
    echo -e "${YELLOW}  aws s3 cp $PACKAGE_NAME s3://vyaparai-deployments/$PACKAGE_NAME${NC}"
    echo -e "${YELLOW}  aws lambda update-function-code \\${NC}"
    echo -e "${YELLOW}    --function-name $LAMBDA_FUNCTION_NAME \\${NC}"
    echo -e "${YELLOW}    --s3-bucket vyaparai-deployments \\${NC}"
    echo -e "${YELLOW}    --s3-key $PACKAGE_NAME \\${NC}"
    echo -e "${YELLOW}    --region $AWS_REGION${NC}"
else
    echo "Package is < 50MB, can upload directly:"
    echo ""
    echo -e "${YELLOW}  aws lambda update-function-code \\${NC}"
    echo -e "${YELLOW}    --function-name $LAMBDA_FUNCTION_NAME \\${NC}"
    echo -e "${YELLOW}    --zip-file fileb://$PACKAGE_NAME \\${NC}"
    echo -e "${YELLOW}    --region $AWS_REGION${NC}"
fi

echo ""
echo "Or run with --deploy flag to deploy automatically:"
echo -e "${YELLOW}  $0 --deploy${NC}"
echo ""

# Auto-deploy if --deploy flag is passed
if [ "$1" == "--deploy" ]; then
    echo -e "${YELLOW}Deploying to Lambda...${NC}"

    if [ $ZIPPED_SIZE_MB -gt 50 ]; then
        echo "Uploading to S3 first..."
        aws s3 cp "$PACKAGE_NAME" "s3://vyaparai-deployments/$PACKAGE_NAME" --region "$AWS_REGION"

        aws lambda update-function-code \
            --function-name "$LAMBDA_FUNCTION_NAME" \
            --s3-bucket vyaparai-deployments \
            --s3-key "$PACKAGE_NAME" \
            --region "$AWS_REGION"
    else
        aws lambda update-function-code \
            --function-name "$LAMBDA_FUNCTION_NAME" \
            --zip-file "fileb://$PACKAGE_NAME" \
            --region "$AWS_REGION"
    fi

    echo -e "${YELLOW}Waiting for function to be updated...${NC}"
    aws lambda wait function-updated \
        --function-name "$LAMBDA_FUNCTION_NAME" \
        --region "$AWS_REGION"

    echo -e "${GREEN}Deployment complete!${NC}"
    echo ""
    echo "Testing health endpoint..."
    sleep 3
    curl -s "https://jxxi8dtx1f.execute-api.ap-south-1.amazonaws.com/health" | head -100
    echo ""
fi
