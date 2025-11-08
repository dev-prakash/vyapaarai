"""
Google RCS Business Messaging Client for VyaparAI
Handles communication with Google RCS Business Messaging API
"""

import os
import logging
import google.auth
from google.auth.transport.requests import Request
from google.oauth2 import service_account
import httpx
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class RCSClient:
    """Google RCS Business Messaging client"""
    
    def __init__(self):
        """Initialize RCS client with credentials and configuration"""
        self.agent_id = os.environ.get('RCS_AGENT_ID')
        self.project_id = os.environ.get('GOOGLE_CLOUD_PROJECT_ID')
        self.credentials = self._get_credentials()
        self.base_url = "https://rcsbusinessmessaging.googleapis.com/v1"
        self.client = httpx.AsyncClient(timeout=30.0)
        
        if not self.agent_id:
            logger.warning("RCS_AGENT_ID not set, RCS functionality will be disabled")
    
    def _get_credentials(self) -> Optional[service_account.Credentials]:
        """Initialize Google service account credentials"""
        try:
            # Try to load from service account file
            service_account_path = os.environ.get('RCS_SERVICE_ACCOUNT_PATH', 'rcs-service-account.json')
            
            if os.path.exists(service_account_path):
                return service_account.Credentials.from_service_account_file(
                    service_account_path,
                    scopes=['https://www.googleapis.com/auth/rcsbusinessmessaging']
                )
            else:
                # Try to use default credentials
                logger.info("Service account file not found, using default credentials")
                credentials, project = google.auth.default(
                    scopes=['https://www.googleapis.com/auth/rcsbusinessmessaging']
                )
                return credentials
                
        except Exception as e:
            logger.error(f"Failed to initialize RCS credentials: {e}")
            return None
    
    async def send_message(
        self, 
        phone: str, 
        text: str, 
        suggestions: List[Dict] = None,
        fallback_text: str = None
    ) -> Dict[str, Any]:
        """Send text message with optional suggested replies"""
        
        if not self.credentials or not self.agent_id:
            logger.warning("RCS not configured, skipping message send")
            return {"status": "skipped", "reason": "not_configured"}
        
        try:
            message = {
                "contentMessage": {
                    "text": text
                }
            }
            
            if suggestions:
                message["contentMessage"]["suggestions"] = suggestions
            
            if fallback_text:
                message["contentMessage"]["fallbackText"] = fallback_text
            
            return await self._send_api_request(phone, message)
            
        except Exception as e:
            logger.error(f"Error sending RCS message: {e}")
            return {"status": "error", "error": str(e)}
    
    async def send_rich_card(
        self,
        phone: str,
        card: Dict[str, Any],
        fallback_text: str = None
    ) -> Dict[str, Any]:
        """Send rich card with media and actions"""
        
        if not self.credentials or not self.agent_id:
            logger.warning("RCS not configured, skipping rich card send")
            return {"status": "skipped", "reason": "not_configured"}
        
        try:
            message = {
                "contentMessage": {
                    "richCard": {
                        "standaloneCard": {
                            "cardOrientation": "VERTICAL",
                            "cardContent": card
                        }
                    }
                }
            }
            
            if fallback_text:
                message["contentMessage"]["fallbackText"] = fallback_text
            
            return await self._send_api_request(phone, message)
            
        except Exception as e:
            logger.error(f"Error sending RCS rich card: {e}")
            return {"status": "error", "error": str(e)}
    
    async def send_carousel(
        self,
        phone: str,
        cards: List[Dict[str, Any]],
        fallback_text: str = None
    ) -> Dict[str, Any]:
        """Send carousel of multiple cards"""
        
        if not self.credentials or not self.agent_id:
            logger.warning("RCS not configured, skipping carousel send")
            return {"status": "skipped", "reason": "not_configured"}
        
        try:
            message = {
                "contentMessage": {
                    "richCard": {
                        "carouselCard": {
                            "cardWidth": "MEDIUM",
                            "cardContents": cards
                        }
                    }
                }
            }
            
            if fallback_text:
                message["contentMessage"]["fallbackText"] = fallback_text
            
            return await self._send_api_request(phone, message)
            
        except Exception as e:
            logger.error(f"Error sending RCS carousel: {e}")
            return {"status": "error", "error": str(e)}
    
    async def send_typing_indicator(self, phone: str) -> Dict[str, Any]:
        """Show typing indicator"""
        
        if not self.credentials or not self.agent_id:
            logger.warning("RCS not configured, skipping typing indicator")
            return {"status": "skipped", "reason": "not_configured"}
        
        try:
            event = {
                "eventType": "TYPING_STARTED",
                "representative": {
                    "representativeType": "BOT"
                }
            }
            
            return await self._send_event(phone, event)
            
        except Exception as e:
            logger.error(f"Error sending typing indicator: {e}")
            return {"status": "error", "error": str(e)}
    
    async def send_read_receipt(self, phone: str, message_id: str) -> Dict[str, Any]:
        """Send read receipt for a message"""
        
        if not self.credentials or not self.agent_id:
            logger.warning("RCS not configured, skipping read receipt")
            return {"status": "skipped", "reason": "not_configured"}
        
        try:
            event = {
                "eventType": "READ",
                "representative": {
                    "representativeType": "BOT"
                },
                "messageId": message_id
            }
            
            return await self._send_event(phone, event)
            
        except Exception as e:
            logger.error(f"Error sending read receipt: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _send_api_request(self, phone: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send message via RCS API"""
        
        try:
            # Clean phone number
            clean_phone = phone.replace('+', '').replace(' ', '').replace('-', '')
            
            # Add required fields
            message["agentId"] = self.agent_id
            message["messageId"] = f"msg-{datetime.now().timestamp()}-{clean_phone[-4:]}"
            message["msisdn"] = clean_phone
            
            url = f"{self.base_url}/phones/{phone}/agentMessages"
            
            # Get auth token
            if self.credentials:
                self.credentials.refresh(Request())
                token = self.credentials.token
            else:
                logger.error("No credentials available")
                return {"status": "error", "error": "no_credentials"}
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            logger.info(f"Sending RCS message to {phone}")
            response = await self.client.post(
                url,
                headers=headers,
                json=message
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"RCS message sent successfully: {result.get('name', 'unknown')}")
                return {"status": "success", "message_id": result.get('name')}
            else:
                logger.error(f"RCS API error: {response.status_code} - {response.text}")
                return {"status": "error", "error": f"API error: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Error in RCS API request: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _send_event(self, phone: str, event: Dict[str, Any]) -> Dict[str, Any]:
        """Send event (typing indicator, read receipt)"""
        
        try:
            # Clean phone number
            clean_phone = phone.replace('+', '').replace(' ', '').replace('-', '')
            
            url = f"{self.base_url}/phones/{phone}/agentEvents"
            
            if self.credentials:
                self.credentials.refresh(Request())
                token = self.credentials.token
            else:
                logger.error("No credentials available")
                return {"status": "error", "error": "no_credentials"}
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            # Add required fields
            event["agentId"] = self.agent_id
            event["eventId"] = f"evt-{datetime.now().timestamp()}-{clean_phone[-4:]}"
            event["msisdn"] = clean_phone
            
            logger.info(f"Sending RCS event to {phone}")
            response = await self.client.post(url, headers=headers, json=event)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"RCS event sent successfully: {result.get('name', 'unknown')}")
                return {"status": "success", "event_id": result.get('name')}
            else:
                logger.error(f"RCS API error: {response.status_code} - {response.text}")
                return {"status": "error", "error": f"API error: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Error in RCS event request: {e}")
            return {"status": "error", "error": str(e)}
    
    async def get_agent_info(self) -> Dict[str, Any]:
        """Get agent information"""
        
        if not self.credentials or not self.agent_id:
            return {"status": "error", "error": "not_configured"}
        
        try:
            url = f"{self.base_url}/agents/{self.agent_id}"
            
            if self.credentials:
                self.credentials.refresh(Request())
                token = self.credentials.token
            else:
                return {"status": "error", "error": "no_credentials"}
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            response = await self.client.get(url, headers=headers)
            
            if response.status_code == 200:
                return {"status": "success", "agent": response.json()}
            else:
                return {"status": "error", "error": f"API error: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Error getting agent info: {e}")
            return {"status": "error", "error": str(e)}
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

# Global instance
rcs_client = RCSClient()
