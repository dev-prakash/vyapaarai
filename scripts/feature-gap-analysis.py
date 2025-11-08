#!/usr/bin/env python3
"""
VyaparAI Feature Gap Analysis Script
Tests complete order workflow and identifies missing critical features
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Any

class FeatureGapAnalysis:
    def __init__(self):
        self.api_url = "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws"
        self.gaps = {
            "critical": [],
            "important": [],
            "nice_to_have": []
        }
        self.test_results = {
            "order_workflow": {},
            "ai_processing": {},
            "customer_management": {},
            "payment_integration": {},
            "frontend_features": {},
            "mobile_experience": {}
        }
    
    def test_order_workflow(self):
        """Test complete order creation to completion workflow"""
        print("🛒 Testing complete order workflow...")
        
        workflow_steps = [
            ("Create Order", "POST", "/api/v1/orders/test/generate-order", {
                "customer_name": "Test Customer",
                "customer_phone": "+919876543210",
                "items": [{"name": "Basmati Rice", "quantity": "1 kg", "price": 150}],
                "delivery_address": "123 Test Street, Mumbai"
            }),
            ("List Orders", "GET", "/api/v1/orders", None),
            ("Get Order Details", "GET", "/api/v1/orders/{order_id}", None),
            ("Update Order Status", "PUT", "/api/v1/orders/{order_id}/status", {"status": "processing"}),
            ("Complete Order", "PUT", "/api/v1/orders/{order_id}/status", {"status": "completed"})
        ]
        
        order_id = None
        workflow_status = {}
        
        for step_name, method, endpoint, data in workflow_steps:
            try:
                if "{order_id}" in endpoint and order_id:
                    endpoint = endpoint.replace("{order_id}", order_id)
                elif "{order_id}" in endpoint and not order_id:
                    print(f"⏭️  Skipping {step_name} - no order_id available")
                    workflow_status[step_name] = {"status": "skipped", "reason": "no_order_id"}
                    continue
                
                if method == "POST":
                    response = requests.post(f"{self.api_url}{endpoint}", json=data, timeout=10)
                elif method == "PUT":
                    response = requests.put(f"{self.api_url}{endpoint}", json=data, timeout=10)
                else:
                    response = requests.get(f"{self.api_url}{endpoint}", timeout=10)
                
                if response.status_code in [200, 201]:
                    print(f"✅ {step_name}: Working")
                    workflow_status[step_name] = {"status": "working", "response_code": response.status_code}
                    
                    # Extract order_id from create order response
                    if step_name == "Create Order":
                        response_data = response.json()
                        if isinstance(response_data, dict) and response_data.get("id"):
                            order_id = response_data["id"]
                            print(f"📦 Order created with ID: {order_id}")
                        elif isinstance(response_data, list) and len(response_data) > 0:
                            order_id = response_data[0].get("id")
                            print(f"📦 Order ID extracted: {order_id}")
                            
                else:
                    print(f"❌ {step_name}: Failed ({response.status_code})")
                    workflow_status[step_name] = {"status": "failed", "response_code": response.status_code}
                    self.gaps["critical"].append(f"{step_name} endpoint not working properly")
                    
            except Exception as e:
                print(f"❌ {step_name}: Error - {e}")
                workflow_status[step_name] = {"status": "error", "error": str(e)}
                self.gaps["critical"].append(f"{step_name} functionality missing")
        
        self.test_results["order_workflow"] = workflow_status
        return order_id
    
    def test_ai_processing(self):
        """Test AI processing for Indian languages"""
        print("\n🤖 Testing AI/NLP processing...")
        
        test_messages = [
            "मुझे 1 किलो बासमती चावल चाहिए",  # Hindi
            "I need 1 kg basmati rice",  # English
            "1 kg चावल और 500g दाल चाहिए",  # Hinglish
            "2 kg potatoes, 1 kg onions",  # English grocery terms
            "दूध 1 लीटर और ब्रेड 1 पैकेट",  # Hindi grocery terms
        ]
        
        ai_status = {}
        
        for i, message in enumerate(test_messages):
            try:
                # Test with order processing endpoint
                response = requests.post(f"{self.api_url}/api/v1/orders/test/generate-order", 
                                       json={
                                           "customer_name": f"AI Test Customer {i+1}",
                                           "customer_phone": "+919876543210",
                                           "message": message,
                                           "items": [{"name": "Test Item", "quantity": "1", "price": 100}]
                                       }, timeout=10)
                
                if response.status_code == 200:
                    print(f"✅ AI Processing: {message[:30]}...")
                    ai_status[f"test_{i+1}"] = {"status": "working", "message": message[:30]}
                else:
                    print(f"❌ AI Processing failed for: {message[:30]}...")
                    ai_status[f"test_{i+1}"] = {"status": "failed", "message": message[:30]}
                    self.gaps["critical"].append("AI processing not working for multilingual input")
                    
            except Exception as e:
                print(f"❌ AI Processing error for: {message[:30]}... - {e}")
                ai_status[f"test_{i+1}"] = {"status": "error", "message": message[:30], "error": str(e)}
                self.gaps["critical"].append("AI processing endpoint missing or broken")
        
        self.test_results["ai_processing"] = ai_status
    
    def test_customer_management(self):
        """Test customer management functionality"""
        print("\n👥 Testing customer management...")
        
        customer_endpoints = [
            ("List Customers", "GET", "/api/v1/customers", None),
            ("Create Customer", "POST", "/api/v1/customers", {
                "name": "Test Customer",
                "phone": "+919876543210",
                "address": "Test Address"
            }),
            ("Customer Profile", "GET", "/api/v1/customers/{customer_id}", None),
            ("Customer Orders", "GET", "/api/v1/customers/{customer_id}/orders", None),
            ("Update Customer", "PUT", "/api/v1/customers/{customer_id}", {
                "name": "Updated Customer",
                "address": "Updated Address"
            })
        ]
        
        customer_status = {}
        
        for endpoint_name, method, endpoint, data in customer_endpoints:
            try:
                if method == "POST":
                    response = requests.post(f"{self.api_url}{endpoint}", json=data, timeout=10)
                elif method == "PUT":
                    response = requests.put(f"{self.api_url}{endpoint}", json=data, timeout=10)
                else:
                    response = requests.get(f"{self.api_url}{endpoint}", timeout=10)
                
                if response.status_code in [200, 201]:
                    print(f"✅ {endpoint_name}: Available")
                    customer_status[endpoint_name] = {"status": "available", "response_code": response.status_code}
                elif response.status_code == 404:
                    print(f"❌ {endpoint_name}: Not implemented")
                    customer_status[endpoint_name] = {"status": "not_implemented", "response_code": 404}
                    self.gaps["important"].append(f"{endpoint_name} needs implementation")
                else:
                    print(f"⚠️ {endpoint_name}: Unexpected response ({response.status_code})")
                    customer_status[endpoint_name] = {"status": "unexpected", "response_code": response.status_code}
                    
            except Exception as e:
                print(f"❌ {endpoint_name}: Error - {e}")
                customer_status[endpoint_name] = {"status": "error", "error": str(e)}
                self.gaps["important"].append(f"{endpoint_name} missing")
        
        self.test_results["customer_management"] = customer_status
    
    def test_payment_integration(self):
        """Test payment processing"""
        print("\n💳 Testing payment integration...")
        
        payment_tests = [
            ("Payment Methods", "GET", "/api/v1/payments/methods", None),
            ("Process Payment", "POST", "/api/v1/payments/process", {
                "order_id": "test_order",
                "amount": 100,
                "method": "upi"
            }),
            ("Payment Status", "GET", "/api/v1/payments/{payment_id}/status", None),
            ("Payment History", "GET", "/api/v1/payments/history", None),
            ("Refund Payment", "POST", "/api/v1/payments/refund", {
                "payment_id": "test_payment",
                "amount": 50,
                "reason": "Customer request"
            })
        ]
        
        payment_status = {}
        
        for test_name, method, endpoint, data in payment_tests:
            try:
                if method == "POST":
                    response = requests.post(f"{self.api_url}{endpoint}", json=data, timeout=10)
                else:
                    response = requests.get(f"{self.api_url}{endpoint}", timeout=10)
                
                if response.status_code == 404:
                    print(f"❌ {test_name}: Not implemented")
                    payment_status[test_name] = {"status": "not_implemented", "response_code": 404}
                    self.gaps["critical"].append(f"Payment system not implemented - {test_name}")
                elif response.status_code in [200, 201]:
                    print(f"✅ {test_name}: Available")
                    payment_status[test_name] = {"status": "available", "response_code": response.status_code}
                else:
                    print(f"⚠️ {test_name}: Unexpected response ({response.status_code})")
                    payment_status[test_name] = {"status": "unexpected", "response_code": response.status_code}
                    
            except Exception as e:
                print(f"❌ {test_name}: Error - {e}")
                payment_status[test_name] = {"status": "error", "error": str(e)}
                self.gaps["critical"].append(f"Payment system error - {test_name}")
        
        self.test_results["payment_integration"] = payment_status
    
    def test_inventory_management(self):
        """Test inventory management functionality"""
        print("\n📦 Testing inventory management...")
        
        inventory_tests = [
            ("List Products", "GET", "/api/v1/inventory/products", None),
            ("Add Product", "POST", "/api/v1/inventory/products", {
                "name": "Test Product",
                "category": "groceries",
                "price": 100,
                "stock": 50
            }),
            ("Update Stock", "PUT", "/api/v1/inventory/products/{product_id}/stock", {
                "quantity": 25,
                "operation": "add"
            }),
            ("Low Stock Alerts", "GET", "/api/v1/inventory/alerts", None),
            ("Product Categories", "GET", "/api/v1/inventory/categories", None)
        ]
        
        inventory_status = {}
        
        for test_name, method, endpoint, data in inventory_tests:
            try:
                if method == "POST":
                    response = requests.post(f"{self.api_url}{endpoint}", json=data, timeout=10)
                elif method == "PUT":
                    response = requests.put(f"{self.api_url}{endpoint}", json=data, timeout=10)
                else:
                    response = requests.get(f"{self.api_url}{endpoint}", timeout=10)
                
                if response.status_code == 404:
                    print(f"❌ {test_name}: Not implemented")
                    inventory_status[test_name] = {"status": "not_implemented", "response_code": 404}
                    self.gaps["important"].append(f"Inventory management not implemented - {test_name}")
                elif response.status_code in [200, 201]:
                    print(f"✅ {test_name}: Available")
                    inventory_status[test_name] = {"status": "available", "response_code": response.status_code}
                else:
                    print(f"⚠️ {test_name}: Unexpected response ({response.status_code})")
                    inventory_status[test_name] = {"status": "unexpected", "response_code": response.status_code}
                    
            except Exception as e:
                print(f"❌ {test_name}: Error - {e}")
                inventory_status[test_name] = {"status": "error", "error": str(e)}
                self.gaps["important"].append(f"Inventory management error - {test_name}")
        
        self.test_results["inventory_management"] = inventory_status
    
    def test_notification_system(self):
        """Test notification system"""
        print("\n📱 Testing notification system...")
        
        notification_tests = [
            ("Send SMS", "POST", "/api/v1/notifications/sms", {
                "phone": "+919876543210",
                "message": "Test SMS notification"
            }),
            ("Send WhatsApp", "POST", "/api/v1/notifications/whatsapp", {
                "phone": "+919876543210",
                "message": "Test WhatsApp notification"
            }),
            ("Send Email", "POST", "/api/v1/notifications/email", {
                "email": "test@example.com",
                "subject": "Test Email",
                "message": "Test email notification"
            }),
            ("Notification Templates", "GET", "/api/v1/notifications/templates", None),
            ("Notification History", "GET", "/api/v1/notifications/history", None)
        ]
        
        notification_status = {}
        
        for test_name, method, endpoint, data in notification_tests:
            try:
                if method == "POST":
                    response = requests.post(f"{self.api_url}{endpoint}", json=data, timeout=10)
                else:
                    response = requests.get(f"{self.api_url}{endpoint}", timeout=10)
                
                if response.status_code == 404:
                    print(f"❌ {test_name}: Not implemented")
                    notification_status[test_name] = {"status": "not_implemented", "response_code": 404}
                    self.gaps["important"].append(f"Notification system not implemented - {test_name}")
                elif response.status_code in [200, 201]:
                    print(f"✅ {test_name}: Available")
                    notification_status[test_name] = {"status": "available", "response_code": response.status_code}
                else:
                    print(f"⚠️ {test_name}: Unexpected response ({response.status_code})")
                    notification_status[test_name] = {"status": "unexpected", "response_code": response.status_code}
                    
            except Exception as e:
                print(f"❌ {test_name}: Error - {e}")
                notification_status[test_name] = {"status": "error", "error": str(e)}
                self.gaps["important"].append(f"Notification system error - {test_name}")
        
        self.test_results["notification_system"] = notification_status
    
    def analyze_frontend_features(self):
        """Analyze frontend feature completeness"""
        print("\n🖥️ Analyzing frontend features...")
        
        frontend_features = {
            "order_creation": {
                "status": "implemented",
                "description": "Order creation form exists",
                "priority": "critical"
            },
            "order_management": {
                "status": "implemented", 
                "description": "Live order feed with polling",
                "priority": "critical"
            },
            "customer_management": {
                "status": "missing",
                "description": "Customer profile management interface",
                "priority": "important"
            },
            "payment_processing": {
                "status": "missing",
                "description": "Payment processing UI",
                "priority": "critical"
            },
            "inventory_management": {
                "status": "missing",
                "description": "Inventory management interface",
                "priority": "important"
            },
            "mobile_responsiveness": {
                "status": "implemented",
                "description": "PWA with mobile optimization",
                "priority": "critical"
            },
            "offline_capabilities": {
                "status": "partial",
                "description": "Basic offline support, needs enhancement",
                "priority": "important"
            },
            "push_notifications": {
                "status": "missing",
                "description": "Push notification system",
                "priority": "important"
            }
        }
        
        self.test_results["frontend_features"] = frontend_features
        
        # Add gaps based on frontend analysis
        for feature, details in frontend_features.items():
            if details["status"] == "missing":
                self.gaps[details["priority"]].append(f"Frontend: {details['description']}")
            elif details["status"] == "partial":
                self.gaps["important"].append(f"Frontend: {details['description']} - needs enhancement")
    
    def generate_report(self):
        """Generate comprehensive feature gap report"""
        report = {
            "analysis_date": datetime.now().isoformat(),
            "api_url": self.api_url,
            "test_results": self.test_results,
            "gaps": self.gaps,
            "summary": {
                "critical_gaps_count": len(self.gaps["critical"]),
                "important_gaps_count": len(self.gaps["important"]),
                "nice_to_have_count": len(self.gaps["nice_to_have"]),
                "overall_readiness": "not_ready" if len(self.gaps["critical"]) > 0 else "ready"
            },
            "recommendations": [],
            "implementation_priority": [],
            "customer_readiness_assessment": {}
        }
        
        # Generate recommendations
        if len(self.gaps["critical"]) > 0:
            report["recommendations"].append("❌ Address all critical gaps before first customer")
            report["recommendations"].append("🔧 Focus on core order workflow and payment integration")
        else:
            report["recommendations"].append("✅ Core functionality ready for first customer")
        
        if len(self.gaps["important"]) > 0:
            report["recommendations"].append("📈 Implement important features for better customer experience")
        
        report["recommendations"].append("🤖 AI processing needs validation with real grocery terms")
        report["recommendations"].append("📱 Mobile experience is critical for Indian market")
        
        # Implementation priority
        priority_order = [
            "Complete order workflow (create, update, complete, cancel)",
            "Payment processing integration (UPI, cards, cash)",
            "AI/NLP processing for Indian languages and grocery terms",
            "Customer management system (profiles, history)",
            "Inventory management (stock tracking, alerts)",
            "Notification system (SMS, WhatsApp, email)",
            "Mobile app features (offline, push notifications)",
            "Analytics and reporting dashboard"
        ]
        
        report["implementation_priority"] = priority_order
        
        # Customer readiness assessment
        readiness_score = 0
        total_features = 0
        
        for category, features in self.test_results.items():
            if isinstance(features, dict):
                for feature, details in features.items():
                    total_features += 1
                    if isinstance(details, dict) and details.get("status") in ["working", "available", "implemented"]:
                        readiness_score += 1
        
        readiness_percentage = (readiness_score / total_features * 100) if total_features > 0 else 0
        
        report["customer_readiness_assessment"] = {
            "readiness_score": readiness_score,
            "total_features": total_features,
            "readiness_percentage": round(readiness_percentage, 2),
            "status": "ready" if readiness_percentage >= 80 else "needs_work" if readiness_percentage >= 60 else "not_ready",
            "critical_blockers": len(self.gaps["critical"]),
            "estimated_development_time": f"{len(self.gaps['critical']) * 2 + len(self.gaps['important']) * 1} weeks"
        }
        
        return report

def main():
    analyzer = FeatureGapAnalysis()
    
    print("🔍 VYAPARAI FEATURE GAP ANALYSIS")
    print("=" * 50)
    print("Testing complete functionality for customer readiness...")
    print()
    
    # Run all tests
    order_id = analyzer.test_order_workflow()
    analyzer.test_ai_processing()
    analyzer.test_customer_management()
    analyzer.test_payment_integration()
    analyzer.test_inventory_management()
    analyzer.test_notification_system()
    analyzer.analyze_frontend_features()
    
    # Generate report
    report = analyzer.generate_report()
    
    # Print summary
    print(f"\n📊 ANALYSIS RESULTS")
    print("=" * 50)
    print(f"Critical gaps: {report['summary']['critical_gaps_count']}")
    print(f"Important gaps: {report['summary']['important_gaps_count']}")
    print(f"Nice to have: {report['summary']['nice_to_have_count']}")
    print(f"Overall readiness: {report['summary']['overall_readiness']}")
    print(f"Customer readiness: {report['customer_readiness_assessment']['readiness_percentage']}%")
    print(f"Estimated development time: {report['customer_readiness_assessment']['estimated_development_time']}")
    
    if report['gaps']['critical']:
        print(f"\n🚨 CRITICAL GAPS (Must fix before first customer):")
        for gap in report['gaps']['critical']:
            print(f"  • {gap}")
    
    if report['gaps']['important']:
        print(f"\n📈 IMPORTANT GAPS (Should implement for growth):")
        for gap in report['gaps']['important']:
            print(f"  • {gap}")
    
    # Save detailed report
    with open('feature-gap-report.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Detailed report saved to: feature-gap-report.json")
    
    return report

if __name__ == "__main__":
    main()
