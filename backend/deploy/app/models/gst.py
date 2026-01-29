"""
GST Models for VyapaarAI
Pydantic models for GST calculations, API requests/responses

Author: DevPrakash
"""

from decimal import Decimal
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class GSTRateEnum(str, Enum):
    """Valid GST rate slabs in India"""
    ZERO = "0"
    FIVE = "5"
    TWELVE = "12"
    EIGHTEEN = "18"
    TWENTY_EIGHT = "28"


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class ItemGSTBreakdown(BaseModel):
    """GST breakdown for a single item in an order"""

    # Product info
    product_id: str = Field(..., description="Product identifier")
    product_name: str = Field(default="", description="Product name")
    quantity: int = Field(..., ge=1, description="Quantity ordered")
    unit_price: Decimal = Field(..., ge=0, description="Unit price before tax")

    # Taxable amount
    taxable_amount: Decimal = Field(
        ...,
        ge=0,
        description="Price x Quantity before tax"
    )

    # GST rates and amounts
    gst_rate: Decimal = Field(
        ...,
        ge=0,
        le=28,
        description="Total GST rate (e.g., 18)"
    )
    cgst_rate: Decimal = Field(
        ...,
        ge=0,
        description="Central GST rate (half of GST for intra-state)"
    )
    cgst_amount: Decimal = Field(
        ...,
        ge=0,
        description="Central GST amount"
    )
    sgst_rate: Decimal = Field(
        ...,
        ge=0,
        description="State GST rate (half of GST for intra-state)"
    )
    sgst_amount: Decimal = Field(
        ...,
        ge=0,
        description="State GST amount"
    )
    igst_rate: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Integrated GST rate (for inter-state)"
    )
    igst_amount: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Integrated GST amount"
    )

    # Cess (for luxury items like aerated drinks, tobacco)
    cess_rate: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Cess rate (applicable on luxury/sin goods)"
    )
    cess_amount: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Cess amount"
    )

    # Totals
    total_tax: Decimal = Field(
        ...,
        ge=0,
        description="Total tax (CGST + SGST or IGST + Cess)"
    )
    total_amount: Decimal = Field(
        ...,
        ge=0,
        description="Taxable amount + Total tax"
    )

    # Metadata
    hsn_code: Optional[str] = Field(
        default=None,
        description="HSN code for the product"
    )
    gst_category: Optional[str] = Field(
        default=None,
        description="GST category code"
    )
    is_exempt: bool = Field(
        default=False,
        description="Whether item is GST exempt"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "product_id": "PROD-001",
                "product_name": "Tata Tea Gold 500g",
                "quantity": 2,
                "unit_price": "250.00",
                "taxable_amount": "500.00",
                "gst_rate": "5",
                "cgst_rate": "2.5",
                "cgst_amount": "12.50",
                "sgst_rate": "2.5",
                "sgst_amount": "12.50",
                "igst_rate": "0",
                "igst_amount": "0",
                "cess_rate": "0",
                "cess_amount": "0",
                "total_tax": "25.00",
                "total_amount": "525.00",
                "hsn_code": "0902",
                "gst_category": "TEA",
                "is_exempt": False
            }
        }
    }


class RateWiseSummary(BaseModel):
    """Summary of taxes grouped by GST rate (for invoice/filing)"""

    gst_rate: Decimal = Field(
        ...,
        description="GST rate slab"
    )
    taxable_amount: Decimal = Field(
        ...,
        ge=0,
        description="Total taxable amount at this rate"
    )
    cgst_amount: Decimal = Field(
        ...,
        ge=0,
        description="Total CGST at this rate"
    )
    sgst_amount: Decimal = Field(
        ...,
        ge=0,
        description="Total SGST at this rate"
    )
    igst_amount: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Total IGST at this rate (inter-state)"
    )
    cess_amount: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Total cess at this rate"
    )
    total_tax: Decimal = Field(
        ...,
        ge=0,
        description="Total tax at this rate"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "gst_rate": "18",
                "taxable_amount": "1000.00",
                "cgst_amount": "90.00",
                "sgst_amount": "90.00",
                "igst_amount": "0",
                "cess_amount": "0",
                "total_tax": "180.00"
            }
        }
    }


