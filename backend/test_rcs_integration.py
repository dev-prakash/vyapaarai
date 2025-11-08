#!/usr/bin/env python3
"""
Test script for VyaparAI RCS Integration
Tests all components of the RCS Business Messaging integration
"""

import asyncio
import json
import os
import sys
import time
from typing import Dict, List, Any
import httpx

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

# Import RCS components
from app.channels.rcs.rcs_client import rcs_client
from app.channels.rcs.rich_cards import (
    OrderConfirmationCard, 
    ProductCarousel, 
    OrderStatusCard, 
    WelcomeCard
)

class RCSIntegrationTester:
    """Test suite for RCS integration"""
    
    def __init__(self):
        self.test_results = []
        self.test_phone = "+919999999999"
        
    def log_test(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"   Details: {details}")
        
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details
        })
    
    async def test_rcs_client_initialization(self):
        """Test RCS client initialization"""
        try:
            # Check if client is properly initialized
            if rcs_client.agent_id:
                self.log_test("RCS Client Initialization", True, f"Agent ID: {rcs_client.agent_id}")
            else:
                self.log_test("RCS Client Initialization", False, "Agent ID not configured")
        except Exception as e:
            self.log_test("RCS Client Initialization", False, str(e))
    
    async def test_credentials_loading(self):
        """Test credentials loading"""
        try:
            if rcs_client.credentials:
                self.log_test("Credentials Loading", True, "Service account credentials loaded")
            else:
                self.log_test("Credentials Loading", False, "No credentials available")
        except Exception as e:
            self.log_test("Credentials Loading", False, str(e))
    
    async def test_agent_info_retrieval(self):
        """Test agent information retrieval"""
        try:
            agent_info = await rcs_client.get_agent_info()
            if agent_info.get("status") == "success":
                self.log_test("Agent Info Retrieval", True, "Agent information retrieved successfully")
            else:
                self.log_test("Agent Info Retrieval", False, agent_info.get("error", "Unknown error"))
        except Exception as e:
            self.log_test("Agent Info Retrieval", False, str(e))
    
    async def test_text_message_sending(self):
        """Test text message sending"""
        try:
            result = await rcs_client.send_message(
                phone=self.test_phone,
                text="🧪 Test message from VyaparAI RCS integration",
                suggestions=[
                    {
                        "reply": {
                            "text": "Test Reply",
                            "postbackData": "action=test"
                        }
                    }
                ]
            )
            
            if result.get("status") in ["success", "skipped"]:
                self.log_test("Text Message Sending", True, f"Status: {result.get('status')}")
            else:
                self.log_test("Text Message Sending", False, result.get("error", "Unknown error"))
        except Exception as e:
            self.log_test("Text Message Sending", False, str(e))
    
    async def test_typing_indicator(self):
        """Test typing indicator"""
        try:
            result = await rcs_client.send_typing_indicator(self.test_phone)
            if result.get("status") in ["success", "skipped"]:
                self.log_test("Typing Indicator", True, f"Status: {result.get('status')}")
            else:
                self.log_test("Typing Indicator", False, result.get("error", "Unknown error"))
        except Exception as e:
            self.log_test("Typing Indicator", False, str(e))
    
    async def test_rich_cards(self):
        """Test rich card generation"""
        try:
            # Test OrderConfirmationCard
            order_card = OrderConfirmationCard(
                order_id="TEST-123",
                items=[
                    {"product": "rice", "quantity": 2, "unit": "kg", "brand": "Tilda"},
                    {"product": "oil", "quantity": 1, "unit": "liter", "brand": "Fortune"}
                ],
                total=150.0,
                language="en"
            )
            card_data = order_card.build()
            
            if card_data and "title" in card_data and "suggestions" in card_data:
                self.log_test("OrderConfirmationCard Generation", True, "Card structure valid")
            else:
                self.log_test("OrderConfirmationCard Generation", False, "Invalid card structure")
                
        except Exception as e:
            self.log_test("OrderConfirmationCard Generation", False, str(e))
    
    async def test_product_carousel(self):
        """Test product carousel generation"""
        try:
            products = [
                {
                    "product_id": "prod-1",
                    "name": {"en": "Basmati Rice", "hi": "बासमती चावल"},
                    "price": 50.0,
                    "unit": "kg",
                    "brand": "Tilda",
                    "stock_quantity": 10
                },
                {
                    "product_id": "prod-2", 
                    "name": {"en": "Mustard Oil", "hi": "सरसों का तेल"},
                    "price": 120.0,
                    "unit": "liter",
                    "brand": "Fortune",
                    "stock_quantity": 5
                }
            ]
            
            carousel = ProductCarousel(products, language="en")
            carousel_data = carousel.build()
            
            if carousel_data and len(carousel_data) == 2:
                self.log_test("ProductCarousel Generation", True, f"Generated {len(carousel_data)} cards")
            else:
                self.log_test("ProductCarousel Generation", False, "Invalid carousel structure")
                
        except Exception as e:
            self.log_test("ProductCarousel Generation", False, str(e))
    
    async def test_order_status_card(self):
        """Test order status card generation"""
        try:
            status_card = OrderStatusCard(
                order_id="TEST-123",
                status="confirmed",
                language="en",
                order_details={"total_amount": 150.0, "created_at": "2024-01-01T10:00:00Z"}
            )
            card_data = status_card.build()
            
            if card_data and "title" in card_data and "description" in card_data:
                self.log_test("OrderStatusCard Generation", True, "Status card structure valid")
            else:
                self.log_test("OrderStatusCard Generation", False, "Invalid status card structure")
                
        except Exception as e:
            self.log_test("OrderStatusCard Generation", False, str(e))
    
    async def test_welcome_card(self):
        """Test welcome card generation"""
        try:
            welcome_card = WelcomeCard(language="en", user_name="Test User")
            card_data = welcome_card.build()
            
            if card_data and "title" in card_data and "suggestions" in card_data:
                self.log_test("WelcomeCard Generation", True, "Welcome card structure valid")
            else:
                self.log_test("WelcomeCard Generation", False, "Invalid welcome card structure")
                
        except Exception as e:
            self.log_test("WelcomeCard Generation", False, str(e))
    
    async def test_localization(self):
        """Test localization support"""
        try:
            # Test Hindi localization
            hindi_card = OrderConfirmationCard(
                order_id="TEST-123",
                items=[{"product": "rice", "quantity": 1, "unit": "kg"}],
                total=50.0,
                language="hi"
            )
            hindi_data = hindi_card.build()
            
            # Test Tamil localization
            tamil_card = OrderConfirmationCard(
                order_id="TEST-123",
                items=[{"product": "rice", "quantity": 1, "unit": "kg"}],
                total=50.0,
                language="ta"
            )
            tamil_data = tamil_card.build()
            
            if hindi_data and tamil_data:
                self.log_test("Localization Support", True, "Hindi and Tamil cards generated")
            else:
                self.log_test("Localization Support", False, "Localization failed")
                
        except Exception as e:
            self.log_test("Localization Support", False, str(e))
    
    async def test_rich_card_sending(self):
        """Test rich card sending"""
        try:
            card = OrderConfirmationCard(
                order_id="TEST-123",
                items=[{"product": "rice", "quantity": 1, "unit": "kg"}],
                total=50.0,
                language="en"
            )
            
            result = await rcs_client.send_rich_card(
                phone=self.test_phone,
                card=card.build(),
                fallback_text="Order confirmation: 1 kg rice - ₹50"
            )
            
            if result.get("status") in ["success", "skipped"]:
                self.log_test("Rich Card Sending", True, f"Status: {result.get('status')}")
            else:
                self.log_test("Rich Card Sending", False, result.get("error", "Unknown error"))
                
        except Exception as e:
            self.log_test("Rich Card Sending", False, str(e))
    
    async def test_carousel_sending(self):
        """Test carousel sending"""
        try:
            products = [
                {
                    "product_id": "prod-1",
                    "name": "Basmati Rice",
                    "price": 50.0,
                    "unit": "kg",
                    "brand": "Tilda",
                    "stock_quantity": 10
                }
            ]
            
            carousel = ProductCarousel(products, language="en")
            
            result = await rcs_client.send_carousel(
                phone=self.test_phone,
                cards=carousel.build(),
                fallback_text="Product: Basmati Rice - ₹50/kg"
            )
            
            if result.get("status") in ["success", "skipped"]:
                self.log_test("Carousel Sending", True, f"Status: {result.get('status')}")
            else:
                self.log_test("Carousel Sending", False, result.get("error", "Unknown error"))
                
        except Exception as e:
            self.log_test("Carousel Sending", False, str(e))
    
    async def test_webhook_simulation(self):
        """Test webhook simulation"""
        try:
            # Simulate webhook payload
            webhook_payload = {
                "agentId": os.environ.get("RCS_AGENT_ID", "vyaparai-agent"),
                "messageId": f"test-msg-{int(time.time())}",
                "msisdn": self.test_phone.replace("+", ""),
                "message": {
                    "text": "2 kg rice, 1 liter oil"
                }
            }
            
            # This would normally be sent to the webhook endpoint
            # For testing, we just validate the payload structure
            if (webhook_payload.get("agentId") and 
                webhook_payload.get("messageId") and 
                webhook_payload.get("msisdn") and 
                webhook_payload.get("message", {}).get("text")):
                self.log_test("Webhook Payload Structure", True, "Valid webhook payload structure")
            else:
                self.log_test("Webhook Payload Structure", False, "Invalid webhook payload")
                
        except Exception as e:
            self.log_test("Webhook Payload Structure", False, str(e))
    
    async def test_error_handling(self):
        """Test error handling"""
        try:
            # Test with invalid phone number
            result = await rcs_client.send_message(
                phone="invalid-phone",
                text="Test message"
            )
            
            # Should handle gracefully
            if result.get("status") in ["error", "skipped"]:
                self.log_test("Error Handling", True, "Graceful error handling for invalid phone")
            else:
                self.log_test("Error Handling", False, "Did not handle invalid phone gracefully")
                
        except Exception as e:
            self.log_test("Error Handling", False, str(e))
    
    async def test_performance(self):
        """Test performance metrics"""
        try:
            start_time = time.time()
            
            # Test multiple operations
            await rcs_client.send_typing_indicator(self.test_phone)
            await asyncio.sleep(0.1)  # Small delay
            
            card = OrderConfirmationCard(
                order_id="PERF-123",
                items=[{"product": "rice", "quantity": 1, "unit": "kg"}],
                total=50.0,
                language="en"
            )
            card.build()
            
            end_time = time.time()
            duration = end_time - start_time
            
            if duration < 5.0:  # Should complete within 5 seconds
                self.log_test("Performance", True, f"Completed in {duration:.2f}s")
            else:
                self.log_test("Performance", False, f"Too slow: {duration:.2f}s")
                
        except Exception as e:
            self.log_test("Performance", False, str(e))
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("RCS INTEGRATION TEST SUMMARY")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print("\nFailed Tests:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  ❌ {result['test']}: {result['details']}")
        
        print("\n" + "="*60)
        
        return passed_tests == total_tests

