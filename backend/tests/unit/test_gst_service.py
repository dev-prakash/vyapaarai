"""
Unit Tests for GST Service
Author: DevPrakash

Comprehensive tests for India GST calculation accuracy across all tax slabs.
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.gst_config import (
    GST_CATEGORIES,
    GSTRate,
    get_default_gst_rate,
    get_gst_rate_from_hsn,
    suggest_category_from_product_name,
    validate_hsn_code,
)
from app.models.gst import ProductGSTInfo
from app.services.gst_service import GSTService


# ============================================================================
# TEST: GST Configuration
# ============================================================================

class TestGSTConfig:
    """Tests for GST configuration and HSN lookup"""

    @pytest.mark.unit
    def test_all_gst_rates_are_valid(self):
        """Verify all GST rate enum values are valid Indian rates"""
        valid_rates = {
            Decimal("0"), Decimal("5"), Decimal("12"),
            Decimal("18"), Decimal("28")
        }
        for rate in GSTRate:
            assert rate.value in valid_rates, f"Invalid rate: {rate.value}"

    @pytest.mark.unit
    def test_gst_categories_count(self):
        """Verify we have 35+ GST categories configured"""
        assert len(GST_CATEGORIES) >= 35, \
            f"Expected 35+ categories, found {len(GST_CATEGORIES)}"

    @pytest.mark.unit
    def test_all_categories_have_valid_rates(self):
        """Verify all categories have valid GST rates"""
        valid_rates = {GSTRate.ZERO, GSTRate.FIVE, GSTRate.TWELVE,
                       GSTRate.EIGHTEEN, GSTRate.TWENTY_EIGHT}
        for key, cat in GST_CATEGORIES.items():
            assert cat.gst_rate in valid_rates, \
                f"Invalid rate for {key}: {cat.gst_rate}"

    @pytest.mark.unit
    def test_all_categories_have_hsn_prefix(self):
        """Verify all categories have HSN prefix defined"""
        for key, cat in GST_CATEGORIES.items():
            assert cat.hsn_prefix, f"Missing HSN prefix for {key}"

    @pytest.mark.unit
    def test_default_gst_rate(self):
        """Verify default GST rate is 18%"""
        default = get_default_gst_rate()
        assert default == GSTRate.EIGHTEEN
        assert default.value == Decimal("18")


class TestHSNLookup:
    """Tests for HSN code lookup functionality"""

    @pytest.mark.unit
    def test_hsn_lookup_tea(self):
        """Test HSN lookup for tea (0902) returns 5%"""
        category = get_gst_rate_from_hsn("0902")
        assert category is not None
        assert category.gst_rate == GSTRate.FIVE

    @pytest.mark.unit
    def test_hsn_lookup_biscuits(self):
        """Test HSN lookup for biscuits (1905) returns 18%"""
        category = get_gst_rate_from_hsn("1905")
        assert category is not None
        assert category.gst_rate == GSTRate.EIGHTEEN

    @pytest.mark.unit
    def test_hsn_lookup_aerated_drinks(self):
        """Test HSN lookup for aerated drinks (2202) returns 28% + cess"""
        category = get_gst_rate_from_hsn("2202")
        assert category is not None
        assert category.gst_rate == GSTRate.TWENTY_EIGHT
        assert category.cess_rate > 0

    @pytest.mark.unit
    def test_hsn_lookup_fresh_vegetables(self):
        """Test HSN lookup for fresh vegetables (0702) returns 0%"""
        category = get_gst_rate_from_hsn("0702")
        assert category is not None
        assert category.gst_rate == GSTRate.ZERO

    @pytest.mark.unit
    def test_hsn_lookup_invalid_code(self):
        """Test HSN lookup returns None for invalid code"""
        category = get_gst_rate_from_hsn("9999")
        assert category is None

    @pytest.mark.unit
    def test_hsn_lookup_empty_code(self):
        """Test HSN lookup returns None for empty code"""
        category = get_gst_rate_from_hsn("")
        assert category is None

    @pytest.mark.unit
    def test_hsn_lookup_prefix_match(self):
        """Test HSN lookup works with 4-digit prefix"""
        # 07011000 should match 0701 (potatoes)
        category = get_gst_rate_from_hsn("07010000")
        assert category is not None
        assert category.gst_rate == GSTRate.ZERO


class TestHSNValidation:
    """Tests for HSN code validation"""

    @pytest.mark.unit
    def test_validate_hsn_4_digits(self):
        """Valid 4-digit HSN code"""
        assert validate_hsn_code("0902") is True

    @pytest.mark.unit
    def test_validate_hsn_6_digits(self):
        """Valid 6-digit HSN code"""
        assert validate_hsn_code("090210") is True

    @pytest.mark.unit
    def test_validate_hsn_8_digits(self):
        """Valid 8-digit HSN code"""
        assert validate_hsn_code("09021010") is True

    @pytest.mark.unit
    def test_validate_hsn_invalid_length(self):
        """Invalid 5-digit HSN code"""
        assert validate_hsn_code("09021") is False

    @pytest.mark.unit
    def test_validate_hsn_non_numeric(self):
        """Invalid non-numeric HSN code"""
        assert validate_hsn_code("090A") is False

    @pytest.mark.unit
    def test_validate_hsn_empty(self):
        """Empty HSN code is invalid"""
        assert validate_hsn_code("") is False


class TestCategorySuggestion:
    """Tests for category suggestion from product name"""

    @pytest.mark.unit
    def test_suggest_category_tea(self):
        """Suggest TEA category for tea products"""
        assert suggest_category_from_product_name("Tata Tea Gold") == "TEA_PACKAGED"

    @pytest.mark.unit
    def test_suggest_category_biscuit(self):
        """Suggest BISCUITS category for biscuit products"""
        assert suggest_category_from_product_name("Parle-G Biscuits") == "BISCUITS"

    @pytest.mark.unit
    def test_suggest_category_soap(self):
        """Suggest SOAP category for soap products"""
        assert suggest_category_from_product_name("Lux Soap") == "SOAP"

    @pytest.mark.unit
    def test_suggest_category_cola(self):
        """Suggest AERATED_DRINKS for cola products"""
        assert suggest_category_from_product_name("Coca Cola 2L") == "AERATED_DRINKS"

    @pytest.mark.unit
    def test_suggest_category_unknown(self):
        """Return None for unknown product names"""
        assert suggest_category_from_product_name("XYZ Product") is None


# ============================================================================
# TEST: GST Service - Tax Split
# ============================================================================

class TestGSTSplit:
    """Tests for CGST/SGST/IGST split calculations"""

    @pytest.fixture
    def gst_service(self):
        """Create GST service with mock mode"""
        service = GSTService()
        service.use_mock = True
        return service

    @pytest.mark.unit
    @pytest.mark.regression
    def test_cgst_sgst_split_intra_state(self, gst_service):
        """Verify CGST and SGST are exactly half of total GST for intra-state"""
        split = gst_service._split_gst(
            gst_rate=Decimal("18"),
            taxable_amount=Decimal("1000.00"),
            is_inter_state=False
        )

        assert split['cgst_rate'] == Decimal("9")
        assert split['sgst_rate'] == Decimal("9")
        assert split['cgst_amount'] == Decimal("90.00")
        assert split['sgst_amount'] == Decimal("90.00")
        assert split['igst_rate'] == Decimal("0")
        assert split['igst_amount'] == Decimal("0")

    @pytest.mark.unit
    @pytest.mark.regression
    def test_igst_for_inter_state(self, gst_service):
        """Verify IGST is used for inter-state transactions"""
        split = gst_service._split_gst(
            gst_rate=Decimal("18"),
            taxable_amount=Decimal("1000.00"),
            is_inter_state=True
        )

        assert split['cgst_rate'] == Decimal("0")
        assert split['sgst_rate'] == Decimal("0")
        assert split['cgst_amount'] == Decimal("0")
        assert split['sgst_amount'] == Decimal("0")
        assert split['igst_rate'] == Decimal("18")
        assert split['igst_amount'] == Decimal("180.00")

    @pytest.mark.unit
    @pytest.mark.regression
    def test_split_5_percent(self, gst_service):
        """Test 5% GST split"""
        split = gst_service._split_gst(
            gst_rate=Decimal("5"),
            taxable_amount=Decimal("100.00"),
            is_inter_state=False
        )

        assert split['cgst_rate'] == Decimal("2.5")
        assert split['sgst_rate'] == Decimal("2.5")
        assert split['cgst_amount'] == Decimal("2.50")
        assert split['sgst_amount'] == Decimal("2.50")

    @pytest.mark.unit
    @pytest.mark.regression
    def test_split_zero_percent(self, gst_service):
        """Test 0% GST split"""
        split = gst_service._split_gst(
            gst_rate=Decimal("0"),
            taxable_amount=Decimal("100.00"),
            is_inter_state=False
        )

        assert split['cgst_rate'] == Decimal("0")
        assert split['sgst_rate'] == Decimal("0")
        assert split['cgst_amount'] == Decimal("0")
        assert split['sgst_amount'] == Decimal("0")


# ============================================================================
# TEST: GST Service - Item Calculation
# ============================================================================

class TestItemGSTCalculation:
    """Tests for per-item GST calculations"""

    @pytest.fixture
    def gst_service(self):
        """Create GST service with mock mode"""
        service = GSTService()
        service.use_mock = True
        return service

    @pytest.mark.unit
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_calculate_item_gst_zero_rate(self, gst_service):
        """Test GST calculation for 0% items (essentials)"""
        # Mock the get_gst_rate_for_product to return 0% rate
        with patch.object(gst_service, 'get_gst_rate_for_product') as mock:
            mock.return_value = ProductGSTInfo(
                product_id="PROD-001",
                gst_rate=Decimal("0"),
                cess_rate=Decimal("0"),
                hsn_code="0701",
                is_exempt=False
            )

            result = await gst_service.calculate_item_gst(
                product_id="PROD-001",
                store_id="STORE-001",
                quantity=2,
                unit_price=Decimal("100.00")
            )

        assert result.taxable_amount == Decimal("200.00")
        assert result.gst_rate == Decimal("0")
        assert result.total_tax == Decimal("0.00")
        assert result.total_amount == Decimal("200.00")

    @pytest.mark.unit
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_calculate_item_gst_five_percent(self, gst_service):
        """Test GST calculation for 5% items"""
        with patch.object(gst_service, 'get_gst_rate_for_product') as mock:
            mock.return_value = ProductGSTInfo(
                product_id="PROD-001",
                gst_rate=Decimal("5"),
                cess_rate=Decimal("0"),
                hsn_code="0902",
                is_exempt=False
            )

            result = await gst_service.calculate_item_gst(
                product_id="PROD-001",
                store_id="STORE-001",
                quantity=1,
                unit_price=Decimal("100.00")
            )

        assert result.gst_rate == Decimal("5")
        assert result.cgst_rate == Decimal("2.5")
        assert result.sgst_rate == Decimal("2.5")
        assert result.cgst_amount == Decimal("2.50")
        assert result.sgst_amount == Decimal("2.50")
        assert result.total_tax == Decimal("5.00")
        assert result.total_amount == Decimal("105.00")

    @pytest.mark.unit
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_calculate_item_gst_twelve_percent(self, gst_service):
        """Test GST calculation for 12% items"""
        with patch.object(gst_service, 'get_gst_rate_for_product') as mock:
            mock.return_value = ProductGSTInfo(
                product_id="PROD-001",
                gst_rate=Decimal("12"),
                cess_rate=Decimal("0"),
                hsn_code="0405",
                is_exempt=False
            )

            result = await gst_service.calculate_item_gst(
                product_id="PROD-001",
                store_id="STORE-001",
                quantity=1,
                unit_price=Decimal("100.00")
            )

        assert result.gst_rate == Decimal("12")
        assert result.cgst_rate == Decimal("6")
        assert result.sgst_rate == Decimal("6")
        assert result.cgst_amount == Decimal("6.00")
        assert result.sgst_amount == Decimal("6.00")
        assert result.total_tax == Decimal("12.00")
        assert result.total_amount == Decimal("112.00")

    @pytest.mark.unit
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_calculate_item_gst_eighteen_percent(self, gst_service):
        """Test GST calculation for 18% items (standard rate)"""
        with patch.object(gst_service, 'get_gst_rate_for_product') as mock:
            mock.return_value = ProductGSTInfo(
                product_id="PROD-001",
                gst_rate=Decimal("18"),
                cess_rate=Decimal("0"),
                hsn_code="1905",
                is_exempt=False
            )

            result = await gst_service.calculate_item_gst(
                product_id="PROD-001",
                store_id="STORE-001",
                quantity=1,
                unit_price=Decimal("100.00")
            )

        assert result.gst_rate == Decimal("18")
        assert result.cgst_amount == Decimal("9.00")
        assert result.sgst_amount == Decimal("9.00")
        assert result.total_tax == Decimal("18.00")
        assert result.total_amount == Decimal("118.00")

    @pytest.mark.unit
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_calculate_item_gst_twentyeight_percent_with_cess(self, gst_service):
        """Test GST calculation for 28% items with cess (luxury)"""
        with patch.object(gst_service, 'get_gst_rate_for_product') as mock:
            mock.return_value = ProductGSTInfo(
                product_id="PROD-001",
                gst_rate=Decimal("28"),
                cess_rate=Decimal("12"),  # 12% cess on aerated drinks
                hsn_code="2202",
                is_exempt=False
            )

            result = await gst_service.calculate_item_gst(
                product_id="PROD-001",
                store_id="STORE-001",
                quantity=1,
                unit_price=Decimal("100.00")
            )

        assert result.gst_rate == Decimal("28")
        assert result.cgst_amount == Decimal("14.00")
        assert result.sgst_amount == Decimal("14.00")
        assert result.cess_rate == Decimal("12")
        assert result.cess_amount == Decimal("12.00")
        assert result.total_tax == Decimal("40.00")  # 28% GST + 12% cess
        assert result.total_amount == Decimal("140.00")

    @pytest.mark.unit
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_calculate_item_gst_exempt(self, gst_service):
        """Test GST calculation for exempt items"""
        with patch.object(gst_service, 'get_gst_rate_for_product') as mock:
            mock.return_value = ProductGSTInfo(
                product_id="PROD-001",
                gst_rate=Decimal("0"),
                cess_rate=Decimal("0"),
                is_exempt=True
            )

            result = await gst_service.calculate_item_gst(
                product_id="PROD-001",
                store_id="STORE-001",
                quantity=1,
                unit_price=Decimal("100.00")
            )

        assert result.is_exempt is True
        assert result.total_tax == Decimal("0")
        assert result.total_amount == Decimal("100.00")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_calculate_item_gst_inter_state(self, gst_service):
        """Test GST calculation for inter-state supply uses IGST"""
        with patch.object(gst_service, 'get_gst_rate_for_product') as mock:
            mock.return_value = ProductGSTInfo(
                product_id="PROD-001",
                gst_rate=Decimal("18"),
                cess_rate=Decimal("0"),
                is_exempt=False
            )

            result = await gst_service.calculate_item_gst(
                product_id="PROD-001",
                store_id="STORE-001",
                quantity=1,
                unit_price=Decimal("100.00"),
                is_inter_state=True
            )

        assert result.cgst_amount == Decimal("0")
        assert result.sgst_amount == Decimal("0")
        assert result.igst_rate == Decimal("18")
        assert result.igst_amount == Decimal("18.00")
        assert result.total_tax == Decimal("18.00")


# ============================================================================
# TEST: GST Service - Order Calculation
# ============================================================================

class TestOrderGSTCalculation:
    """Tests for order-level GST calculations"""

    @pytest.fixture
    def gst_service(self):
        """Create GST service with mock mode"""
        service = GSTService()
        service.use_mock = True
        return service

    @pytest.mark.unit
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_order_with_mixed_gst_rates(self, gst_service):
        """Test order with items at different GST rates"""
        # Mock to return different rates for different products
        async def mock_get_rate(product_id, store_id):
            rates = {
                'PROD-001': ProductGSTInfo(
                    product_id='PROD-001',
                    gst_rate=Decimal('5'),
                    cess_rate=Decimal('0')
                ),
                'PROD-002': ProductGSTInfo(
                    product_id='PROD-002',
                    gst_rate=Decimal('18'),
                    cess_rate=Decimal('0')
                ),
                'PROD-003': ProductGSTInfo(
                    product_id='PROD-003',
                    gst_rate=Decimal('0'),
                    cess_rate=Decimal('0')
                ),
            }
            return rates.get(product_id, ProductGSTInfo(
                product_id=product_id,
                gst_rate=Decimal('18'),
                cess_rate=Decimal('0')
            ))

        with patch.object(gst_service, 'get_gst_rate_for_product',
                          side_effect=mock_get_rate):
            result = await gst_service.calculate_order_gst(
                store_id="STORE-001",
                items=[
                    {'product_id': 'PROD-001', 'quantity': 2,
                     'unit_price': Decimal('100'), 'product_name': 'Tea'},
                    {'product_id': 'PROD-002', 'quantity': 1,
                     'unit_price': Decimal('200'), 'product_name': 'Biscuits'},
                    {'product_id': 'PROD-003', 'quantity': 3,
                     'unit_price': Decimal('50'), 'product_name': 'Rice'},
                ]
            )

        # Verify rate-wise summary has 3 entries (0%, 5%, 18%)
        assert len(result.rate_wise_summary) == 3

        # Verify subtotal: 200 + 200 + 150 = 550
        assert result.subtotal == Decimal('550.00')

        # Verify item count
        assert len(result.item_breakdowns) == 3

    @pytest.mark.unit
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_rate_wise_summary_aggregation(self, gst_service):
        """Test rate-wise summary correctly aggregates multiple items at same rate"""
        async def mock_get_rate(product_id, store_id):
            return ProductGSTInfo(
                product_id=product_id,
                gst_rate=Decimal('18'),
                cess_rate=Decimal('0')
            )

        with patch.object(gst_service, 'get_gst_rate_for_product',
                          side_effect=mock_get_rate):
            result = await gst_service.calculate_order_gst(
                store_id="STORE-001",
                items=[
                    {'product_id': 'PROD-001', 'quantity': 1,
                     'unit_price': Decimal('100'), 'product_name': 'Item 1'},
                    {'product_id': 'PROD-002', 'quantity': 1,
                     'unit_price': Decimal('100'), 'product_name': 'Item 2'},
                ]
            )

        # Should have single rate summary (both items at 18%)
        assert len(result.rate_wise_summary) == 1
        assert result.rate_wise_summary[0].gst_rate == Decimal('18')
        assert result.rate_wise_summary[0].taxable_amount == Decimal('200.00')
        assert result.rate_wise_summary[0].total_tax == Decimal('36.00')

    @pytest.mark.unit
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_order_totals_accuracy(self, gst_service):
        """Test order total calculations are accurate"""
        async def mock_get_rate(product_id, store_id):
            return ProductGSTInfo(
                product_id=product_id,
                gst_rate=Decimal('18'),
                cess_rate=Decimal('0')
            )

        with patch.object(gst_service, 'get_gst_rate_for_product',
                          side_effect=mock_get_rate):
            result = await gst_service.calculate_order_gst(
                store_id="STORE-001",
                items=[
                    {'product_id': 'PROD-001', 'quantity': 1,
                     'unit_price': Decimal('100.00')},
                ]
            )

        # Subtotal: 100
        assert result.subtotal == Decimal('100.00')
        # CGST: 9, SGST: 9
        assert result.cgst_total == Decimal('9.00')
        assert result.sgst_total == Decimal('9.00')
        # Total tax: 18
        assert result.tax_total == Decimal('18.00')
        # Grand total: 118
        assert result.grand_total == Decimal('118.00')

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_order_empty_items(self, gst_service):
        """Test order with empty items list"""
        result = await gst_service.calculate_order_gst(
            store_id="STORE-001",
            items=[]
        )

        assert result.subtotal == Decimal('0')
        assert result.tax_total == Decimal('0')
        assert result.grand_total == Decimal('0')
        assert len(result.item_breakdowns) == 0
        assert len(result.rate_wise_summary) == 0


# ============================================================================
# TEST: GST Service - Edge Cases
# ============================================================================

class TestGSTEdgeCases:
    """Tests for edge cases and special scenarios"""

    @pytest.fixture
    def gst_service(self):
        """Create GST service with mock mode"""
        service = GSTService()
        service.use_mock = True
        return service

    @pytest.mark.unit
    @pytest.mark.regression
    def test_rounding_consistency(self, gst_service):
        """Test tax rounding follows standard rules (ROUND_HALF_UP)"""
        # Rs 99.99 at 18% = 17.9982, should round to 18.00
        result = gst_service._round_tax(Decimal("99.99") * Decimal("0.18"))
        assert result == Decimal("18.00")

        # Rs 10.05 should stay 10.05
        result = gst_service._round_tax(Decimal("10.05"))
        assert result == Decimal("10.05")

        # Rs 10.005 should round to 10.01
        result = gst_service._round_tax(Decimal("10.005"))
        assert result == Decimal("10.01")

    @pytest.mark.unit
    @pytest.mark.regression
    def test_rounding_small_amounts(self, gst_service):
        """Test rounding for small tax amounts"""
        # 5% on Rs 1 = 0.05
        result = gst_service._round_tax(Decimal("1.00") * Decimal("0.05"))
        assert result == Decimal("0.05")

    @pytest.mark.unit
    def test_get_all_categories(self, gst_service):
        """Test getting all GST categories"""
        categories = gst_service.get_all_gst_categories()
        assert len(categories) >= 35
        assert all(hasattr(c, 'code') for c in categories)
        assert all(hasattr(c, 'gst_rate') for c in categories)

    @pytest.mark.unit
    def test_get_hsn_info_valid(self, gst_service):
        """Test HSN info lookup for valid code"""
        result = gst_service.get_hsn_info("0902")
        assert result is not None
        assert result.gst_rate == Decimal("5")

    @pytest.mark.unit
    def test_get_hsn_info_invalid(self, gst_service):
        """Test HSN info lookup for invalid code"""
        result = gst_service.get_hsn_info("9999")
        assert result is None

    @pytest.mark.unit
    def test_suggest_category(self, gst_service):
        """Test category suggestion from product name"""
        result = gst_service.suggest_gst_category("Tata Tea Premium")
        assert result is not None
        assert result.gst_rate == Decimal("5")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_large_quantity(self, gst_service):
        """Test GST calculation with large quantities"""
        with patch.object(gst_service, 'get_gst_rate_for_product') as mock:
            mock.return_value = ProductGSTInfo(
                product_id="PROD-001",
                gst_rate=Decimal("18"),
                cess_rate=Decimal("0"),
                is_exempt=False
            )

            result = await gst_service.calculate_item_gst(
                product_id="PROD-001",
                store_id="STORE-001",
                quantity=1000,
                unit_price=Decimal("100.00")
            )

        assert result.taxable_amount == Decimal("100000.00")
        assert result.total_tax == Decimal("18000.00")
        assert result.total_amount == Decimal("118000.00")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_decimal_unit_price(self, gst_service):
        """Test GST calculation with decimal unit prices"""
        with patch.object(gst_service, 'get_gst_rate_for_product') as mock:
            mock.return_value = ProductGSTInfo(
                product_id="PROD-001",
                gst_rate=Decimal("18"),
                cess_rate=Decimal("0"),
                is_exempt=False
            )

            result = await gst_service.calculate_item_gst(
                product_id="PROD-001",
                store_id="STORE-001",
                quantity=3,
                unit_price=Decimal("33.33")
            )

        # 3 x 33.33 = 99.99
        assert result.taxable_amount == Decimal("99.99")
        # 18% of 99.99 = 18.00 (rounded)
        assert result.total_tax == Decimal("18.00")


# ============================================================================
# TEST: GST Service - Categories API
# ============================================================================

class TestGSTCategoriesAPI:
    """Tests for GST categories listing"""

    @pytest.fixture
    def gst_service(self):
        """Create GST service with mock mode"""
        service = GSTService()
        service.use_mock = True
        return service

    @pytest.mark.unit
    def test_categories_sorted_by_rate(self, gst_service):
        """Test categories are sorted by rate"""
        categories = gst_service.get_all_gst_categories()

        # Should be sorted by rate first
        rates = [c.gst_rate for c in categories]
        assert rates == sorted(rates)

    @pytest.mark.unit
    def test_categories_have_required_fields(self, gst_service):
        """Test all categories have required fields"""
        categories = gst_service.get_all_gst_categories()

        for cat in categories:
            assert cat.code, "Missing code"
            assert cat.name, "Missing name"
            assert cat.hsn_prefix, "Missing HSN prefix"
            assert cat.gst_rate is not None, "Missing GST rate"

    @pytest.mark.unit
    def test_zero_rate_categories_exist(self, gst_service):
        """Test 0% rate categories exist"""
        categories = gst_service.get_all_gst_categories()
        zero_rate = [c for c in categories if c.gst_rate == Decimal("0")]
        assert len(zero_rate) >= 5, "Should have at least 5 zero-rate categories"

    @pytest.mark.unit
    def test_cess_categories_exist(self, gst_service):
        """Test categories with cess exist"""
        categories = gst_service.get_all_gst_categories()
        cess_cats = [c for c in categories if c.cess_rate > 0]
        assert len(cess_cats) >= 1, "Should have at least 1 category with cess"