class OrderGSTSummary(BaseModel):
    """Complete GST summary for an order"""

    # Identifiers
    order_id: str = Field(
        default="",
        description="Order identifier"
    )
    store_id: str = Field(
        ...,
        description="Store identifier"
    )

    # Totals
    subtotal: Decimal = Field(
        ...,
        ge=0,
        description="Sum of all taxable amounts (before tax)"
    )
    cgst_total: Decimal = Field(
        ...,
        ge=0,
        description="Total Central GST"
    )
    sgst_total: Decimal = Field(
        ...,
        ge=0,
        description="Total State GST"
    )
    igst_total: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Total Integrated GST (inter-state)"
    )
    cess_total: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Total Cess"
    )
    tax_total: Decimal = Field(
        ...,
        ge=0,
        description="Total tax amount (all components)"
    )
    grand_total: Decimal = Field(
        ...,
        ge=0,
        description="Subtotal + Total tax"
    )

    # State information (for IGST determination)
    is_inter_state: bool = Field(
        default=False,
        description="True if inter-state supply (use IGST)"
    )
    supply_state: Optional[str] = Field(
        default=None,
        description="State of supply (seller location)"
    )
    billing_state: Optional[str] = Field(
        default=None,
        description="State of billing (buyer location)"
    )

    # Breakdowns
    item_breakdowns: List[ItemGSTBreakdown] = Field(
        default_factory=list,
        description="GST breakdown for each item"
    )
    rate_wise_summary: List[RateWiseSummary] = Field(
        default_factory=list,
        description="Tax summary grouped by rate (for filing)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "order_id": "ORD-2024-001",
                "store_id": "STR-001",
                "subtotal": "1500.00",
                "cgst_total": "67.50",
                "sgst_total": "67.50",
                "igst_total": "0",
                "cess_total": "0",
                "tax_total": "135.00",
                "grand_total": "1635.00",
                "is_inter_state": False,
                "supply_state": "Maharashtra",
                "billing_state": "Maharashtra"
            }
        }
    }


class ProductGSTInfo(BaseModel):
    """GST information for a product"""

    product_id: str = Field(
        ...,
        description="Product identifier"
    )
    hsn_code: Optional[str] = Field(
        default=None,
        description="HSN/SAC code"
    )
    gst_rate: Decimal = Field(
        ...,
        ge=0,
        le=28,
        description="Applicable GST rate"
    )
    cess_rate: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Applicable cess rate"
    )
    gst_category: Optional[str] = Field(
        default=None,
        description="GST category code"
    )
    is_exempt: bool = Field(
        default=False,
        description="Whether product is GST exempt"
    )
    is_override: bool = Field(
        default=False,
        description="Whether rate is store-level override"
    )
    effective_date: Optional[str] = Field(
        default=None,
        description="Date from which rate is effective"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "product_id": "PROD-001",
                "hsn_code": "0902",
                "gst_rate": "5",
                "cess_rate": "0",
                "gst_category": "TEA",
                "is_exempt": False,
                "is_override": False
            }
        }
    }


class GSTCategoryResponse(BaseModel):
    """GST category information for API response"""

    code: str = Field(
        ...,
        description="Category code"
    )
    name: str = Field(
        ...,
        description="Category display name"
    )
    hsn_prefix: str = Field(
        ...,
        description="HSN code prefix(es) for this category"
    )
    gst_rate: Decimal = Field(
        ...,
        description="GST rate for this category"
    )
    cess_rate: Decimal = Field(
        default=Decimal("0"),
        description="Cess rate (if applicable)"
    )
    description: str = Field(
        default="",
        description="Category description"
    )
    item_count: int = Field(
        default=0,
        description="Number of products in this category"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "code": "TEA",
                "name": "Tea (Packaged)",
                "hsn_prefix": "0902",
                "gst_rate": "5",
                "cess_rate": "0",
                "description": "Packaged tea leaves, tea bags",
                "item_count": 45
            }
        }
    }


# ============================================================================
# REQUEST MODELS
# ============================================================================

class CalculateItemGSTRequest(BaseModel):
    """Request to calculate GST for a single item"""

    product_id: str = Field(
        ...,
        description="Product identifier"
    )
    store_id: str = Field(
        ...,
        description="Store identifier"
    )
    quantity: int = Field(
        default=1,
        ge=1,
        description="Quantity"
    )
    unit_price: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="Override unit price (optional, uses product price if not provided)"
    )
    is_inter_state: bool = Field(
        default=False,
        description="True for inter-state supply (use IGST)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "product_id": "PROD-001",
                "store_id": "STR-001",
                "quantity": 2,
                "unit_price": "250.00",
                "is_inter_state": False
            }
        }
    }


