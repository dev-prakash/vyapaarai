"""
API v1 Router Initialization
Exports all routers for the VyaparAI API v1
"""

from fastapi import APIRouter
from .orders import router as orders_router
from .auth import router as auth_router
from .admin_auth import router as admin_auth_router
from .admin_products import router as admin_products_router
from .customer_auth import router as customer_auth_router
from .customer_orders import router as customer_orders_router
from .analytics import router as analytics_router
from .customers import router as customers_router
from .inventory import router as inventory_router
from .stores import router as stores_router
# TEMPORARILY DISABLED - PIL not in Lambda package
# from .product_media import router as product_media_router
from .cart import router as cart_router
from .cart_migration import router as cart_migration_router
from .public import router as public_router
from .notifications import router as notifications_router
from .payments import router as payments_router
from .khata import router as khata_router

# Create main v1 router
api_v1_router = APIRouter(prefix="/api/v1")

# Include all routers
api_v1_router.include_router(auth_router)
api_v1_router.include_router(admin_auth_router)
api_v1_router.include_router(admin_products_router)
api_v1_router.include_router(customer_auth_router)
api_v1_router.include_router(customer_orders_router)
api_v1_router.include_router(orders_router)
api_v1_router.include_router(analytics_router)
api_v1_router.include_router(customers_router)
api_v1_router.include_router(inventory_router)
api_v1_router.include_router(stores_router)
# api_v1_router.include_router(product_media_router)  # TEMPORARILY DISABLED
api_v1_router.include_router(cart_router)
api_v1_router.include_router(cart_migration_router)
api_v1_router.include_router(public_router, prefix="/public", tags=["Public"])
api_v1_router.include_router(notifications_router)
api_v1_router.include_router(payments_router, prefix="/payments", tags=["Payments"])
api_v1_router.include_router(khata_router)

# Export the main router
__all__ = ["api_v1_router"]
