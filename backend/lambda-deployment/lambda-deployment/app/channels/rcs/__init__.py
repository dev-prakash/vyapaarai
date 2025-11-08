"""
RCS (Rich Communication Services) Module for VyaparAI
Handles Google RCS Business Messaging integration
"""

from .rcs_client import rcs_client
from .webhook_handler import router as rcs_webhook_router
from .rich_cards import (
    OrderConfirmationCard,
    ProductCarousel,
    OrderStatusCard,
    WelcomeCard
)

__all__ = [
    "rcs_client",
    "rcs_webhook_router",
    "OrderConfirmationCard",
    "ProductCarousel", 
    "OrderStatusCard",
    "WelcomeCard"
]
