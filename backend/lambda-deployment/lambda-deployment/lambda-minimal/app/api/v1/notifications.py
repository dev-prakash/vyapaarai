"""
Notifications API endpoints - Simplified for Lambda
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

class NotificationSettings(BaseModel):
    email_notifications: bool = True
    sms_notifications: bool = True
    push_notifications: bool = True
    order_alerts: bool = True
    low_stock_alerts: bool = True
    payment_alerts: bool = True

@router.get("/settings")
async def get_notification_settings():
    """
    Get notification settings - mock data for Lambda
    """
    return {
        "success": True,
        "settings": {
            "email_notifications": True,
            "sms_notifications": True, 
            "push_notifications": True,
            "order_alerts": True,
            "low_stock_alerts": True,
            "payment_alerts": True
        }
    }

@router.post("/settings")
async def update_notification_settings(settings: NotificationSettings):
    """
    Update notification settings - mock for Lambda
    """
    return {
        "success": True,
        "message": "Notification settings updated successfully",
        "settings": settings.dict()
    }