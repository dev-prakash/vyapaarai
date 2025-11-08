#!/usr/bin/env python3
"""
VyaparAI FastAPI Application Startup Script
Handles environment setup and application startup
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def check_dependencies():
    """Check if required dependencies are installed"""
    required_packages = [
        "fastapi",
        "uvicorn",
        "pydantic",
        "redis",
        "httpx"
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        logger.error(f"Missing required packages: {', '.join(missing_packages)}")
        logger.info("Install missing packages with: pip install -r requirements.txt")
        return False
    
    return True

def check_environment():
    """Check environment variables and configuration"""
    logger.info("Checking environment configuration...")
    
    # Check for .env file
    env_file = Path(".env")
    if not env_file.exists():
        logger.warning(".env file not found. Creating from .env.example...")
        example_env = Path(".env.example")
        if example_env.exists():
            with open(example_env, 'r') as f:
                env_content = f.read()
            with open(env_file, 'w') as f:
                f.write(env_content)
            logger.info("Created .env file from .env.example")
        else:
            logger.warning("No .env.example file found. Please create .env file manually.")
    
    # Check environment variables
    env_vars = {
        "ENVIRONMENT": os.getenv("ENVIRONMENT", "development"),
        "REDIS_URL": os.getenv("REDIS_URL", "redis://localhost:6379"),
        "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY"),
        "GOOGLE_TRANSLATE_API_KEY": os.getenv("GOOGLE_TRANSLATE_API_KEY")
    }
    
    logger.info("Environment variables:")
    for key, value in env_vars.items():
        if key.endswith("_KEY") and value:
            logger.info(f"  {key}: {'*' * len(value)}")
        else:
            logger.info(f"  {key}: {value}")
    
    return True

def check_redis():
    """Check Redis connection"""
    try:
        import redis
        r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        r.ping()
        logger.info("Redis connection successful")
        return True
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}")
        logger.info("Redis is optional for development. Rate limiting will use in-memory storage.")
        return False

def start_application():
    """Start the FastAPI application"""
    logger.info("Starting VyaparAI FastAPI application...")
    
    # Get configuration
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("ENVIRONMENT", "development") == "development"
    log_level = "debug" if reload else "info"
    
    # Build uvicorn command
    cmd = [
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--host", host,
        "--port", str(port),
        "--log-level", log_level
    ]
    
    if reload:
        cmd.append("--reload")
        logger.info("Development mode: Auto-reload enabled")
    
    logger.info(f"Starting server on {host}:{port}")
    logger.info(f"Command: {' '.join(cmd)}")
    
    try:
        # Start the application
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except subprocess.CalledProcessError as e:
        logger.error(f"Application failed to start: {e}")
        return False
    
    return True

def main():
    """Main startup function"""
    print("=" * 60)
    print("VyaparAI FastAPI Application Startup")
    print("=" * 60)
    
    # Check dependencies
    logger.info("Checking dependencies...")
    if not check_dependencies():
        sys.exit(1)
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Check Redis (optional)
    check_redis()
    
    # Start application
    if not start_application():
        sys.exit(1)

if __name__ == "__main__":
    main()
