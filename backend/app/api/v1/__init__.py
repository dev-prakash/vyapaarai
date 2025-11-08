"""
API v1 Router Initialization
Exports all routers for the VyaparAI API v1
"""

from fastapi import APIRouter
from .orders import router as orders_router
from .auth import router as auth_router
from .customer_auth import router as customer_auth_router
from .analytics import router as analytics_router
from .customers import router as customers_router
from .inventory import router as inventory_router
from .stores import router as stores_router

# Create main v1 router
api_v1_router = APIRouter(prefix="/api/v1")

# Include all routers
api_v1_router.include_router(auth_router)
api_v1_router.include_router(customer_auth_router)
api_v1_router.include_router(orders_router)
api_v1_router.include_router(analytics_router)
api_v1_router.include_router(customers_router)
api_v1_router.include_router(inventory_router)
api_v1_router.include_router(stores_router)

# Export the main router
__all__ = ["api_v1_router"]
