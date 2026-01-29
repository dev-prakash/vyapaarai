"""
Notification Models - Pydantic models for notification API requests/responses
"""

from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field
from datetime import datetime


# ============================================================================
# Request Models
# ============================================================================

class RegisterDeviceRequest(BaseModel):
    """Request to register a device token"""
    token: str = Field(..., description="FCM device token")
    platform: str = Field(..., description="Platform: web, android, ios")
    browser: Optional[str] = Field(None, description="Browser name for web platform")
    device_info: Optional[Dict] = Field(None, description="Additional device information")

    class Config:
        json_schema_extra = {
            "example": {
                "token": "fcm_token_abc123...",
                "platform": "web",
                "browser": "chrome",
                "device_info": {
                    "user_agent": "Mozilla/5.0...",
                    "screen_width": 1920,
                    "screen_height": 1080
                }
            }
        }


class UnregisterDeviceRequest(BaseModel):
    """Request to unregister a device token"""
    device_id: str = Field(..., description="Device ID to unregister")

    class Config:
        json_schema_extra = {
            "example": {
                "device_id": "abc123def456"
            }
        }


class NotificationTypesPreferences(BaseModel):
    """Preferences for different notification types"""
    order_updates: Optional[bool] = Field(True, description="Order confirmations, status changes")
    delivery_alerts: Optional[bool] = Field(True, description="Out for delivery, delivered")
    promotions: Optional[bool] = Field(False, description="Marketing, offers")
    price_drops: Optional[bool] = Field(False, description="Wishlist price alerts")
    back_in_stock: Optional[bool] = Field(False, description="Inventory alerts")


class NotificationChannelsPreferences(BaseModel):
    """Preferences for notification channels"""
    push: Optional[bool] = Field(True, description="Push notifications via Firebase")


class QuietHoursPreferences(BaseModel):
    """Quiet hours configuration"""
    enabled: Optional[bool] = Field(False, description="Enable quiet hours")
    start: Optional[str] = Field("22:00", description="Start time (HH:MM)")
    end: Optional[str] = Field("08:00", description="End time (HH:MM)")
    timezone: Optional[str] = Field("Asia/Kolkata", description="Timezone for quiet hours")


class UpdatePreferencesRequest(BaseModel):
    """Request to update notification preferences"""
    notifications: Optional[bool] = Field(None, description="Master toggle for all notifications")
    notification_types: Optional[NotificationTypesPreferences] = Field(None, description="Per-type preferences")
    notification_channels: Optional[NotificationChannelsPreferences] = Field(None, description="Channel preferences")
    quiet_hours: Optional[QuietHoursPreferences] = Field(None, description="Quiet hours settings")

    class Config:
        json_schema_extra = {
            "example": {
                "notifications": True,
                "notification_types": {
                    "order_updates": True,
                    "delivery_alerts": True,
                    "promotions": False
                },
                "quiet_hours": {
                    "enabled": True,
                    "start": "22:00",
                    "end": "08:00",
                    "timezone": "Asia/Kolkata"
                }
            }
        }


class SendTestNotificationRequest(BaseModel):
    """Request to send a test notification"""
    title: Optional[str] = Field("Test Notification", description="Notification title")
    body: Optional[str] = Field("VyaparAI notifications are working!", description="Notification body")


# ============================================================================
# Response Models
# ============================================================================

class DeviceTokenResponse(BaseModel):
    """Device token information"""
    device_id: str
    platform: str
    browser: Optional[str] = None
    created_at: str
    last_used_at: str
    is_active: bool


class NotificationPreferencesResponse(BaseModel):
    """Full notification preferences response"""
    notifications: bool = Field(..., description="Master toggle")
    notification_types: Dict[str, bool] = Field(..., description="Per-type preferences")
    notification_channels: Dict[str, bool] = Field(..., description="Channel preferences")
    quiet_hours: Dict[str, Any] = Field(..., description="Quiet hours settings")
    device_tokens: Optional[List[DeviceTokenResponse]] = Field(None, description="Registered devices")

    class Config:
        json_schema_extra = {
            "example": {
                "notifications": True,
                "notification_types": {
                    "order_updates": True,
                    "delivery_alerts": True,
                    "promotions": False,
                    "price_drops": False,
                    "back_in_stock": False
                },
                "notification_channels": {
                    "push": True
                },
                "quiet_hours": {
                    "enabled": False,
                    "start": "22:00",
                    "end": "08:00",
                    "timezone": "Asia/Kolkata"
                },
                "device_tokens": [
                    {
                        "device_id": "abc123",
                        "platform": "web",
                        "browser": "chrome",
                        "created_at": "2025-12-19T10:30:00Z",
                        "last_used_at": "2025-12-19T10:30:00Z",
                        "is_active": True
                    }
                ]
            }
        }


class NotificationResultResponse(BaseModel):
    """Response for notification operations"""
    success: bool
    message: Optional[str] = None
    message_id: Optional[str] = None
    error: Optional[str] = None
    processing_time_ms: Optional[float] = None


class StandardResponse(BaseModel):
    """Standard API response wrapper"""
    success: bool
    data: Optional[Dict] = None
    error: Optional[str] = None
    timestamp: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {"message": "Operation completed"},
                "timestamp": "2025-12-19T10:30:00Z"
            }
        }
