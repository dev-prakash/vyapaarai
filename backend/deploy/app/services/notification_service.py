"""
Notification Service - Firebase Cloud Messaging Integration
Handles push notifications for order updates, delivery alerts, and promotions
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from decimal import Decimal
import asyncio
import logging
import os
import json
import base64
from datetime import datetime, time
import uuid

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)

# Try to import Firebase Admin SDK
try:
    import firebase_admin
    from firebase_admin import credentials, messaging
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    logger.warning("Firebase Admin SDK not installed. Push notifications disabled.")

# Try to import pytz for timezone handling
try:
    import pytz
    PYTZ_AVAILABLE = True
except ImportError:
    PYTZ_AVAILABLE = False
    logger.warning("pytz not installed. Quiet hours feature disabled.")


@dataclass
class NotificationResult:
    """Result of a notification operation"""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    processing_time_ms: float = 0.0


@dataclass
class DeviceToken:
    """Device token information"""
    device_id: str
    token: str
    platform: str  # "web", "android", "ios"
    browser: Optional[str] = None
    created_at: Optional[str] = None
    last_used_at: Optional[str] = None
    is_active: bool = True


# Default notification preferences
DEFAULT_NOTIFICATION_PREFERENCES = {
    "notifications": True,  # Master toggle
    "notification_types": {
        "order_updates": True,
        "delivery_alerts": True,
        "promotions": False,
        "price_drops": False,
        "back_in_stock": False,
    },
    "notification_channels": {
        "push": True,
    },
    "quiet_hours": {
        "enabled": False,
        "start": "22:00",
        "end": "08:00",
        "timezone": "Asia/Kolkata",
    },
}


class NotificationService:
    """
    Notification Service with Firebase Cloud Messaging integration

    Features:
    - Send push notifications via FCM
    - Device token management
    - Granular notification preferences
    - Quiet hours support
    - Order status notifications
    """

    def __init__(self):
        """Initialize notification service with Firebase and DynamoDB"""
        self.is_production = settings.ENVIRONMENT.lower() == 'production'
        self.firebase_initialized = False
        self.enabled = getattr(settings, 'ENABLE_PUSH_NOTIFICATIONS', True)

        # Initialize DynamoDB
        self._initialize_dynamodb()

        # Initialize Firebase
        if FIREBASE_AVAILABLE and self.enabled:
            self._initialize_firebase()
        else:
            logger.warning("Push notifications disabled or Firebase SDK not available")

    def _initialize_dynamodb(self):
        """Initialize DynamoDB connection"""
        try:
            kwargs = {'region_name': settings.AWS_REGION}
            if settings.DYNAMODB_ENDPOINT:
                kwargs['endpoint_url'] = settings.DYNAMODB_ENDPOINT

            self.dynamodb = boto3.resource('dynamodb', **kwargs)
            self.customers_table = self.dynamodb.Table(
                getattr(settings, 'DYNAMODB_CUSTOMERS_TABLE', 'vyaparai-customers-prod')
            )
            logger.info("✅ Notification service connected to DynamoDB")
        except Exception as e:
            logger.error(f"❌ DynamoDB connection failed: {e}")
            self.dynamodb = None
            self.customers_table = None

    def _initialize_firebase(self):
        """Initialize Firebase Admin SDK"""
        try:
            # Check if Firebase is already initialized
            try:
                firebase_admin.get_app()
                self.firebase_initialized = True
                logger.info("✅ Firebase Admin SDK already initialized")
                return
            except ValueError:
                pass  # App not initialized, continue

            # Try to load credentials from base64 encoded JSON (for Lambda)
            creds_json = getattr(settings, 'FIREBASE_CREDENTIALS_JSON', None)
            if creds_json:
                try:
                    creds_dict = json.loads(base64.b64decode(creds_json).decode('utf-8'))
                    cred = credentials.Certificate(creds_dict)
                    firebase_admin.initialize_app(cred)
                    self.firebase_initialized = True
                    logger.info("✅ Firebase Admin SDK initialized from base64 credentials")
                    return
                except Exception as e:
                    logger.warning(f"Failed to load base64 credentials: {e}")

            # Try to load credentials from file path (for local development)
            creds_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None)
            if creds_path and os.path.exists(creds_path):
                try:
                    cred = credentials.Certificate(creds_path)
                    firebase_admin.initialize_app(cred)
                    self.firebase_initialized = True
                    logger.info(f"✅ Firebase Admin SDK initialized from file: {creds_path}")
                    return
                except Exception as e:
                    logger.warning(f"Failed to load credentials from file: {e}")

            # Try default credentials (for Google Cloud environments)
            try:
                firebase_admin.initialize_app()
                self.firebase_initialized = True
                logger.info("✅ Firebase Admin SDK initialized with default credentials")
                return
            except Exception as e:
                logger.warning(f"Failed to initialize with default credentials: {e}")

            logger.error("❌ Could not initialize Firebase Admin SDK")

        except Exception as e:
            logger.error(f"❌ Firebase initialization error: {e}")
            self.firebase_initialized = False

    async def register_device_token(
        self,
        customer_id: str,
        token: str,
        platform: str,
        browser: Optional[str] = None,
        device_info: Optional[Dict] = None
    ) -> NotificationResult:
        """
        Register a device token for a customer

        Args:
            customer_id: Customer ID
            token: FCM device token
            platform: Platform (web, android, ios)
            browser: Browser name (for web)
            device_info: Additional device information
        """
        start_time = datetime.utcnow()

        try:
            if not self.customers_table:
                return NotificationResult(
                    success=False,
                    error="Database not available"
                )

            device_id = str(uuid.uuid4())[:12]
            now = datetime.utcnow().isoformat()

            device_token = {
                "device_id": device_id,
                "token": token,
                "platform": platform,
                "browser": browser,
                "created_at": now,
                "last_used_at": now,
                "is_active": True,
            }

            if device_info:
                device_token["device_info"] = device_info

            # Update customer record with new device token
            # First, get existing tokens to avoid duplicates
            response = await asyncio.to_thread(
                self.customers_table.get_item,
                Key={'customer_id': customer_id},
                ProjectionExpression='device_tokens'
            )

            existing_tokens = response.get('Item', {}).get('device_tokens', [])

            # Remove any existing token with the same FCM token (update scenario)
            existing_tokens = [t for t in existing_tokens if t.get('token') != token]

            # Add new token
            existing_tokens.append(device_token)

            # Keep only the last 5 device tokens per customer
            if len(existing_tokens) > 5:
                existing_tokens = existing_tokens[-5:]

            # Update customer record
            await asyncio.to_thread(
                self.customers_table.update_item,
                Key={'customer_id': customer_id},
                UpdateExpression='SET device_tokens = :tokens, updated_at = :now',
                ExpressionAttributeValues={
                    ':tokens': existing_tokens,
                    ':now': now
                }
            )

            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            logger.info(f"✅ Registered device token for customer {customer_id}")
            return NotificationResult(
                success=True,
                message_id=device_id,
                processing_time_ms=processing_time
            )

        except Exception as e:
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"❌ Failed to register device token: {e}")
            return NotificationResult(
                success=False,
                error=str(e),
                processing_time_ms=processing_time
            )

    async def unregister_device_token(
        self,
        customer_id: str,
        device_id: str
    ) -> NotificationResult:
        """Remove a device token for a customer"""
        start_time = datetime.utcnow()

        try:
            if not self.customers_table:
                return NotificationResult(success=False, error="Database not available")

            # Get existing tokens
            response = await asyncio.to_thread(
                self.customers_table.get_item,
                Key={'customer_id': customer_id},
                ProjectionExpression='device_tokens'
            )

            existing_tokens = response.get('Item', {}).get('device_tokens', [])

            # Remove the specified device
            updated_tokens = [t for t in existing_tokens if t.get('device_id') != device_id]

            # Update customer record
            await asyncio.to_thread(
                self.customers_table.update_item,
                Key={'customer_id': customer_id},
                UpdateExpression='SET device_tokens = :tokens, updated_at = :now',
                ExpressionAttributeValues={
                    ':tokens': updated_tokens,
                    ':now': datetime.utcnow().isoformat()
                }
            )

            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            return NotificationResult(success=True, processing_time_ms=processing_time)

        except Exception as e:
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"❌ Failed to unregister device token: {e}")
            return NotificationResult(success=False, error=str(e), processing_time_ms=processing_time)

    async def get_notification_preferences(self, customer_id: str) -> Dict:
        """Get notification preferences for a customer"""
        try:
            if not self.customers_table:
                return DEFAULT_NOTIFICATION_PREFERENCES.copy()

            response = await asyncio.to_thread(
                self.customers_table.get_item,
                Key={'customer_id': customer_id},
                ProjectionExpression='preferences'
            )

            preferences = response.get('Item', {}).get('preferences', {})

            # Merge with defaults to ensure all fields exist
            result = DEFAULT_NOTIFICATION_PREFERENCES.copy()
            if preferences:
                # Update top-level notification flag
                if 'notifications' in preferences:
                    result['notifications'] = preferences['notifications']

                # Update notification types
                if 'notification_types' in preferences:
                    result['notification_types'].update(preferences['notification_types'])

                # Update notification channels
                if 'notification_channels' in preferences:
                    result['notification_channels'].update(preferences['notification_channels'])

                # Update quiet hours
                if 'quiet_hours' in preferences:
                    result['quiet_hours'].update(preferences['quiet_hours'])

            return result

        except Exception as e:
            logger.error(f"❌ Failed to get notification preferences: {e}")
            return DEFAULT_NOTIFICATION_PREFERENCES.copy()

    async def update_notification_preferences(
        self,
        customer_id: str,
        preferences: Dict
    ) -> NotificationResult:
        """Update notification preferences for a customer"""
        start_time = datetime.utcnow()

        try:
            if not self.customers_table:
                return NotificationResult(success=False, error="Database not available")

            # Get current preferences
            current = await self.get_notification_preferences(customer_id)

            # Merge with new preferences
            if 'notifications' in preferences:
                current['notifications'] = preferences['notifications']
            if 'notification_types' in preferences:
                current['notification_types'].update(preferences['notification_types'])
            if 'notification_channels' in preferences:
                current['notification_channels'].update(preferences['notification_channels'])
            if 'quiet_hours' in preferences:
                current['quiet_hours'].update(preferences['quiet_hours'])

            # Update in DynamoDB
            await asyncio.to_thread(
                self.customers_table.update_item,
                Key={'customer_id': customer_id},
                UpdateExpression='SET preferences = :prefs, updated_at = :now',
                ExpressionAttributeValues={
                    ':prefs': current,
                    ':now': datetime.utcnow().isoformat()
                }
            )

            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.info(f"✅ Updated notification preferences for customer {customer_id}")
            return NotificationResult(success=True, processing_time_ms=processing_time)

        except Exception as e:
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"❌ Failed to update notification preferences: {e}")
            return NotificationResult(success=False, error=str(e), processing_time_ms=processing_time)

    def _is_quiet_hours(self, quiet_hours: Dict) -> bool:
        """Check if current time is within quiet hours"""
        if not quiet_hours.get('enabled', False):
            return False

        if not PYTZ_AVAILABLE:
            return False

        try:
            tz = pytz.timezone(quiet_hours.get('timezone', 'Asia/Kolkata'))
            now = datetime.now(tz)
            current_time = now.time()

            start_str = quiet_hours.get('start', '22:00')
            end_str = quiet_hours.get('end', '08:00')

            start_time = time(int(start_str.split(':')[0]), int(start_str.split(':')[1]))
            end_time = time(int(end_str.split(':')[0]), int(end_str.split(':')[1]))

            # Handle overnight quiet hours (e.g., 22:00 to 08:00)
            if start_time > end_time:
                # Quiet hours span midnight
                return current_time >= start_time or current_time <= end_time
            else:
                # Quiet hours within same day
                return start_time <= current_time <= end_time

        except Exception as e:
            logger.error(f"Error checking quiet hours: {e}")
            return False

    async def should_send_notification(
        self,
        customer_id: str,
        notification_type: str
    ) -> bool:
        """
        Check if a notification should be sent based on preferences

        Args:
            customer_id: Customer ID
            notification_type: Type of notification (order_updates, delivery_alerts, etc.)
        """
        try:
            prefs = await self.get_notification_preferences(customer_id)

            # Check master toggle
            if not prefs.get('notifications', True):
                return False

            # Check push channel
            if not prefs.get('notification_channels', {}).get('push', True):
                return False

            # Check notification type
            if not prefs.get('notification_types', {}).get(notification_type, True):
                return False

            # Check quiet hours
            if self._is_quiet_hours(prefs.get('quiet_hours', {})):
                logger.info(f"Skipping notification for {customer_id} - quiet hours active")
                return False

            return True

        except Exception as e:
            logger.error(f"Error checking notification preferences: {e}")
            return True  # Default to sending if we can't check

    async def _get_customer_tokens(self, customer_id: str) -> List[str]:
        """Get active device tokens for a customer"""
        try:
            if not self.customers_table:
                return []

            response = await asyncio.to_thread(
                self.customers_table.get_item,
                Key={'customer_id': customer_id},
                ProjectionExpression='device_tokens'
            )

            device_tokens = response.get('Item', {}).get('device_tokens', [])

            # Return only active tokens
            return [t['token'] for t in device_tokens if t.get('is_active', True)]

        except Exception as e:
            logger.error(f"Error getting customer tokens: {e}")
            return []

    async def send_to_token(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        image: Optional[str] = None
    ) -> NotificationResult:
        """
        Send a notification to a specific device token

        Args:
            token: FCM device token
            title: Notification title
            body: Notification body
            data: Additional data payload
            image: Optional image URL
        """
        start_time = datetime.utcnow()

        if not self.firebase_initialized:
            return NotificationResult(
                success=False,
                error="Firebase not initialized"
            )

        try:
            # Build notification
            notification = messaging.Notification(
                title=title,
                body=body,
                image=image
            )

            # Build message
            message = messaging.Message(
                notification=notification,
                token=token,
                data=data or {}
            )

            # Send message
            response = await asyncio.to_thread(messaging.send, message)

            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            logger.info(f"✅ Notification sent: {response}")
            return NotificationResult(
                success=True,
                message_id=response,
                processing_time_ms=processing_time
            )

        except messaging.UnregisteredError:
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.warning(f"Device token unregistered: {token[:20]}...")
            return NotificationResult(
                success=False,
                error="Device token unregistered",
                processing_time_ms=processing_time
            )

        except Exception as e:
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"❌ Failed to send notification: {e}")
            return NotificationResult(
                success=False,
                error=str(e),
                processing_time_ms=processing_time
            )

    async def send_notification(
        self,
        customer_id: str,
        title: str,
        body: str,
        notification_type: str = "order_updates",
        data: Optional[Dict[str, str]] = None,
        image: Optional[str] = None
    ) -> NotificationResult:
        """
        Send a notification to a customer (all their devices)

        Args:
            customer_id: Customer ID
            title: Notification title
            body: Notification body
            notification_type: Type for preference checking
            data: Additional data payload
            image: Optional image URL
        """
        start_time = datetime.utcnow()

        # Check if we should send
        should_send = await self.should_send_notification(customer_id, notification_type)
        if not should_send:
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            return NotificationResult(
                success=True,
                message_id="skipped",
                processing_time_ms=processing_time
            )

        # Get customer tokens
        tokens = await self._get_customer_tokens(customer_id)
        if not tokens:
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            return NotificationResult(
                success=False,
                error="No device tokens registered",
                processing_time_ms=processing_time
            )

        # Send to all tokens
        results = []
        for token in tokens:
            result = await self.send_to_token(token, title, body, data, image)
            results.append(result)

        # Check if at least one succeeded
        any_success = any(r.success for r in results)

        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        if any_success:
            return NotificationResult(
                success=True,
                message_id=f"sent_to_{len([r for r in results if r.success])}_devices",
                processing_time_ms=processing_time
            )
        else:
            return NotificationResult(
                success=False,
                error="Failed to send to any device",
                processing_time_ms=processing_time
            )

    # Convenience methods for specific notification types

    async def send_order_notification(
        self,
        customer_id: str,
        order_id: str,
        order_number: str,
        status: str
    ) -> NotificationResult:
        """Send order status notification"""
        status_messages = {
            'placed': ('Order Placed', f'Your order {order_number} has been placed successfully!'),
            'confirmed': ('Order Confirmed', f'Your order {order_number} has been confirmed!'),
            'preparing': ('Order Being Prepared', f'Your order {order_number} is being prepared'),
            'ready': ('Order Ready', f'Your order {order_number} is ready for pickup/delivery'),
            'out_for_delivery': ('Out for Delivery', f'Your order {order_number} is on the way!'),
            'delivered': ('Order Delivered', f'Your order {order_number} has been delivered!'),
            'cancelled': ('Order Cancelled', f'Your order {order_number} has been cancelled'),
        }

        title, body = status_messages.get(status, ('Order Update', f'Order {order_number}: {status}'))

        return await self.send_notification(
            customer_id=customer_id,
            title=title,
            body=body,
            notification_type='order_updates',
            data={
                'type': 'order_update',
                'order_id': order_id,
                'order_number': order_number,
                'status': status,
                'url': f'/customer/orders/{order_id}'
            }
        )

    async def send_delivery_alert(
        self,
        customer_id: str,
        order_id: str,
        order_number: str,
        estimated_time: str
    ) -> NotificationResult:
        """Send delivery alert notification"""
        return await self.send_notification(
            customer_id=customer_id,
            title='🚚 Delivery Alert',
            body=f'Your order {order_number} will arrive in {estimated_time}',
            notification_type='delivery_alerts',
            data={
                'type': 'delivery_alert',
                'order_id': order_id,
                'order_number': order_number,
                'url': f'/customer/orders/{order_id}/tracking'
            }
        )

    async def send_promotion_notification(
        self,
        customer_id: str,
        title: str,
        message: str,
        promo_url: Optional[str] = None
    ) -> NotificationResult:
        """Send promotional notification"""
        return await self.send_notification(
            customer_id=customer_id,
            title=f'🎉 {title}',
            body=message,
            notification_type='promotions',
            data={
                'type': 'promotion',
                'url': promo_url or '/customer/offers'
            }
        )

    async def send_test_notification(self, customer_id: str) -> NotificationResult:
        """Send a test notification"""
        return await self.send_notification(
            customer_id=customer_id,
            title='Test Notification',
            body='VyaparAI notifications are working!',
            notification_type='order_updates',  # Use order_updates to bypass promotion preferences
            data={
                'type': 'test',
                'timestamp': datetime.utcnow().isoformat()
            }
        )


# Singleton instance
notification_service = NotificationService()