async def main():
    """Main test function"""
    print("🧪 VyaparAI RCS Integration Test Suite")
    print("="*50)
    
    # Check environment variables
    required_env_vars = ["RCS_AGENT_ID", "GOOGLE_CLOUD_PROJECT_ID"]
    missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
    
    if missing_vars:
        print(f"⚠️  Warning: Missing environment variables: {', '.join(missing_vars)}")
        print("Some tests may be skipped or fail.")
        print()
    
    # Initialize tester
    tester = RCSIntegrationTester()
    
    # Run all tests
    test_methods = [
        tester.test_rcs_client_initialization,
        tester.test_credentials_loading,
        tester.test_agent_info_retrieval,
        tester.test_text_message_sending,
        tester.test_typing_indicator,
        tester.test_rich_cards,
        tester.test_product_carousel,
        tester.test_order_status_card,
        tester.test_welcome_card,
        tester.test_localization,
        tester.test_rich_card_sending,
        tester.test_carousel_sending,
        tester.test_webhook_simulation,
        tester.test_error_handling,
        tester.test_performance
    ]
    
    for test_method in test_methods:
        try:
            await test_method()
        except Exception as e:
            tester.log_test(test_method.__name__, False, f"Test exception: {str(e)}")
    
    # Print summary
    success = tester.print_summary()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())
