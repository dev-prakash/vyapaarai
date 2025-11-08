"""
Main FastAPI application for VyaparAI Lambda deployment
Simplified version without complex dependencies
"""

import os
from fastapi import FastAPI

# Import routers
from app.api.v1.auth import router as auth_router
from app.api.v1.stores import router as stores_router
from app.api.v1.notifications import router as notifications_router

# Create FastAPI app
app = FastAPI(
    title="VyaparAI API",
    description="Store management API for Lambda deployment",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS handled by AWS Lambda URL configuration

# Include API routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(stores_router)
app.include_router(notifications_router)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "VyaparAI API - Lambda Deployment",
        "version": "1.0.0",
        "status": "running",
        "environment": os.environ.get("ENVIRONMENT", "production")
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "vyaparai-api",
        "version": "1.0.0",
        "timestamp": "2025-01-03T10:00:00Z"
    }