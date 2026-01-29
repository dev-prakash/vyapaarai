import razorpay
import os
import json
from decimal import Decimal
from typing import Dict, Any, Optional
from enum import Enum

class PaymentStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed" 
    FAILED = "failed"
    REFUNDED = "refunded"

class PaymentMethod(Enum):
    UPI = "upi"
    CARD = "card"
    COD = "cod"
    WALLET = "wallet"

class PaymentService:
    def __init__(self):
        # Initialize Razorpay client with environment variables
        # For development, use test keys
        razorpay_key_id = os.getenv("RAZORPAY_KEY_ID", "rzp_test_placeholder")
        razorpay_key_secret = os.getenv("RAZORPAY_KEY_SECRET", "test_secret_placeholder")
        
        self.razorpay_client = razorpay.Client(
            auth=(razorpay_key_id, razorpay_key_secret)
        )
        
        # Mock mode for development/testing
        self.mock_mode = os.getenv("PAYMENT_MOCK_MODE", "true").lower() == "true"
    
    async def create_payment_intent(
        self, 
        order_id: str, 
        amount: Decimal, 
        currency: str = "INR",
        customer_info: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create payment intent with Razorpay"""
        
        try:
            # Convert amount to paise (smallest currency unit)
            amount_paise = int(amount * 100)
            
            payment_data = {
                "amount": amount_paise,
                "currency": currency,
                "receipt": f"order_{order_id}",
                "notes": {
                    "order_id": order_id,
                    "customer_name": customer_info.get("name", "") if customer_info else ""
                }
            }
            
            if self.mock_mode:
                # Return mock payment intent for development
                return {
                    "success": True,
                    "payment_id": f"mock_payment_{order_id}_{int(amount)}",
                    "amount": amount,
                    "currency": currency,
                    "status": PaymentStatus.PENDING.value,
                    "gateway_response": {
                        "id": f"mock_payment_{order_id}_{int(amount)}",
                        "amount": amount_paise,
                        "currency": currency,
                        "receipt": f"order_{order_id}",
                        "status": "created"
                    }
                }
            
            razorpay_order = self.razorpay_client.order.create(data=payment_data)
            
            return {
                "success": True,
                "payment_id": razorpay_order["id"],
                "amount": amount,
                "currency": currency,
                "status": PaymentStatus.PENDING.value,
                "gateway_response": razorpay_order
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Payment intent creation failed: {str(e)}",
                "status": PaymentStatus.FAILED.value
            }
    
    async def verify_payment(self, payment_id: str, razorpay_payment_id: str, razorpay_signature: str) -> Dict[str, Any]:
        """Verify payment signature from Razorpay"""
        
        try:
            if self.mock_mode:
                # Mock payment verification for development
                return {
                    "success": True,
                    "status": PaymentStatus.COMPLETED.value,
                    "payment_id": razorpay_payment_id or payment_id
                }
            
            # Verify payment signature
            params_dict = {
                'razorpay_order_id': payment_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            }
            
            self.razorpay_client.utility.verify_payment_signature(params_dict)
            
            return {
                "success": True,
                "status": PaymentStatus.COMPLETED.value,
                "payment_id": razorpay_payment_id
            }
            
        except razorpay.errors.SignatureVerificationError:
            return {
                "success": False,
                "error": "Payment signature verification failed",
                "status": PaymentStatus.FAILED.value
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Payment verification failed: {str(e)}",
                "status": PaymentStatus.FAILED.value
            }
    
    async def get_payment_status(self, payment_id: str) -> Dict[str, Any]:
        """Get payment status from Razorpay"""
        
        try:
            if self.mock_mode:
                # Mock payment status for development
                return {
                    "success": True,
                    "status": PaymentStatus.COMPLETED.value,
                    "amount": Decimal("150.00"),
                    "method": "upi",
                    "gateway_response": {
                        "id": payment_id,
                        "status": "captured",
                        "method": "upi",
                        "amount": 15000
                    }
                }
            
            payment = self.razorpay_client.payment.fetch(payment_id)
            
            status_mapping = {
                "created": PaymentStatus.PENDING.value,
                "authorized": PaymentStatus.PROCESSING.value,
                "captured": PaymentStatus.COMPLETED.value,
                "refunded": PaymentStatus.REFUNDED.value,
                "failed": PaymentStatus.FAILED.value
            }
            
            return {
                "success": True,
                "status": status_mapping.get(payment["status"], PaymentStatus.PENDING.value),
                "amount": Decimal(payment["amount"]) / 100,  # Convert from paise
                "method": payment.get("method", "unknown"),
                "gateway_response": payment
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get payment status: {str(e)}",
                "status": PaymentStatus.FAILED.value
            }
    
    async def process_cod_payment(self, order_id: str, amount: Decimal) -> Dict[str, Any]:
        """Handle Cash on Delivery payment"""
        
        return {
            "success": True,
            "payment_id": f"cod_{order_id}_{int(amount)}",
            "status": PaymentStatus.PENDING.value,  # Will be completed on delivery
            "method": PaymentMethod.COD.value,
            "amount": amount,
            "gateway_response": {
                "id": f"cod_{order_id}_{int(amount)}",
                "method": "cod",
                "status": "pending"
            }
        }
    
    async def process_refund(self, payment_id: str, amount: Optional[Decimal] = None) -> Dict[str, Any]:
        """Process refund through Razorpay"""
        
        try:
            if self.mock_mode:
                # Mock refund for development
                return {
                    "success": True,
                    "refund_id": f"mock_refund_{payment_id}",
                    "status": PaymentStatus.REFUNDED.value,
                    "amount": amount or Decimal("150.00"),
                    "gateway_response": {
                        "id": f"mock_refund_{payment_id}",
                        "payment_id": payment_id,
                        "amount": int((amount or Decimal("150.00")) * 100)
                    }
                }
            
            refund_data = {}
            if amount:
                refund_data["amount"] = int(amount * 100)  # Convert to paise
            
            refund = self.razorpay_client.payment.refund(payment_id, refund_data)
            
            return {
                "success": True,
                "refund_id": refund["id"],
                "status": PaymentStatus.REFUNDED.value,
                "amount": Decimal(refund["amount"]) / 100,
                "gateway_response": refund
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Refund failed: {str(e)}"
            }
    
    def get_available_payment_methods(self) -> Dict[str, Any]:
        """Get list of available payment methods"""
        
        return {
            "methods": [
                {
                    "id": PaymentMethod.UPI.value,
                    "name": "UPI",
                    "description": "Pay using UPI (Google Pay, PhonePe, Paytm)",
                    "enabled": True,
                    "icon": "upi-icon"
                },
                {
                    "id": PaymentMethod.CARD.value,
                    "name": "Card",
                    "description": "Debit/Credit Card",
                    "enabled": True,
                    "icon": "card-icon"
                },
                {
                    "id": PaymentMethod.COD.value,
                    "name": "Cash on Delivery",
                    "description": "Pay when order is delivered",
                    "enabled": True,
                    "icon": "cod-icon"
                },
                {
                    "id": PaymentMethod.WALLET.value,
                    "name": "Wallet",
                    "description": "Paytm, Mobikwik, etc.",
                    "enabled": True,
                    "icon": "wallet-icon"
                }
            ]
        }
    
    async def calculate_order_total(self, items: list, tax_rate: float = 0.18, delivery_fee: Decimal = Decimal("50.00")) -> Dict[str, Any]:
        """Calculate order total with tax and delivery"""
        
        try:
            subtotal = sum(Decimal(str(item.get("price", 0))) * Decimal(str(item.get("quantity", 1))) for item in items)
            tax_amount = subtotal * Decimal(str(tax_rate))
            total = subtotal + tax_amount + delivery_fee
            
            return {
                "success": True,
                "subtotal": subtotal,
                "tax_amount": tax_amount,
                "tax_rate": tax_rate,
                "delivery_fee": delivery_fee,
                "total": total,
                "breakdown": {
                    "items": items,
                    "subtotal": float(subtotal),
                    "tax": float(tax_amount),
                    "delivery": float(delivery_fee),
                    "total": float(total)
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to calculate order total: {str(e)}"
            }
