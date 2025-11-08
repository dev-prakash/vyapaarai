from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from decimal import Decimal
from typing import Optional, List

from app.services.payment_service import PaymentService, PaymentStatus

router = APIRouter()
payment_service = PaymentService()

class CreatePaymentRequest(BaseModel):
    order_id: str
    amount: Decimal
    customer_info: Optional[dict] = None

class ConfirmPaymentRequest(BaseModel):
    payment_id: str
    razorpay_payment_id: str
    razorpay_signature: str

class RefundRequest(BaseModel):
    amount: Optional[Decimal] = None
    reason: Optional[str] = None

class CalculateTotalRequest(BaseModel):
    items: List[dict]
    tax_rate: Optional[float] = 0.18
    delivery_fee: Optional[Decimal] = Decimal("50.00")

@router.post("/create")
async def create_payment(request: CreatePaymentRequest):
    """Create payment intent"""
    
    try:
        result = await payment_service.create_payment_intent(
            order_id=request.order_id,
            amount=request.amount,
            customer_info=request.customer_info
        )
        
        if result["success"]:
            return {
                "success": True,
                "payment_id": result["payment_id"],
                "amount": result["amount"],
                "currency": result["currency"],
                "status": result["status"],
                "gateway_response": result.get("gateway_response", {})
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Payment creation failed: {str(e)}")

@router.post("/confirm")
async def confirm_payment(request: ConfirmPaymentRequest):
    """Confirm and verify payment"""
    
    try:
        result = await payment_service.verify_payment(
            payment_id=request.payment_id,
            razorpay_payment_id=request.razorpay_payment_id,
            razorpay_signature=request.razorpay_signature
        )
        
        if result["success"]:
            return {
                "success": True,
                "status": result["status"],
                "payment_id": result["payment_id"]
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Payment confirmation failed: {str(e)}")

@router.get("/{payment_id}/status")
async def get_payment_status(payment_id: str):
    """Get payment status"""
    
    try:
        result = await payment_service.get_payment_status(payment_id)
        
        if result["success"]:
            return {
                "success": True,
                "payment_id": payment_id,
                "status": result["status"],
                "amount": result["amount"],
                "method": result["method"],
                "gateway_response": result.get("gateway_response", {})
            }
        else:
            raise HTTPException(status_code=404, detail=result["error"])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get payment status: {str(e)}")

@router.post("/{payment_id}/refund")
async def process_refund(payment_id: str, request: RefundRequest):
    """Process payment refund"""
    
    try:
        result = await payment_service.process_refund(
            payment_id=payment_id,
            amount=request.amount
        )
        
        if result["success"]:
            return {
                "success": True,
                "refund_id": result["refund_id"],
                "status": result["status"],
                "amount": result["amount"],
                "gateway_response": result.get("gateway_response", {})
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Refund failed: {str(e)}")

@router.get("/methods")
async def get_payment_methods():
    """Get available payment methods"""
    
    return payment_service.get_available_payment_methods()

@router.post("/calculate-total")
async def calculate_order_total(request: CalculateTotalRequest):
    """Calculate order total with tax and delivery"""
    
    try:
        result = await payment_service.calculate_order_total(
            items=request.items,
            tax_rate=request.tax_rate,
            delivery_fee=request.delivery_fee
        )
        
        if result["success"]:
            return {
                "success": True,
                "subtotal": result["subtotal"],
                "tax_amount": result["tax_amount"],
                "tax_rate": result["tax_rate"],
                "delivery_fee": result["delivery_fee"],
                "total": result["total"],
                "breakdown": result["breakdown"]
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate total: {str(e)}")

@router.post("/cod")
async def create_cod_payment(request: CreatePaymentRequest):
    """Create Cash on Delivery payment"""
    
    try:
        result = await payment_service.process_cod_payment(
            order_id=request.order_id,
            amount=request.amount
        )
        
        return {
            "success": True,
            "payment_id": result["payment_id"],
            "status": result["status"],
            "method": result["method"],
            "amount": result["amount"],
            "gateway_response": result.get("gateway_response", {})
        }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"COD payment creation failed: {str(e)}")