class OrderItemForGST(BaseModel):
    """Order item for GST calculation"""

    product_id: str = Field(
        ...,
        description="Product identifier"
    )
    quantity: int = Field(
        ...,
        ge=1,
        description="Quantity"
    )
    unit_price: Decimal = Field(
        ...,
        ge=0,
        description="Unit price"
    )
    product_name: str = Field(
        default="",
        description="Product name (optional)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "product_id": "PROD-001",
                "quantity": 2,
                "unit_price": "250.00",
                "product_name": "Tata Tea Gold 500g"
            }
        }
    }


class CalculateOrderGSTRequest(BaseModel):
    """Request to calculate GST for an entire order"""

    store_id: str = Field(
        ...,
        description="Store identifier"
    )
    items: List[OrderItemForGST] = Field(
        ...,
        min_length=1,
        description="List of order items"
    )
    billing_state: Optional[str] = Field(
        default=None,
        description="Customer billing state (for IGST determination)"
    )
    is_inter_state: bool = Field(
        default=False,
        description="True for inter-state supply"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "store_id": "STR-001",
                "items": [
                    {
                        "product_id": "PROD-001",
                        "quantity": 2,
                        "unit_price": "250.00",
                        "product_name": "Tata Tea Gold 500g"
                    },
                    {
                        "product_id": "PROD-002",
                        "quantity": 1,
                        "unit_price": "45.00",
                        "product_name": "Parle-G Biscuits"
                    }
                ],
                "billing_state": "Maharashtra",
                "is_inter_state": False
            }
        }
    }


class UpdateProductGSTRequest(BaseModel):
    """Request to update GST information for a product"""

    hsn_code: Optional[str] = Field(
        default=None,
        description="HSN code (4, 6, or 8 digits)"
    )
    gst_rate: Optional[Decimal] = Field(
        default=None,
        ge=0,
        le=28,
        description="GST rate override"
    )
    cess_rate: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="Cess rate"
    )
    gst_category: Optional[str] = Field(
        default=None,
        description="GST category code"
    )
    is_gst_exempt: Optional[bool] = Field(
        default=None,
        description="Whether product is GST exempt"
    )

    @field_validator('hsn_code')
    @classmethod
    def validate_hsn_code(cls, v):
        if v is None:
            return v
        v_clean = v.strip().replace(" ", "")
        if not v_clean.isdigit():
            raise ValueError("HSN code must contain only digits")
        if len(v_clean) not in (4, 6, 8):
            raise ValueError("HSN code must be 4, 6, or 8 digits")
        return v_clean

    @field_validator('gst_rate')
    @classmethod
    def validate_gst_rate(cls, v):
        if v is None:
            return v
        valid_rates = [Decimal("0"), Decimal("5"), Decimal("12"),
                       Decimal("18"), Decimal("28")]
        if v not in valid_rates:
            raise ValueError(f"GST rate must be one of {valid_rates}")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "hsn_code": "0902",
                "gst_rate": "5",
                "cess_rate": "0",
                "gst_category": "TEA",
                "is_gst_exempt": False
            }
        }
    }


# ============================================================================
# GST INVOICE MODELS
# ============================================================================

class GSTInvoiceHeader(BaseModel):
    """GST invoice header information"""

    invoice_number: str = Field(..., description="Invoice number")
    invoice_date: str = Field(..., description="Invoice date (YYYY-MM-DD)")
    order_id: str = Field(..., description="Associated order ID")

    # Seller details
    seller_gstin: Optional[str] = Field(default=None, description="Seller GSTIN")
    seller_name: str = Field(..., description="Seller/Store name")
    seller_address: str = Field(default="", description="Seller address")
    seller_state: str = Field(..., description="Seller state")
    seller_state_code: str = Field(default="", description="State code")

    # Buyer details
    buyer_name: str = Field(..., description="Buyer name")
    buyer_address: str = Field(default="", description="Buyer address")
    buyer_state: str = Field(default="", description="Buyer state")
    buyer_gstin: Optional[str] = Field(default=None, description="Buyer GSTIN (if B2B)")

    # Transaction type
    is_inter_state: bool = Field(default=False, description="Inter-state supply")
    supply_type: str = Field(default="B2C", description="B2B or B2C")


class GSTInvoice(BaseModel):
    """Complete GST invoice"""

    header: GSTInvoiceHeader = Field(..., description="Invoice header")
    items: List[ItemGSTBreakdown] = Field(..., description="Invoice line items")
    summary: OrderGSTSummary = Field(..., description="Tax summary")

    # Additional charges
    delivery_fee: Decimal = Field(default=Decimal("0"), description="Delivery charges")
    discount: Decimal = Field(default=Decimal("0"), description="Total discount")

    # Finals
    invoice_total: Decimal = Field(..., description="Final invoice amount")
    amount_in_words: str = Field(default="", description="Amount in words")
