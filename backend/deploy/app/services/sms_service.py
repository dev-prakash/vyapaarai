"""
SMS Service - Gupshup Integration for OTP and Transactional SMS
Handles SMS delivery for OTP verification and order notifications

Gupshup Enterprise SMS API Documentation:
https://docs.gupshup.io/docs/sms-api-introduction
"""

import os
import logging
import asyncio
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import aiohttp
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# Environment detection
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT == "production"


@dataclass
class SMSResult:
    """Result of an SMS operation"""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    provider_response: Optional[Dict] = None
    processing_time_ms: float = 0.0


class GupshupSMSService:
    """
    Gupshup Enterprise SMS Service

    Features:
    - Send OTP via SMS
    - Send transactional messages
    - DLT compliant (India regulations)
    - Async/non-blocking operations

    Required Environment Variables:
    - GUPSHUP_USERID: Your Gupshup user ID
    - GUPSHUP_PASSWORD: Your Gupshup password
    - GUPSHUP_SENDER_ID: Registered sender ID (6 chars for India)
    - GUPSHUP_OTP_TEMPLATE_ID: DLT registered template ID for OTP
    - GUPSHUP_ENTITY_ID: Principal Entity ID from DLT registration
    """

    # Gupshup API endpoints
    BASE_URL = "https://enterprise.smsgupshup.com/GatewayAPI/rest"

    def __init__(self):
        """Initialize Gupshup SMS service with credentials"""
        self.userid = os.getenv("GUPSHUP_USERID", "")
        self.password = os.getenv("GUPSHUP_PASSWORD", "")
        self.sender_id = os.getenv("GUPSHUP_SENDER_ID", "VYAPAR")  # 6 char sender ID
        self.otp_template_id = os.getenv("GUPSHUP_OTP_TEMPLATE_ID", "")
        self.entity_id = os.getenv("GUPSHUP_ENTITY_ID", "")  # DLT Principal Entity ID

        # Check if credentials are configured
        self.is_configured = bool(self.userid and self.password)

        if not self.is_configured:
            logger.warning("Gupshup SMS credentials not configured. SMS will be disabled.")
        else:
            logger.info(f"Gupshup SMS service initialized (Sender: {self.sender_id})")

    def _format_phone_number(self, phone: str) -> str:
        """
        Format phone number for Gupshup API
        Gupshup expects: 91XXXXXXXXXX (country code + 10 digit number)
        """
        # Remove all non-digit characters
        phone = ''.join(filter(str.isdigit, phone))

        # If starts with 0, remove it
        if phone.startswith('0'):
            phone = phone[1:]

        # If 10 digits, add India country code
        if len(phone) == 10:
            phone = '91' + phone

        # If starts with +91, remove the +
        if phone.startswith('91') and len(phone) == 12:
            return phone

        # If starts with 91 and is 12 digits, it's correct
        return phone

    async def send_otp(
        self,
        phone: str,
        otp: str,
        template_message: Optional[str] = None
    ) -> SMSResult:
        """
        Send OTP via SMS using Gupshup

        Args:
            phone: Phone number (with or without country code)
            otp: The OTP code to send
            template_message: Optional custom message template
                             Use {otp} as placeholder for OTP code

        Returns:
            SMSResult with success status and details
        """
        start_time = datetime.utcnow()

        # Check if service is configured
        if not self.is_configured:
            if IS_PRODUCTION:
                logger.error("SMS service not configured in production!")
                return SMSResult(
                    success=False,
                    error="SMS service not configured",
                    processing_time_ms=0
                )
            else:
                # In development, log the OTP and return success
                logger.info(f"[DEV MODE] OTP for {phone[-4:].rjust(len(phone), '*')}: {otp}")
                return SMSResult(
                    success=True,
                    message_id="dev_mode_no_sms",
                    processing_time_ms=0
                )

        try:
            # Format phone number
            formatted_phone = self._format_phone_number(phone)

            # Build message
            if template_message:
                message = template_message.replace("{otp}", otp)
            else:
                message = f"Your VyaparAI verification code is {otp}. Valid for 5 minutes. Do not share this code."

            # Build API parameters
            params = {
                "userid": self.userid,
                "password": self.password,
                "send_to": formatted_phone,
                "msg": message,
                "method": "SendMessage",
                "msg_type": "TEXT",
                "format": "JSON",
                "auth_scheme": "PLAIN",
                "v": "1.1"
            }

            # Add DLT parameters if configured (required for India)
            if self.entity_id:
                params["principalEntityId"] = self.entity_id
            if self.otp_template_id:
                params["dltTemplateId"] = self.otp_template_id

            # Make API request
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.BASE_URL,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    response_text = await response.text()

                    processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                    # Parse response
                    # Gupshup returns: success | <message_id> or error | <error_message>
                    if response.status == 200:
                        if "success" in response_text.lower():
                            # Extract message ID from response
                            parts = response_text.split("|")
                            message_id = parts[1].strip() if len(parts) > 1 else "unknown"

                            logger.info(f"SMS sent successfully to {formatted_phone[-4:].rjust(12, '*')}")
                            return SMSResult(
                                success=True,
                                message_id=message_id,
                                provider_response={"raw": response_text},
                                processing_time_ms=processing_time
                            )
                        else:
                            logger.error(f"Gupshup API error: {response_text}")
                            return SMSResult(
                                success=False,
                                error=response_text,
                                provider_response={"raw": response_text},
                                processing_time_ms=processing_time
                            )
                    else:
                        logger.error(f"Gupshup HTTP error: {response.status} - {response_text}")
                        return SMSResult(
                            success=False,
                            error=f"HTTP {response.status}: {response_text}",
                            processing_time_ms=processing_time
                        )

        except asyncio.TimeoutError:
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error("SMS request timed out")
            return SMSResult(
                success=False,
                error="Request timed out",
                processing_time_ms=processing_time
            )

        except Exception as e:
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"SMS send error: {str(e)}")
            return SMSResult(
                success=False,
                error=str(e),
                processing_time_ms=processing_time
            )

    async def send_transactional_sms(
        self,
        phone: str,
        message: str,
        template_id: Optional[str] = None
    ) -> SMSResult:
        """
        Send transactional SMS (order updates, delivery notifications, etc.)

        Args:
            phone: Phone number
            message: Message content (must match DLT registered template)
            template_id: DLT template ID for this message type

        Returns:
            SMSResult with success status
        """
        start_time = datetime.utcnow()

        if not self.is_configured:
            if IS_PRODUCTION:
                return SMSResult(success=False, error="SMS service not configured")
            else:
                logger.info(f"[DEV MODE] SMS to {phone[-4:].rjust(len(phone), '*')}: {message[:50]}...")
                return SMSResult(success=True, message_id="dev_mode_no_sms")

        try:
            formatted_phone = self._format_phone_number(phone)

            params = {
                "userid": self.userid,
                "password": self.password,
                "send_to": formatted_phone,
                "msg": message,
                "method": "SendMessage",
                "msg_type": "TEXT",
                "format": "JSON",
                "auth_scheme": "PLAIN",
                "v": "1.1"
            }

            if self.entity_id:
                params["principalEntityId"] = self.entity_id
            if template_id:
                params["dltTemplateId"] = template_id

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.BASE_URL,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    response_text = await response.text()
                    processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                    if response.status == 200 and "success" in response_text.lower():
                        parts = response_text.split("|")
                        message_id = parts[1].strip() if len(parts) > 1 else "unknown"
                        return SMSResult(
                            success=True,
                            message_id=message_id,
                            processing_time_ms=processing_time
                        )
                    else:
                        return SMSResult(
                            success=False,
                            error=response_text,
                            processing_time_ms=processing_time
                        )

        except Exception as e:
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            return SMSResult(success=False, error=str(e), processing_time_ms=processing_time)

    async def check_balance(self) -> Dict[str, Any]:
        """
        Check SMS credit balance

        Returns:
            Dictionary with balance information
        """
        if not self.is_configured:
            return {"error": "SMS service not configured", "balance": 0}

        try:
            params = {
                "userid": self.userid,
                "password": self.password,
                "method": "CREDITS",
                "format": "JSON",
                "v": "1.1"
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.BASE_URL,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    response_text = await response.text()

                    if response.status == 200:
                        # Parse balance from response
                        # Response format: success | balance
                        parts = response_text.split("|")
                        if len(parts) > 1 and "success" in parts[0].lower():
                            return {
                                "success": True,
                                "balance": float(parts[1].strip()),
                                "provider": "Gupshup"
                            }

                    return {"error": response_text, "balance": 0}

        except Exception as e:
            return {"error": str(e), "balance": 0}

    def get_status(self) -> Dict[str, Any]:
        """Get SMS service status"""
        return {
            "provider": "Gupshup",
            "configured": self.is_configured,
            "sender_id": self.sender_id if self.is_configured else None,
            "dlt_configured": bool(self.entity_id and self.otp_template_id),
            "environment": ENVIRONMENT
        }


# Singleton instance
sms_service = GupshupSMSService()


# Convenience function for sending OTP
async def send_otp_sms(phone: str, otp: str) -> SMSResult:
    """
    Send OTP via SMS

    This is a convenience function that uses the singleton sms_service.

    Args:
        phone: Phone number (Indian format)
        otp: OTP code to send

    Returns:
        SMSResult with success status
    """
    return await sms_service.send_otp(phone, otp)
