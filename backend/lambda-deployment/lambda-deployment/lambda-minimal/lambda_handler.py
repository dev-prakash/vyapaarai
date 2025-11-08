"""
Lambda handler for VyaparAI FastAPI application
Complete deployment with all authentication features
"""
import os
import sys

# Add current directory to path for imports
sys.path.insert(0, '/var/task')

# Import mangum for FastAPI-Lambda adapter
from mangum import Mangum

# Set environment before importing app
os.environ['ENVIRONMENT'] = os.environ.get('ENVIRONMENT', 'production')

# Import FastAPI app
from app.main import app

# Create Lambda handler
handler = Mangum(app, lifespan="off")