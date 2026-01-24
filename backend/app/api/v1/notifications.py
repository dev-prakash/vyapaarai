"""
Notification API Endpoints
Handles push notification registration, preferences, and testing
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from typing import Optional, Dict
from datetime import datetime
import logging
import jwt

from app.services.notification_service import notification_service
from app.models.notification import (
    RegisterDeviceRequest,
    UnregisterDeviceRequest,
    UpdatePreferencesRequest,
    SendTestNotificationRequest,
    NotificationPreferencesResponse,
    NotificationResultResponse,
    StandardResponse,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])

# ============================================================================
# Authentication
# ============================================================================

security = HTTPBearer()


def verify_token(token: str, expected_type: str = "customer") -> dict:
    """Verify JWT token and return payload"""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )

        # Verify token type
        token_type = payload.get('type', 'customer')
        if token_type != expected_type:
            raise jwt.InvalidTokenError(f"Expected {expected_type} token, got {token_type}")

        return payload
    except jwt.ExpiredSignatureError:
        raise jwt.ExpiredSignatureError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise jwt.InvalidTokenError(f"Invalid token: {str(e)}")


async def get_current_customer(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Verify JWT token and return customer data
    Used as dependency for protected endpoints
    """
    try:
        token = credentials.credentials
        payload = verify_token(token, expected_type="customer")

        customer_id = payload.get('customer_id')
        if not customer_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )

        return {"customer_id": customer_id, "payload": payload}

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )


# ============================================================================
# Device Registration Endpoints
# ============================================================================

@router.post("/register-device", response_model=StandardResponse)
async def register_device(
    request: RegisterDeviceRequest,
    current_customer: dict = Depends(get_current_customer)
):
    """
    Register a device token for push notifications

    This endpoint registers an FCM device token to receive push notifications.
    Customers can have up to 5 active device tokens (for multiple devices).
    """
    try:
        customer_id = current_customer["customer_id"]

        result = await notification_service.register_device_token(
            customer_id=customer_id,
            token=request.token,
            platform=request.platform,
            browser=request.browser,
            device_info=request.device_info
        )

        if result.success:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "success": True,
                    "data": {
                        "message": "Device registered successfully",
                        "device_id": result.message_id
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "error": result.error,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

    except Exception as e:
        logger.error(f"Error registering device: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register device: {str(e)}"
        )


@router.delete("/unregister-device", response_model=StandardResponse)
async def unregister_device(
    request: UnregisterDeviceRequest,
    current_customer: dict = Depends(get_current_customer)
):
    """
    Unregister a device token

    This endpoint removes a device token so it will no longer receive notifications.
    """
    try:
        customer_id = current_customer["customer_id"]

        result = await notification_service.unregister_device_token(
            customer_id=customer_id,
            device_id=request.device_id
        )

        if result.success:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "success": True,
                    "data": {"message": "Device unregistered successfully"},
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "error": result.error,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

    except Exception as e:
        logger.error(f"Error unregistering device: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unregister device: {str(e)}"
        )


# ============================================================================
# Preferences Endpoints
# ============================================================================

@router.get("/preferences", response_model=StandardResponse)
async def get_preferences(
    current_customer: dict = Depends(get_current_customer)
):
    """
    Get notification preferences

    Returns the customer's notification preferences including:
    - Master toggle
    - Per-type preferences (order updates, delivery alerts, promotions, etc.)
    - Channel preferences (push, SMS, email)
    - Quiet hours settings
    - Registered devices
    """
    try:
        customer_id = current_customer["customer_id"]

        preferences = await notification_service.get_notification_preferences(customer_id)

        # Get device tokens for the response
        device_tokens = []
        if notification_service.customers_table:
            try:
                import asyncio
                response = await asyncio.to_thread(
                    notification_service.customers_table.get_item,
                    Key={'customer_id': customer_id},
                    ProjectionExpression='device_tokens'
                )
                tokens = response.get('Item', {}).get('device_tokens', [])
                device_tokens = [
                    {
                        "device_id": t.get("device_id"),
                        "platform": t.get("platform"),
                        "browser": t.get("browser"),
                        "created_at": t.get("created_at"),
                        "last_used_at": t.get("last_used_at"),
                        "is_active": t.get("is_active", True)
                    }
                    for t in tokens
                ]
            except Exception as e:
                logger.warning(f"Failed to get device tokens: {e}")

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": {
                    **preferences,
                    "device_tokens": device_tokens
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    except Exception as e:
        logger.error(f"Error getting preferences: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get preferences: {str(e)}"
        )


@router.put("/preferences", response_model=StandardResponse)
async def update_preferences(
    request: UpdatePreferencesRequest,
    current_customer: dict = Depends(get_current_customer)
):
    """
    Update notification preferences

    Update any or all notification preferences. Only provided fields will be updated.
    """
    try:
        customer_id = current_customer["customer_id"]

        # Convert Pydantic model to dict, excluding None values
        preferences_update = {}

        if request.notifications is not None:
            preferences_update["notifications"] = request.notifications

        if request.notification_types is not None:
            preferences_update["notification_types"] = request.notification_types.dict(exclude_none=True)

        if request.notification_channels is not None:
            preferences_update["notification_channels"] = request.notification_channels.dict(exclude_none=True)

        if request.quiet_hours is not None:
            preferences_update["quiet_hours"] = request.quiet_hours.dict(exclude_none=True)

        result = await notification_service.update_notification_preferences(
            customer_id=customer_id,
            preferences=preferences_update
        )

        if result.success:
            # Get updated preferences
            updated_prefs = await notification_service.get_notification_preferences(customer_id)

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "success": True,
                    "data": {
                        "message": "Preferences updated successfully",
                        "preferences": updated_prefs
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "error": result.error,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

    except Exception as e:
        logger.error(f"Error updating preferences: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update preferences: {str(e)}"
        )


# ============================================================================
# Test Notification Endpoint
# ============================================================================

@router.post("/test", response_model=StandardResponse)
async def send_test_notification(
    request: SendTestNotificationRequest = SendTestNotificationRequest(),
    current_customer: dict = Depends(get_current_customer)
):
    """
    Send a test notification

    Sends a test push notification to verify that notifications are working.
    """
    try:
        customer_id = current_customer["customer_id"]

        result = await notification_service.send_test_notification(customer_id)

        if result.success:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "success": True,
                    "data": {
                        "message": "Test notification sent",
                        "message_id": result.message_id,
                        "processing_time_ms": result.processing_time_ms
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "error": result.error,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

    except Exception as e:
        logger.error(f"Error sending test notification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send test notification: {str(e)}"
        )


# ============================================================================
# Status Endpoint (no auth required)
# ============================================================================

@router.get("/status")
async def get_notification_status():
    """
    Get notification service status

    Returns the current status of the notification service including
    Firebase initialization status and feature flags.
    """
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "success": True,
            "data": {
                "enabled": notification_service.enabled,
                "firebase_initialized": notification_service.firebase_initialized,
                "dynamodb_connected": notification_service.customers_table is not None,
                "environment": settings.ENVIRONMENT
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    )
