#!/usr/bin/env python3
"""
VyaparAI Real-Time Features Verification Script
Tests actual vs simulated real-time functionality
"""

import asyncio
import requests
import time
import json
from datetime import datetime
from typing import Dict, List, Any

class RealTimeVerification:
    def __init__(self):
        self.api_url = "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws"
        self.results = {
            'websocket_test': False,
            'polling_test': False,
            'order_updates': False,
            'frontend_implementation': 'unknown',
            'backend_websocket': False,
            'recommendations': []
        }
        
    def test_websocket_connection(self) -> bool:
        """Test if WebSocket connection works"""
        print("🔌 Testing WebSocket connection...")
        
        try:
            # Try to connect to WebSocket endpoint
            response = requests.get(f"{self.api_url}/socket.io/", timeout=5)
            print(f"✅ WebSocket endpoint responds: {response.status_code}")
            self.results['websocket_test'] = True
            return True
        except requests.exceptions.RequestException as e:
            print(f"❌ WebSocket connection failed: {e}")
            self.results['websocket_test'] = False
            return False
    
    def test_polling_simulation(self) -> bool:
        """Test if real-time is actually just polling"""
        print("\n🔄 Testing polling simulation...")
        
        try:
            # Get initial orders
            print("Getting initial orders...")
            response1 = requests.get(f"{self.api_url}/api/v1/orders", timeout=10)
            if response1.status_code != 200:
                print(f"❌ Failed to get initial orders: {response1.status_code}")
                return False
                
            initial_data = response1.json()
            initial_count = len(initial_data.get('data', []))
            print(f"Initial order count: {initial_count}")
            
            # Create new order
            print("Creating test order...")
            new_order_data = {
                "customer_name": "Real-Time Test Customer",
                "customer_phone": "+919876543210",
                "items": [
                    {
                        "name": "Test Item for Real-Time",
                        "quantity": 1,
                        "price": 100
                    }
                ]
            }
            
            create_response = requests.post(
                f"{self.api_url}/api/v1/orders/test/generate-order",
                json=new_order_data,
                timeout=10
            )
            
            if create_response.status_code != 200:
                print(f"❌ Failed to create test order: {create_response.status_code}")
                return False
                
            print("✅ Test order created successfully")
            
            # Wait a moment for order to be processed
            time.sleep(2)
            
            # Check if orders list updates
            print("Checking if orders list updates...")
            response2 = requests.get(f"{self.api_url}/api/v1/orders", timeout=10)
            if response2.status_code != 200:
                print(f"❌ Failed to get updated orders: {response2.status_code}")
                return False
                
            updated_data = response2.json()
            new_count = len(updated_data.get('data', []))
            print(f"Updated order count: {new_count}")
            
            if new_count > initial_count:
                print("✅ Orders update immediately (real-time or good API)")
                self.results['polling_test'] = True
                return True
            else:
                print("❌ Orders don't update automatically (need manual refresh)")
                self.results['polling_test'] = False
                return False
                
        except Exception as e:
            print(f"❌ Polling test failed: {e}")
            self.results['polling_test'] = False
            return False
    
    def check_frontend_implementation(self) -> str:
        """Check if frontend uses polling for updates"""
        print("\n🔍 Checking frontend implementation...")
        
        try:
            # Check useWebSocket hook
            websocket_file = "frontend-pwa/src/hooks/useWebSocket.ts"
            with open(websocket_file, 'r') as f:
                content = f.read()
                
            if "isLambdaBackend" in content and "return mock interface" in content:
                print("🔄 Frontend uses polling for Lambda backend")
                self.results['frontend_implementation'] = 'polling'
                return 'polling'
            elif "setInterval" in content and "polling" in content:
                print("🔄 Frontend uses polling")
                self.results['frontend_implementation'] = 'polling'
                return 'polling'
            elif "WebSocket" in content or "socket.io" in content:
                print("⚡ Frontend has WebSocket implementation")
                self.results['frontend_implementation'] = 'websocket'
                return 'websocket'
            else:
                print("❓ Frontend real-time mechanism unclear")
                self.results['frontend_implementation'] = 'unknown'
                return 'unknown'
                
        except FileNotFoundError:
            print("❌ WebSocket service file not found")
            self.results['frontend_implementation'] = 'not_found'
            return 'not_found'
        except Exception as e:
            print(f"❌ Error checking frontend: {e}")
            self.results['frontend_implementation'] = 'error'
            return 'error'
    
    def check_backend_websocket_support(self) -> bool:
        """Check if backend has WebSocket support"""
        print("\n🔧 Checking backend WebSocket support...")
        
        try:
            # Check main.py for WebSocket imports
            main_file = "backend/app/main.py"
            with open(main_file, 'r') as f:
                content = f.read()
                
            if "socketio" in content or "websocket" in content:
                print("⚡ Backend has WebSocket support")
                self.results['backend_websocket'] = True
                return True
            else:
                print("❌ Backend has no WebSocket support")
                self.results['backend_websocket'] = False
                return False
                
        except FileNotFoundError:
            print("❌ Backend main.py not found")
            self.results['backend_websocket'] = False
            return False
        except Exception as e:
            print(f"❌ Error checking backend: {e}")
            self.results['backend_websocket'] = False
            return False
    
    def test_order_updates(self) -> bool:
        """Test if order updates work in real-time"""
        print("\n📦 Testing order updates...")
        
        try:
            # Get orders
            response = requests.get(f"{self.api_url}/api/v1/orders", timeout=10)
            if response.status_code != 200:
                print(f"❌ Failed to get orders: {response.status_code}")
                return False
                
            orders = response.json().get('data', [])
            if not orders:
                print("⚠️ No orders to test updates")
                return False
                
            # Test updating first order
            first_order = orders[0]
            order_id = first_order.get('id')
            
            if not order_id:
                print("⚠️ Order has no ID")
                return False
                
            print(f"Testing update for order: {order_id}")
            
            # Try to update order status (if endpoint exists)
            update_data = {
                "status": "processing",
                "updated_at": datetime.now().isoformat()
            }
            
            # Note: This endpoint might not exist in the current implementation
            update_response = requests.put(
                f"{self.api_url}/api/v1/orders/{order_id}",
                json=update_data,
                timeout=10
            )
            
            if update_response.status_code == 200:
                print("✅ Order updates work")
                self.results['order_updates'] = True
                return True
            elif update_response.status_code == 404:
                print("⚠️ Order update endpoint not implemented")
                self.results['order_updates'] = False
                return False
            else:
                print(f"⚠️ Order update returned: {update_response.status_code}")
                self.results['order_updates'] = False
                return False
                
        except Exception as e:
            print(f"❌ Order update test failed: {e}")
            self.results['order_updates'] = False
            return False
    
    def generate_recommendations(self) -> List[str]:
        """Provide recommendations based on findings"""
        print("\n📋 Generating recommendations...")
        
        recommendations = []
        
        if not self.results['websocket_test']:
            recommendations.append("WebSocket not supported on Lambda - use polling instead")
            
        if not self.results['backend_websocket']:
            recommendations.append("Backend has no WebSocket implementation")
            
        if self.results['frontend_implementation'] == 'polling':
            recommendations.append("Frontend correctly uses polling for Lambda backend")
            
        if not self.results['order_updates']:
            recommendations.append("Order update endpoints need implementation")
            
        # General recommendations
        recommendations.append("For grocery stores, 10-30 second polling is usually sufficient")
        recommendations.append("Real-time WebSocket only needed for high-frequency updates")
        recommendations.append("Consider upgrading to EC2 if true real-time is required")
        
        self.results['recommendations'] = recommendations
        return recommendations
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'api_url': self.api_url,
            'results': self.results,
            'summary': {
                'websocket_working': self.results['websocket_test'],
                'polling_working': self.results['polling_test'],
                'frontend_implementation': self.results['frontend_implementation'],
                'backend_websocket': self.results['backend_websocket'],
                'order_updates': self.results['order_updates']
            },
            'recommendations': self.results['recommendations']
        }
        
        # Save report
        with open('realtime-verification-report.json', 'w') as f:
            json.dump(report, f, indent=2)
            
        return report
    
    def print_summary(self):
        """Print summary of findings"""
        print("\n" + "="*50)
        print("📊 REAL-TIME VERIFICATION SUMMARY")
        print("="*50)
        
        print(f"WebSocket Support: {'✅ Working' if self.results['websocket_test'] else '❌ Not Working'}")
        print(f"Polling Updates: {'✅ Working' if self.results['polling_test'] else '❌ Not Working'}")
        print(f"Frontend Implementation: {self.results['frontend_implementation'].upper()}")
        print(f"Backend WebSocket: {'✅ Available' if self.results['backend_websocket'] else '❌ Not Available'}")
        print(f"Order Updates: {'✅ Working' if self.results['order_updates'] else '❌ Not Working'}")
        
        print("\n🎯 RECOMMENDATIONS:")
        for rec in self.results['recommendations']:
            print(f"  • {rec}")
        
        print(f"\n📄 Detailed report saved to: realtime-verification-report.json")

async def main():
    verifier = RealTimeVerification()
    
    print("🔍 VERIFYING VYAPARAI REAL-TIME FEATURES")
    print("=" * 50)
    
    # Run all tests
    verifier.test_websocket_connection()
    verifier.test_polling_simulation()
    verifier.check_frontend_implementation()
    verifier.check_backend_websocket_support()
    verifier.test_order_updates()
    verifier.generate_recommendations()
    
    # Generate and print report
    report = verifier.generate_report()
    verifier.print_summary()
    
    return report

if __name__ == "__main__":
    asyncio.run(main())
