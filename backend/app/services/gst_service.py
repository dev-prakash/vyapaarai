"""
GST Service for VyapaarAI
India GST Calculation Service

Handles:
- HSN code based tax lookup
- CGST/SGST/IGST split
- Cess calculation for luxury items
- Store-level rate overrides
- Rate-wise summary aggregation for GST filing

Author: DevPrakash
"""

import asyncio
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.gst_config import (
    GST_CATEGORIES,
    GSTRate,
    get_default_gst_rate,
    get_gst_rate_from_hsn,
    suggest_category_from_product_name,
)
from app.models.gst import (
    GSTCategoryResponse,
    ItemGSTBreakdown,
    OrderGSTSummary,
    ProductGSTInfo,
    RateWiseSummary,
)

logger = logging.getLogger(__name__)


class GSTService:
    """
    GST Calculation Service for VyapaarAI

    Provides India-compliant GST calculations including:
    - Per-item GST with CGST/SGST breakdown (intra-state)
    - IGST for inter-state transactions
    - Cess calculation for luxury/sin goods
    - Rate-wise summary for GST filing
    - Store-level rate overrides

    Usage:
        from app.services.gst_service import gst_service

        # Calculate GST for single item
        breakdown = await gst_service.calculate_item_gst(
            product_id="PROD-001",
            store_id="STORE-001",
            quantity=2,
            unit_price=Decimal("100.00")
        )

        # Calculate GST for order
        summary = await gst_service.calculate_order_gst(
            store_id="STORE-001",
            items=[{"product_id": "P1", "quantity": 2, "unit_price": Decimal("100")}]
        )
    """

    def __init__(self):
        """Initialize GST service with DynamoDB connection"""
        self.use_mock = False

        try:
            kwargs = {'region_name': settings.AWS_REGION}
            if settings.DYNAMODB_ENDPOINT:
                kwargs['endpoint_url'] = settings.DYNAMODB_ENDPOINT

            self.dynamodb = boto3.resource('dynamodb', **kwargs)

            # Table names based on environment
            env_suffix = 'prod' if settings.ENVIRONMENT.lower() == 'production' else 'dev'
            self.store_inventory_table = self.dynamodb.Table(
                f'vyaparai-store-inventory-{env_suffix}'
            )
            self.global_products_table = self.dynamodb.Table(
                f'vyaparai-global-products-{env_suffix}'
            )

            logger.info("GST service initialized successfully")

        except Exception as e:
            logger.error(f"GST service initialization failed: {e}")
            if settings.ENVIRONMENT.lower() == 'production':
                raise RuntimeError(f"GST service required but failed: {e}")
            self.use_mock = True
            logger.warning("GST service running in mock mode")

    def _round_tax(self, amount: Decimal) -> Decimal:
        """
        Round tax amount to 2 decimal places using standard GST rounding.

        Args:
            amount: Amount to round

        Returns:
            Rounded amount (ROUND_HALF_UP)
        """
        return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def _split_gst(
        self,
        gst_rate: Decimal,
        taxable_amount: Decimal,
        is_inter_state: bool = False
    ) -> Dict[str, Decimal]:
        """
        Split GST into CGST/SGST or IGST based on transaction type.

        For intra-state: GST split equally into CGST (Central) and SGST (State)
        For inter-state: Full GST as IGST (Integrated)

        Args:
            gst_rate: Total GST rate (e.g., 18)
            taxable_amount: Amount before tax
            is_inter_state: True for inter-state supply

        Returns:
            Dict with cgst_rate, cgst_amount, sgst_rate, sgst_amount,
            igst_rate, igst_amount
        """
        gst_amount = self._round_tax(
            taxable_amount * gst_rate / Decimal('100')
        )

        if is_inter_state:
            # Inter-state: Use IGST (full rate)
            return {
                'igst_rate': gst_rate,
                'igst_amount': gst_amount,
                'cgst_rate': Decimal('0'),
                'cgst_amount': Decimal('0'),
                'sgst_rate': Decimal('0'),
                'sgst_amount': Decimal('0'),
            }
        else:
            # Intra-state: Split into CGST and SGST (50% each)
            half_rate = gst_rate / Decimal('2')
            half_amount = self._round_tax(
                taxable_amount * half_rate / Decimal('100')
            )
            return {
                'cgst_rate': half_rate,
                'cgst_amount': half_amount,
                'sgst_rate': half_rate,
                'sgst_amount': half_amount,
                'igst_rate': Decimal('0'),
                'igst_amount': Decimal('0'),
            }

    async def get_gst_rate_for_product(
        self,
        product_id: str,
        store_id: str
    ) -> ProductGSTInfo:
        """
        Get applicable GST rate for a product.

        Priority order:
        1. Store-level override (gst_rate_override field)
        2. Product-level GST rate (gst_rate field)
        3. HSN code lookup (from HSN_TO_CATEGORY mapping)
        4. Category suggestion from product name
        5. Default rate (18% - conservative)

        Args:
            product_id: Product identifier
            store_id: Store identifier

        Returns:
            ProductGSTInfo with applicable GST rate and details
        """
        if self.use_mock:
            # Mock mode - return default rate
            return ProductGSTInfo(
                product_id=product_id,
                gst_rate=get_default_gst_rate().value,
                cess_rate=Decimal('0'),
                is_override=False
            )

        try:
            # Check store inventory for product and potential override
            response = await asyncio.to_thread(
                self.store_inventory_table.get_item,
                Key={'store_id': store_id, 'product_id': product_id}
            )

            if 'Item' in response:
                item = response['Item']

                # Priority 1: Store-level override
                if item.get('gst_rate_override') is not None:
                    return ProductGSTInfo(
                        product_id=product_id,
                        hsn_code=item.get('hsn_code'),
                        gst_rate=Decimal(str(item['gst_rate_override'])),
                        cess_rate=Decimal(str(item.get('cess_rate', 0))),
                        gst_category=item.get('gst_category'),
                        is_exempt=item.get('is_gst_exempt', False),
                        is_override=True
                    )

                # Priority 2: Product-level GST rate
                if item.get('gst_rate') is not None:
                    return ProductGSTInfo(
                        product_id=product_id,
                        hsn_code=item.get('hsn_code'),
                        gst_rate=Decimal(str(item['gst_rate'])),
                        cess_rate=Decimal(str(item.get('cess_rate', 0))),
                        gst_category=item.get('gst_category'),
                        is_exempt=item.get('is_gst_exempt', False),
                        is_override=False
                    )

                # Priority 3: HSN code lookup
                hsn_code = item.get('hsn_code')
                if hsn_code:
                    category = get_gst_rate_from_hsn(hsn_code)
                    if category:
                        return ProductGSTInfo(
                            product_id=product_id,
                            hsn_code=hsn_code,
                            gst_rate=category.gst_rate.value,
                            cess_rate=category.cess_rate,
                            gst_category=category.code,
                            is_exempt=False,
                            is_override=False
                        )

                # Priority 4: Category suggestion from product name
                product_name = item.get('product_name', '')
                if product_name:
                    suggested_category = suggest_category_from_product_name(product_name)
                    if suggested_category and suggested_category in GST_CATEGORIES:
                        cat = GST_CATEGORIES[suggested_category]
                        return ProductGSTInfo(
                            product_id=product_id,
                            gst_rate=cat.gst_rate.value,
                            cess_rate=cat.cess_rate,
                            gst_category=cat.code,
                            is_exempt=False,
                            is_override=False
                        )

            # Priority 5: Default rate
            return ProductGSTInfo(
                product_id=product_id,
                gst_rate=get_default_gst_rate().value,
                cess_rate=Decimal('0'),
                is_override=False
            )

        except ClientError as e:
            logger.error(f"DynamoDB error getting GST rate for {product_id}: {e}")
            return ProductGSTInfo(
                product_id=product_id,
                gst_rate=get_default_gst_rate().value,
                cess_rate=Decimal('0'),
                is_override=False
            )
        except Exception as e:
            logger.error(f"Error getting GST rate for {product_id}: {e}")
            return ProductGSTInfo(
                product_id=product_id,
                gst_rate=get_default_gst_rate().value,
                cess_rate=Decimal('0'),
                is_override=False
            )

    async def calculate_item_gst(
        self,
        product_id: str,
        store_id: str,
        quantity: int,
        unit_price: Decimal,
        product_name: str = "",
        is_inter_state: bool = False
    ) -> ItemGSTBreakdown:
        """
        Calculate GST for a single item.

        Args:
            product_id: Product identifier
            store_id: Store identifier
            quantity: Number of units
            unit_price: Price per unit (before tax)
            product_name: Product name (optional)
            is_inter_state: True for inter-state supply

        Returns:
            ItemGSTBreakdown with complete tax breakdown
        """
        # Get GST rate for product
        gst_info = await self.get_gst_rate_for_product(product_id, store_id)

        # Calculate taxable amount
        taxable_amount = self._round_tax(Decimal(str(unit_price)) * quantity)

        # Handle exempt items
        if gst_info.is_exempt:
            return ItemGSTBreakdown(
                product_id=product_id,
                product_name=product_name,
                quantity=quantity,
                unit_price=Decimal(str(unit_price)),
                taxable_amount=taxable_amount,
                gst_rate=Decimal('0'),
                cgst_rate=Decimal('0'),
                cgst_amount=Decimal('0'),
                sgst_rate=Decimal('0'),
                sgst_amount=Decimal('0'),
                igst_rate=Decimal('0'),
                igst_amount=Decimal('0'),
                cess_rate=Decimal('0'),
                cess_amount=Decimal('0'),
                total_tax=Decimal('0'),
                total_amount=taxable_amount,
                hsn_code=gst_info.hsn_code,
                gst_category=gst_info.gst_category,
                is_exempt=True
            )

        # Split GST into CGST/SGST or IGST
        gst_split = self._split_gst(
            gst_info.gst_rate,
            taxable_amount,
            is_inter_state
        )

        # Calculate cess (for luxury/sin goods)
        cess_amount = Decimal('0')
        if gst_info.cess_rate > 0:
            cess_amount = self._round_tax(
                taxable_amount * gst_info.cess_rate / Decimal('100')
            )

        # Calculate totals
        total_gst = (
            gst_split['cgst_amount'] +
            gst_split['sgst_amount'] +
            gst_split['igst_amount']
        )
        total_tax = total_gst + cess_amount
        total_amount = taxable_amount + total_tax

        return ItemGSTBreakdown(
            product_id=product_id,
            product_name=product_name,
            quantity=quantity,
            unit_price=Decimal(str(unit_price)),
            taxable_amount=taxable_amount,
            gst_rate=gst_info.gst_rate,
            cgst_rate=gst_split['cgst_rate'],
            cgst_amount=gst_split['cgst_amount'],
            sgst_rate=gst_split['sgst_rate'],
            sgst_amount=gst_split['sgst_amount'],
            igst_rate=gst_split['igst_rate'],
            igst_amount=gst_split['igst_amount'],
            cess_rate=gst_info.cess_rate,
            cess_amount=cess_amount,
            total_tax=total_tax,
            total_amount=total_amount,
            hsn_code=gst_info.hsn_code,
            gst_category=gst_info.gst_category,
            is_exempt=False
        )

    async def calculate_order_gst(
        self,
        store_id: str,
        items: List[Dict[str, Any]],
        is_inter_state: bool = False,
        billing_state: Optional[str] = None,
        supply_state: Optional[str] = None
    ) -> OrderGSTSummary:
        """
        Calculate GST for an entire order.

        Args:
            store_id: Store identifier
            items: List of items [{product_id, quantity, unit_price, product_name}]
            is_inter_state: True for inter-state supply
            billing_state: Customer billing state
            supply_state: Store/supply state

        Returns:
            OrderGSTSummary with item breakdowns and rate-wise summary
        """
        item_breakdowns: List[ItemGSTBreakdown] = []
        rate_wise_data: Dict[Decimal, Dict[str, Decimal]] = {}

        # Calculate GST for each item
        for item in items:
            breakdown = await self.calculate_item_gst(
                product_id=item['product_id'],
                store_id=store_id,
                quantity=int(item['quantity']),
                unit_price=Decimal(str(item['unit_price'])),
                product_name=item.get('product_name', ''),
                is_inter_state=is_inter_state
            )
            item_breakdowns.append(breakdown)

            # Aggregate by rate for rate-wise summary
            rate = breakdown.gst_rate
            if rate not in rate_wise_data:
                rate_wise_data[rate] = {
                    'taxable_amount': Decimal('0'),
                    'cgst_amount': Decimal('0'),
                    'sgst_amount': Decimal('0'),
                    'igst_amount': Decimal('0'),
                    'cess_amount': Decimal('0'),
                }

            rate_wise_data[rate]['taxable_amount'] += breakdown.taxable_amount
            rate_wise_data[rate]['cgst_amount'] += breakdown.cgst_amount
            rate_wise_data[rate]['sgst_amount'] += breakdown.sgst_amount
            rate_wise_data[rate]['igst_amount'] += breakdown.igst_amount
            rate_wise_data[rate]['cess_amount'] += breakdown.cess_amount

        # Build rate-wise summary (sorted by rate)
        rate_wise_summary: List[RateWiseSummary] = []
        for rate in sorted(rate_wise_data.keys()):
            data = rate_wise_data[rate]
            total_tax = (
                data['cgst_amount'] +
                data['sgst_amount'] +
                data['igst_amount'] +
                data['cess_amount']
            )
            rate_wise_summary.append(RateWiseSummary(
                gst_rate=rate,
                taxable_amount=data['taxable_amount'],
                cgst_amount=data['cgst_amount'],
                sgst_amount=data['sgst_amount'],
                igst_amount=data['igst_amount'],
                cess_amount=data['cess_amount'],
                total_tax=total_tax
            ))

        # Calculate order totals
        subtotal = sum(b.taxable_amount for b in item_breakdowns)
        cgst_total = sum(b.cgst_amount for b in item_breakdowns)
        sgst_total = sum(b.sgst_amount for b in item_breakdowns)
        igst_total = sum(b.igst_amount for b in item_breakdowns)
        cess_total = sum(b.cess_amount for b in item_breakdowns)
        tax_total = cgst_total + sgst_total + igst_total + cess_total
        grand_total = subtotal + tax_total

        return OrderGSTSummary(
            order_id="",  # Will be set by caller
            store_id=store_id,
            subtotal=subtotal,
            cgst_total=cgst_total,
            sgst_total=sgst_total,
            igst_total=igst_total,
            cess_total=cess_total,
            tax_total=tax_total,
            grand_total=grand_total,
            is_inter_state=is_inter_state,
            supply_state=supply_state,
            billing_state=billing_state,
            item_breakdowns=item_breakdowns,
            rate_wise_summary=rate_wise_summary
        )

    def get_all_gst_categories(self) -> List[GSTCategoryResponse]:
        """
        Get all configured GST categories.

        Returns:
            List of GSTCategoryResponse objects
        """
        categories = []
        for key, cat in GST_CATEGORIES.items():
            categories.append(GSTCategoryResponse(
                code=cat.code,
                name=cat.name,
                hsn_prefix=cat.hsn_prefix,
                gst_rate=cat.gst_rate.value,
                cess_rate=cat.cess_rate,
                description=cat.description
            ))

        # Sort by rate, then by name
        categories.sort(key=lambda c: (c.gst_rate, c.name))
        return categories

    def get_hsn_info(self, hsn_code: str) -> Optional[GSTCategoryResponse]:
        """
        Get GST information for an HSN code.

        Args:
            hsn_code: HSN code to lookup

        Returns:
            GSTCategoryResponse if found, None otherwise
        """
        category = get_gst_rate_from_hsn(hsn_code)
        if category:
            return GSTCategoryResponse(
                code=category.code,
                name=category.name,
                hsn_prefix=category.hsn_prefix,
                gst_rate=category.gst_rate.value,
                cess_rate=category.cess_rate,
                description=category.description
            )
        return None

    def suggest_gst_category(self, product_name: str) -> Optional[GSTCategoryResponse]:
        """
        Suggest GST category based on product name.

        Args:
            product_name: Product name to analyze

        Returns:
            GSTCategoryResponse if suggestion found, None otherwise
        """
        category_key = suggest_category_from_product_name(product_name)
        if category_key and category_key in GST_CATEGORIES:
            cat = GST_CATEGORIES[category_key]
            return GSTCategoryResponse(
                code=cat.code,
                name=cat.name,
                hsn_prefix=cat.hsn_prefix,
                gst_rate=cat.gst_rate.value,
                cess_rate=cat.cess_rate,
                description=cat.description
            )
        return None


# Global singleton instance
gst_service = GSTService()
