"""
AWS Lambda handler for VyaparAI Marketplace
Adapts FastAPI application to work with AWS Lambda + API Gateway
"""
from mangum import Mangum
from app.main import app
import os
import logging

# Configure logging for Lambda
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Set environment for Lambda
os.environ['ENVIRONMENT'] = os.environ.get('ENVIRONMENT', 'production')

# Log Lambda initialization
logger.info("Initializing VyaparAI Lambda handler...")
logger.info(f"Environment: {os.environ.get('ENVIRONMENT')}")
logger.info(f"AWS Region: {os.environ.get('AWS_REGION')}")

# Create Lambda handler with Mangum
# lifespan="off" is recommended for Lambda to avoid startup delays
handler = Mangum(app, lifespan="off")

logger.info("VyaparAI Lambda handler initialized successfully")
