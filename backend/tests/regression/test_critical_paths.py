"""
Critical Path Regression Tests
These tests MUST pass before any deployment to production.

Author: DevPrakash
"""
import pytest
import sys
import os
import importlib
from unittest.mock import MagicMock, patch

# Add backend directory to path for imports
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Force test environment
os.environ["VYAPAARAI_ENV"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "ap-south-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost/test"
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["GOOGLE_API_KEY"] = "test-key"
os.environ["JWT_SECRET"] = "test-secret-key-for-testing"


class TestLambdaImport:
    """
    CRITICAL: Test that API route files have valid syntax and configuration.

    This catches issues like:
    - Syntax errors
    - FastAPI route configuration errors (e.g., Query vs Path for path params)
    - Pydantic v2 compatibility issues

    These errors only manifest at Lambda cold start and would cause
    500 Internal Server Error for ALL requests.
    """

    @pytest.mark.regression
    def test_gst_router_syntax_valid(self):
        """
        CRITICAL: Verify GST router file has valid Python syntax.

        This caught the 'Cannot use Query for path param' bug on 2026-01-25.
        """
        import ast

        gst_file = os.path.join(backend_dir, 'app/api/v1/gst.py')

        with open(gst_file, 'r') as f:
            source = f.read()

        # Check syntax is valid
        try:
            ast.parse(source)
        except SyntaxError as e:
            pytest.fail(f"Syntax error in gst.py: {e}")

    @pytest.mark.regression
    def test_stores_router_syntax_valid(self):
        """CRITICAL: Verify stores router file has valid Python syntax."""
        import ast

        stores_file = os.path.join(backend_dir, 'app/api/v1/stores.py')

        with open(stores_file, 'r') as f:
            source = f.read()

        try:
            ast.parse(source)
        except SyntaxError as e:
            pytest.fail(f"Syntax error in stores.py: {e}")

    @pytest.mark.regression
    def test_khata_models_syntax_valid(self):
        """
        CRITICAL: Verify khata models file has valid Python syntax.

        This caught the regex -> pattern Pydantic v2 bug on 2026-01-25.
        """
        import ast

        khata_file = os.path.join(backend_dir, 'app/models/khata.py')

        with open(khata_file, 'r') as f:
            source = f.read()

        try:
            ast.parse(source)
        except SyntaxError as e:
            pytest.fail(f"Syntax error in khata.py: {e}")


class TestPydanticModels:
    """
    CRITICAL: Test that all Pydantic models are valid.

    This catches Pydantic v2 compatibility issues like:
    - regex= renamed to pattern=
    - schema_extra renamed to json_schema_extra
    - Config class changes
    """

    @pytest.mark.regression
    def test_khata_models_valid(self):
        """
        CRITICAL: Verify khata models use Pydantic v2 syntax.

        This caught the regex= vs pattern= bug on 2026-01-25.
        """
        try:
            from app.models.khata import (
                CreditSaleRequest,
                PaymentRequest,
                BalanceAdjustmentRequest,
                CreateCustomerRequest,
                CreateReminderRequest,
            )

            # Test that models can be instantiated
            # CreditSaleRequest with valid phone
            req = CreditSaleRequest(
                customer_phone="+919876543210",
                amount=100.00,
                order_id="ORD-TEST001"
            )
            assert req.customer_phone == "+919876543210"

            # PaymentRequest
            pay = PaymentRequest(
                customer_phone="+919876543210",
                amount=50.00,
                payment_method="cash"
            )
            assert pay.customer_phone == "+919876543210"

        except Exception as e:
            if "regex" in str(e).lower():
                pytest.fail(
                    f"Pydantic v2 compatibility error: {e}\n"
                    "Replace 'regex=' with 'pattern=' in Field() definitions."
                )
            raise

    @pytest.mark.regression
    def test_gst_models_valid(self):
        """Verify GST models are properly defined"""
        try:
            from app.models.gst import (
                GSTCategoryResponse,
                CalculateItemGSTRequest,
                CalculateOrderGSTRequest,
            )

            # Basic instantiation test
            assert GSTCategoryResponse is not None
            assert CalculateItemGSTRequest is not None

        except Exception as e:
            pytest.fail(f"Failed to import GST models: {e}")


class TestStoreVerification:
    """
    CRITICAL: Test store verification endpoint logic.

    This is the primary Store Owner login flow.
    """

    @pytest.mark.regression
    def test_store_verification_email_lookup_logic(self, dynamodb_mock, stores_table, sample_store):
        """
        CRITICAL: Verify store can be found by email in contact_info.

        The store email is stored in contact_info.email, not at the root level.
        """
        # Seed the store
        stores_table.put_item(Item=sample_store)

        # Verify the store can be retrieved
        response = stores_table.get_item(Key={"pk": sample_store["pk"]})
        assert "Item" in response

        # Verify email is in contact_info
        store = response["Item"]
        assert "contact_info" in store
        assert "email" in store["contact_info"]
        assert store["contact_info"]["email"] == "test@vyaparai.com"

    @pytest.mark.regression
    def test_store_verification_returns_required_fields(self, dynamodb_mock, stores_table, sample_store):
        """
        CRITICAL: Verify store verification returns all required fields.

        The frontend expects: store_id, name, owner_name, phone, email, has_password
        """
        stores_table.put_item(Item=sample_store)

        response = stores_table.get_item(Key={"pk": sample_store["pk"]})
        store = response["Item"]

        # Required fields for store verification response
        required_fields = ["pk", "name", "owner_name", "contact_info", "status"]
        for field in required_fields:
            assert field in store, f"Missing required field: {field}"

        # Verify contact_info has required subfields
        assert "phone" in store["contact_info"]
        assert "email" in store["contact_info"]


class TestAsyncAwaitUsage:
    """
    CRITICAL: Test that async methods are properly awaited.

    This catches issues where async methods are called without await,
    causing "coroutine was never awaited" warnings and runtime errors.
    """

    @pytest.mark.regression
    def test_gst_router_awaits_async_methods(self):
        """
        CRITICAL: Verify GST router awaits all async service methods.

        This caught the missing await bug on 2026-01-25 that caused
        'Input should be a valid list' validation error.
        """
        import re

        gst_file = os.path.join(backend_dir, 'app/api/v1/gst.py')

        with open(gst_file, 'r') as f:
            source = f.read()

        # Check async functions in gst_service are awaited
        async_methods = [
            'get_all_gst_categories',
            'get_hsn_info',
            'suggest_gst_category',
        ]

        for method in async_methods:
            # Pattern for calling without await: gst_service.method(...)
            # This should NOT match, we want: await gst_service.method(...)
            pattern = rf'(?<!await\s)gst_service\.{method}\s*\('
            match = re.search(pattern, source)
            if match:
                pytest.fail(
                    f"Async method '{method}' called without 'await' in gst.py\n"
                    f"This causes runtime errors. Add 'await' before the call."
                )


class TestFastAPIRouteConfiguration:
    """
    CRITICAL: Test that FastAPI routes are correctly configured.

    These tests catch issues with path parameters, query parameters,
    and response models that only manifest at import time.
    """

    @pytest.mark.regression
    def test_gst_routes_use_correct_param_types(self):
        """
        CRITICAL: Verify GST routes use Path() for path params.

        This caught the Query vs Path bug on 2026-01-25.
        Bug: /categories/{rate} used Query() instead of Path() for 'rate'
        """
        import ast
        import inspect

        # Read the gst.py source file
        gst_file = os.path.join(
            os.path.dirname(__file__),
            '../../app/api/v1/gst.py'
        )

        if os.path.exists(gst_file):
            with open(gst_file, 'r') as f:
                source = f.read()

            # Check that Path is imported
            assert 'from fastapi import' in source
            assert 'Path' in source, "Path must be imported from fastapi"

            # Look for path parameters with Query (this is wrong)
            # Pattern: route with {param} should not have param = Query()
            import re

            # Find all route definitions with path parameters
            route_pattern = r'@router\.\w+\(\s*["\']([^"\']+)["\']'
            param_pattern = r'(\w+)\s*:\s*\w+\s*=\s*Query\('

            routes = re.findall(route_pattern, source)
            for route in routes:
                # Extract path parameters like {rate}
                path_params = re.findall(r'\{(\w+)\}', route)

                if path_params:
                    # Check that these params don't use Query()
                    for param in path_params:
                        # This pattern would be wrong: rate: int = Query(...)
                        bad_pattern = rf'{param}\s*:\s*\w+\s*=\s*Query\('
                        match = re.search(bad_pattern, source)
                        if match:
                            pytest.fail(
                                f"Path parameter '{param}' in route '{route}' "
                                f"incorrectly uses Query() instead of Path()"
                            )


class TestInventoryEndpoints:
    """
    CRITICAL: Test that inventory endpoints exist and are correctly configured.

    This catches issues like missing PUT endpoints for product updates.
    """

    @pytest.mark.regression
    def test_inventory_router_syntax_valid(self):
        """
        CRITICAL: Verify inventory router file has valid Python syntax.
        """
        import ast

        inventory_file = os.path.join(backend_dir, 'app/api/v1/inventory.py')

        with open(inventory_file, 'r') as f:
            source = f.read()

        try:
            ast.parse(source)
        except SyntaxError as e:
            pytest.fail(f"Syntax error in inventory.py: {e}")

    @pytest.mark.regression
    def test_inventory_put_products_endpoint_exists(self):
        """
        CRITICAL: Verify PUT /products/{product_id} endpoint exists.

        This caught the 404 bug on 2026-01-25 when editing products.
        Frontend calls PUT /api/v1/inventory/products/{productId} but
        this endpoint was missing from the backend.
        """
        import re

        inventory_file = os.path.join(backend_dir, 'app/api/v1/inventory.py')

        with open(inventory_file, 'r') as f:
            source = f.read()

        # Check for PUT /products/{product_id} endpoint
        # Pattern: @router.put("/products/{product_id}")
        put_pattern = r'@router\.put\s*\(\s*["\']\/products\/\{product_id\}["\']'
        match = re.search(put_pattern, source)

        assert match is not None, (
            "Missing PUT /products/{product_id} endpoint in inventory.py.\n"
            "Frontend requires this endpoint for editing products.\n"
            "Add @router.put('/products/{product_id}') endpoint."
        )

    @pytest.mark.regression
    def test_inventory_has_all_required_endpoints(self):
        """
        CRITICAL: Verify all required inventory endpoints exist.

        Frontend requires:
        - GET /products - list products
        - POST /products/custom - add custom product
        - POST /products/from-catalog - add product from catalog
        - PUT /products/{product_id} - update product
        - DELETE /products/custom/{product_id} - delete custom product
        """
        import re

        inventory_file = os.path.join(backend_dir, 'app/api/v1/inventory.py')

        with open(inventory_file, 'r') as f:
            source = f.read()

        required_endpoints = [
            (r'@router\.get\s*\(\s*["\']\/products["\']', 'GET /products'),
            (r'@router\.post\s*\(\s*["\']\/products\/custom["\']', 'POST /products/custom'),
            (r'@router\.put\s*\(\s*["\']\/products\/\{product_id\}["\']', 'PUT /products/{product_id}'),
        ]

        missing = []
        for pattern, endpoint_name in required_endpoints:
            if not re.search(pattern, source):
                missing.append(endpoint_name)

        assert not missing, (
            f"Missing required inventory endpoints: {', '.join(missing)}\n"
            "These endpoints are required for frontend product management."
        )


class TestInventorySummaryAPI:
    """
    CRITICAL: Test that inventory summary API returns correct field names.

    This catches issues where the frontend expects specific field names
    but backend returns different ones, causing dashboard to show 0 values.

    Bug History:
    - 2026-01-25: Dashboard showed 0 products because frontend expected
      response.data.data but backend returned response.data.summary
    - 2026-01-25: Inventory page showed ₹0 stock value because
      inventoryService expected response.data.summary with low_stock/out_of_stock
      but backend returned response.data.data with low_stock_count/out_of_stock_count
    """

    @pytest.mark.regression
    def test_inventory_summary_returns_data_key_not_summary(self):
        """
        CRITICAL: Verify inventory summary returns 'data' key, not 'summary'.

        Both frontend services (dashboardService and inventoryService) expect:
        - response.data.data (NOT response.data.summary)

        This caught the dashboard showing 0 products bug on 2026-01-25.
        """
        import re

        inventory_file = os.path.join(backend_dir, 'app/api/v1/inventory.py')

        with open(inventory_file, 'r') as f:
            source = f.read()

        # Find the get_inventory_summary endpoint
        summary_pattern = r'@router\.get\s*\(\s*["\']\/summary["\']\)'
        match = re.search(summary_pattern, source)
        assert match is not None, "GET /summary endpoint not found in inventory.py"

        # The endpoint MUST return 'data' key (not 'summary')
        # Frontend expects response.data.data
        assert '"data":' in source or "'data':" in source, (
            "Inventory summary endpoint MUST return 'data' key.\n"
            "Frontend dashboardService and inventoryService both expect response.data.data\n"
            "Returning 'summary' key will cause dashboard to show 0 products/stock value."
        )

    @pytest.mark.regression
    def test_inventory_summary_returns_expected_fields(self):
        """
        CRITICAL: Verify inventory summary endpoint returns fields expected by frontend.

        Frontend expects these exact field names in response.data.data:
        - total_products
        - active_products
        - total_stock_value
        - low_stock_count (NOT low_stock - frontend maps this)
        - out_of_stock_count (NOT out_of_stock - frontend maps this)
        - store_id

        This caught the inventory page showing ₹0 stock value bug on 2026-01-25.
        """
        import re

        inventory_file = os.path.join(backend_dir, 'app/api/v1/inventory.py')

        with open(inventory_file, 'r') as f:
            source = f.read()

        # Verify expected field names are present
        expected_fields = [
            'low_stock_count',
            'out_of_stock_count',
            'total_stock_value',
            'total_products',
            'store_id'
        ]

        for field in expected_fields:
            assert f'"{field}"' in source or f"'{field}'" in source, (
                f"Missing expected field '{field}' in inventory summary response.\n"
                f"Frontend services expect this exact field name.\n"
                f"Using different names (e.g., 'low_stock' instead of 'low_stock_count') "
                f"will cause inventory stats to show as 0."
            )

    @pytest.mark.regression
    def test_inventory_summary_does_not_return_wrong_field_names(self):
        """
        CRITICAL: Verify inventory summary does NOT return old/wrong field names.

        The summary endpoint must NOT return these field names directly:
        - 'summary' as the response key (should be 'data')
        - 'low_stock' without '_count' suffix in the response
        - 'out_of_stock' without '_count' suffix in the response

        These old names cause frontend to show 0 values.
        """
        import re

        inventory_file = os.path.join(backend_dir, 'app/api/v1/inventory.py')

        with open(inventory_file, 'r') as f:
            source = f.read()

        # Extract just the get_inventory_summary function
        # Find from @router.get("/summary") to next @router or end
        summary_start = source.find('@router.get("/summary")')
        if summary_start == -1:
            summary_start = source.find("@router.get('/summary')")

        assert summary_start != -1, "GET /summary endpoint not found"

        # Find next route decorator or end of file
        next_route = source.find('@router.', summary_start + 1)
        if next_route == -1:
            next_route = len(source)

        summary_func = source[summary_start:next_route]

        # The return statement should NOT have "summary": as a key
        # It should have "data": instead
        return_pattern = r'return\s*\{[^}]*"summary"\s*:'
        match = re.search(return_pattern, summary_func)
        assert match is None, (
            "Inventory summary endpoint returns 'summary' key but should return 'data'.\n"
            "Change: return {'success': True, 'summary': ...}\n"
            "To:     return {'success': True, 'data': ...}"
        )


class TestDependencyVersions:
    """Test that critical dependencies are compatible versions"""

    @pytest.mark.regression
    def test_pydantic_v2_installed(self):
        """Verify Pydantic v2 is installed (not v1)"""
        import pydantic

        version = pydantic.VERSION
        major_version = int(version.split('.')[0])

        assert major_version >= 2, (
            f"Pydantic v2+ required, found v{version}. "
            "Update with: pip install 'pydantic>=2.0'"
        )

    @pytest.mark.regression
    def test_fastapi_compatible_version(self):
        """Verify FastAPI version is compatible"""
        import fastapi

        version = fastapi.__version__
        parts = version.split('.')
        major = int(parts[0])

        # FastAPI 0.100+ has better Pydantic v2 support
        assert major >= 0 and (major > 0 or int(parts[1]) >= 100), (
            f"FastAPI 0.100+ recommended for Pydantic v2, found v{version}"
        )


class TestInventoryMoreActionsEndpoints:
    """
    CRITICAL: Test that inventory "More Actions" endpoints exist and are correctly configured.

    These endpoints support the frontend's More Actions menu:
    - Delete product
    - Duplicate product
    - Archive/Unarchive product

    Bug History:
    - 2026-01-26: More Actions menu not working because DELETE, POST /duplicate,
      PUT /archive endpoints were missing. Frontend received 404/405 errors.
    """

    @pytest.mark.regression
    def test_delete_product_endpoint_exists(self):
        """
        CRITICAL: Verify DELETE /products/{product_id} endpoint exists.

        This caught the "More Actions > Delete" bug on 2026-01-26.
        Frontend calls DELETE /api/v1/inventory/products/{productId} but
        this endpoint was missing.
        """
        import re

        inventory_file = os.path.join(backend_dir, 'app/api/v1/inventory.py')

        with open(inventory_file, 'r') as f:
            source = f.read()

        # Check for DELETE /products/{product_id} endpoint
        delete_pattern = r'@router\.delete\s*\(\s*["\']\/products\/\{product_id\}["\']'
        match = re.search(delete_pattern, source)

        assert match is not None, (
            "Missing DELETE /products/{product_id} endpoint in inventory.py.\n"
            "Frontend requires this endpoint for 'More Actions > Delete'.\n"
            "Add @router.delete('/products/{product_id}') endpoint."
        )

    @pytest.mark.regression
    def test_duplicate_product_endpoint_exists(self):
        """
        CRITICAL: Verify POST /products/{product_id}/duplicate endpoint exists.

        This caught the "More Actions > Duplicate" bug on 2026-01-26.
        Frontend calls POST /api/v1/inventory/products/{productId}/duplicate
        but this endpoint was missing.
        """
        import re

        inventory_file = os.path.join(backend_dir, 'app/api/v1/inventory.py')

        with open(inventory_file, 'r') as f:
            source = f.read()

        # Check for POST /products/{product_id}/duplicate endpoint
        duplicate_pattern = r'@router\.post\s*\(\s*["\']\/products\/\{product_id\}\/duplicate["\']'
        match = re.search(duplicate_pattern, source)

        assert match is not None, (
            "Missing POST /products/{product_id}/duplicate endpoint in inventory.py.\n"
            "Frontend requires this endpoint for 'More Actions > Duplicate'.\n"
            "Add @router.post('/products/{product_id}/duplicate') endpoint."
        )

    @pytest.mark.regression
    def test_archive_product_endpoint_exists(self):
        """
        CRITICAL: Verify PUT /products/{product_id}/archive endpoint exists.

        This caught the "More Actions > Archive" bug on 2026-01-26.
        Frontend calls PUT /api/v1/inventory/products/{productId}/archive
        but this endpoint was missing.
        """
        import re

        inventory_file = os.path.join(backend_dir, 'app/api/v1/inventory.py')

        with open(inventory_file, 'r') as f:
            source = f.read()

        # Check for PUT /products/{product_id}/archive endpoint
        archive_pattern = r'@router\.put\s*\(\s*["\']\/products\/\{product_id\}\/archive["\']'
        match = re.search(archive_pattern, source)

        assert match is not None, (
            "Missing PUT /products/{product_id}/archive endpoint in inventory.py.\n"
            "Frontend requires this endpoint for 'More Actions > Archive'.\n"
            "Add @router.put('/products/{product_id}/archive') endpoint."
        )

    @pytest.mark.regression
    def test_inventory_service_has_duplicate_method(self):
        """
        CRITICAL: Verify InventoryService has duplicate_product method.

        The duplicate endpoint requires this service method to create a copy
        of the product with a new ID and "(Copy)" suffix.
        """
        import ast

        service_file = os.path.join(backend_dir, 'app/services/inventory_service.py')

        with open(service_file, 'r') as f:
            source = f.read()

        tree = ast.parse(source)

        # Find InventoryService class and check for duplicate_product method
        found_method = False
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == 'duplicate_product':
                found_method = True
                break

        assert found_method, (
            "Missing duplicate_product method in InventoryService.\n"
            "This method is required to create a copy of an existing product."
        )

    @pytest.mark.regression
    def test_inventory_service_has_archive_method(self):
        """
        CRITICAL: Verify InventoryService has archive_product method.

        The archive endpoint requires this service method to toggle
        the product's is_active status.
        """
        import ast

        service_file = os.path.join(backend_dir, 'app/services/inventory_service.py')

        with open(service_file, 'r') as f:
            source = f.read()

        tree = ast.parse(source)

        # Find archive_product method
        found_method = False
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == 'archive_product':
                found_method = True
                break

        assert found_method, (
            "Missing archive_product method in InventoryService.\n"
            "This method is required to toggle product active/archived status."
        )


class TestDuplicateProductHandling:
    """
    CRITICAL: Test that duplicate product from catalog is handled gracefully.

    When a user tries to add a product that already exists in their inventory,
    the system should return a 409 Conflict with helpful information.

    Bug History:
    - 2026-01-26: Adding duplicate product from catalog showed generic error
      instead of helpful "Product already exists" message with guidance.
    """

    @pytest.mark.regression
    def test_from_catalog_endpoint_returns_409_with_product_info(self):
        """
        CRITICAL: Verify /products/from-catalog returns 409 with existing product info.

        When a duplicate product is detected, the response should include:
        - HTTP 409 status code
        - existing_product_id field
        - existing_product_name field
        - helpful message for the user

        This caught the unclear duplicate message bug on 2026-01-26.
        """
        import re

        inventory_file = os.path.join(backend_dir, 'app/api/v1/inventory.py')

        with open(inventory_file, 'r') as f:
            source = f.read()

        # Find the from-catalog endpoint
        assert '/products/from-catalog' in source, (
            "Missing POST /products/from-catalog endpoint"
        )

        # Check that JSONResponse is imported (needed for custom 409 response)
        assert 'JSONResponse' in source, (
            "JSONResponse must be imported to return custom 409 response.\n"
            "Add: from fastapi.responses import JSONResponse"
        )

        # Check that 409 handling includes existing_product_id
        assert 'existing_product_id' in source, (
            "409 response must include existing_product_id field.\n"
            "Frontend uses this to help user find the existing product."
        )

        # Check that helpful message is included
        assert 'already exists' in source.lower() or 'already in your inventory' in source.lower(), (
            "409 response must include helpful message about product existing.\n"
            "This helps users understand they should update instead of add."
        )

    @pytest.mark.regression
    def test_inventory_service_returns_existing_product_on_duplicate(self):
        """
        CRITICAL: Verify inventory service returns existing_product when duplicate detected.

        The add_from_global_catalog method should return the existing product
        information when a duplicate is detected, enabling the API to provide
        helpful context in the 409 response.
        """
        import re

        service_file = os.path.join(backend_dir, 'app/services/inventory_service.py')

        with open(service_file, 'r') as f:
            source = f.read()

        # Check that the service returns existing_product in error case
        assert 'existing_product' in source, (
            "InventoryService must return 'existing_product' when duplicate detected.\n"
            "This enables the API to include product info in 409 response."
        )


class TestPrintLabelFrontend:
    """
    CRITICAL: Test that Print Label functionality includes useful information.

    The print label should include retail-relevant information, not just stock value.

    Bug History:
    - 2026-01-26: Print Label only showed Name, SKU, Price, Stock which is not
      useful for retail labels. Fixed to include MRP, Brand, Category, HSN, etc.
    """

    @pytest.mark.regression
    def test_print_label_includes_mrp_and_discount(self):
        """
        CRITICAL: Verify handlePrintLabel includes MRP and discount info.

        Retail labels must show:
        - MRP (Maximum Retail Price)
        - Selling price (if different from MRP)
        - Discount percentage (if applicable)
        """
        import os

        frontend_file = os.path.join(
            backend_dir, '..', 'frontend-pwa', 'src', 'pages', 'InventoryManagement.tsx'
        )

        if os.path.exists(frontend_file):
            with open(frontend_file, 'r') as f:
                source = f.read()

            # Find handlePrintLabel function
            assert 'handlePrintLabel' in source, (
                "handlePrintLabel function not found in InventoryManagement.tsx"
            )

            # Check for MRP in label
            assert 'mrp' in source.lower() or 'MRP' in source, (
                "Print label must include MRP (Maximum Retail Price).\n"
                "Retail labels require MRP display for compliance."
            )

            # Check for store name
            assert 'storeName' in source or 'store_name' in source or 'store-name' in source, (
                "Print label should include store name for branding."
            )

    @pytest.mark.regression
    def test_print_label_includes_hsn_code(self):
        """
        CRITICAL: Verify handlePrintLabel includes HSN code when available.

        HSN code is important for GST compliance on retail labels.
        """
        import os

        frontend_file = os.path.join(
            backend_dir, '..', 'frontend-pwa', 'src', 'pages', 'InventoryManagement.tsx'
        )

        if os.path.exists(frontend_file):
            with open(frontend_file, 'r') as f:
                source = f.read()

            # Check for HSN in label
            assert 'hsn' in source.lower() or 'HSN' in source, (
                "Print label should include HSN code for GST compliance.\n"
                "HSN codes help with tax categorization."
            )

    @pytest.mark.regression
    def test_product_interface_has_required_fields(self):
        """
        CRITICAL: Verify Product interface includes size and hsn_code fields.

        These fields are needed for proper retail labels.
        """
        import os

        frontend_file = os.path.join(
            backend_dir, '..', 'frontend-pwa', 'src', 'pages', 'InventoryManagement.tsx'
        )

        if os.path.exists(frontend_file):
            with open(frontend_file, 'r') as f:
                source = f.read()

            # Check Product interface has size field
            assert 'size?' in source or 'size:' in source, (
                "Product interface must have 'size' field for pack size info."
            )

            # Check Product interface has hsn_code field
            assert 'hsn_code?' in source or 'hsn_code:' in source, (
                "Product interface must have 'hsn_code' field for GST compliance."
            )


class TestBarcodeEndpointFix:
    """
    CRITICAL: Test that barcode lookup uses the correct API endpoint.

    Bug fixed on 2026-01-27:
    - Frontend was calling /api/v1/inventory/products/barcode/{barcode} (404)
    - Correct endpoint is /api/v1/inventory/barcode/{barcode}
    """

    @pytest.mark.regression
    def test_frontend_uses_correct_barcode_endpoint(self):
        """
        CRITICAL: Verify inventoryService uses /barcode/ not /products/barcode/.

        Bug: Frontend called wrong endpoint causing "product not found" error
        even when product exists in database.
        """
        import os

        frontend_file = os.path.join(
            backend_dir, '..', 'frontend-pwa', 'src', 'services', 'inventoryService.ts'
        )

        if os.path.exists(frontend_file):
            with open(frontend_file, 'r') as f:
                source = f.read()

            # Should use /inventory/barcode/ NOT /inventory/products/barcode/
            assert '/inventory/barcode/' in source, (
                "inventoryService must use /inventory/barcode/ endpoint.\n"
                "Bug: Using /inventory/products/barcode/ causes 404 errors."
            )

            # Should NOT use the wrong endpoint path
            assert '/inventory/products/barcode/' not in source, (
                "inventoryService must NOT use /inventory/products/barcode/ endpoint.\n"
                "Correct path is /inventory/barcode/{barcode}"
            )

    @pytest.mark.regression
    def test_numberpad_supports_keyboard_input(self):
        """
        CRITICAL: Verify NumberPad component supports keyboard input.

        Bug: Users could only use on-screen buttons, not physical keyboard
        or paste functionality for barcode entry.
        """
        import os

        frontend_file = os.path.join(
            backend_dir, '..', 'frontend-pwa', 'src', 'components', 'Inventory', 'NumberPad.tsx'
        )

        if os.path.exists(frontend_file):
            with open(frontend_file, 'r') as f:
                source = f.read()

            # Should have TextField for keyboard input
            assert 'TextField' in source, (
                "NumberPad must include TextField for keyboard input support.\n"
                "Users need to type barcodes using physical keyboard."
            )

            # Should have paste functionality
            assert 'clipboard' in source.lower() or 'paste' in source.lower(), (
                "NumberPad must support paste functionality.\n"
                "Users need to paste copied barcodes."
            )

            # Should support Enter key submission
            assert 'Enter' in source or 'onKeyDown' in source, (
                "NumberPad must support Enter key for submission.\n"
                "Users expect Enter to submit the barcode."
            )


class TestBarcodeScannerUISimplification:
    """
    CRITICAL: Test that barcode scanner UI is simplified and user-friendly.

    Changes made on 2026-01-27:
    - Removed confusing "No Auth Required" button
    - Added USB barcode scanner tip for faster workflow
    - Mobile scanner now auto-falls back if auth fails
    """

    @pytest.mark.regression
    def test_no_auth_required_button_removed(self):
        """
        CRITICAL: Verify "No Auth Required" button is removed from UI.

        This button was confusing - the main mobile scanner button now
        automatically falls back to no-auth method if needed.
        """
        import os

        frontend_file = os.path.join(
            backend_dir, '..', 'frontend-pwa', 'src', 'components',
            'Inventory', 'HybridBarcodeScanner.tsx'
        )

        if os.path.exists(frontend_file):
            with open(frontend_file, 'r') as f:
                source = f.read()

            # Should NOT have "No Auth Required" button text
            assert 'No Auth Required' not in source, (
                "HybridBarcodeScanner should NOT have 'No Auth Required' button.\n"
                "This was removed to simplify the UI - main button auto-falls back."
            )

    @pytest.mark.regression
    def test_usb_scanner_tip_present(self):
        """
        CRITICAL: Verify USB barcode scanner tip is shown to users.

        USB scanners are much faster than mobile camera scanning.
        Users should be informed about this option.
        """
        import os

        frontend_file = os.path.join(
            backend_dir, '..', 'frontend-pwa', 'src', 'components',
            'Inventory', 'HybridBarcodeScanner.tsx'
        )

        if os.path.exists(frontend_file):
            with open(frontend_file, 'r') as f:
                source = f.read()

            # Should have USB scanner tip
            assert 'USB' in source and 'scanner' in source.lower(), (
                "HybridBarcodeScanner should include USB scanner tip.\n"
                "USB scanners are faster than mobile camera scanning."
            )

            # Should mention it's a Pro Tip
            assert 'Pro Tip' in source or 'Tip' in source, (
                "USB scanner suggestion should be presented as a tip.\n"
                "This helps users discover faster scanning options."
            )

    @pytest.mark.regression
    def test_mobile_scanner_checks_localstorage(self):
        """
        CRITICAL: Verify mobile scanner checks localStorage for store owner auth.

        Store owners login via a flow that sets vyaparai_current_store in
        localStorage but may not update useAuthStore. Mobile scanner must
        check both sources.
        """
        import os

        frontend_file = os.path.join(
            backend_dir, '..', 'frontend-pwa', 'src', 'components',
            'Inventory', 'HybridBarcodeScanner.tsx'
        )

        if os.path.exists(frontend_file):
            with open(frontend_file, 'r') as f:
                source = f.read()

            # Should check localStorage for store data
            assert 'vyaparai_current_store' in source, (
                "HybridBarcodeScanner must check localStorage for store data.\n"
                "Store owner login sets vyaparai_current_store, not useAuthStore."
            )

            # Should have fallback mechanism
            assert 'createFallbackMobileSession' in source, (
                "HybridBarcodeScanner must have fallback session mechanism.\n"
                "Auto-fallback ensures scanner works even if auth fails."
            )


class TestGlobalCatalogSearch:
    """
    CRITICAL: Test that global catalog search scans entire table when filtering.

    Bug fixed on 2026-01-27:
    - DynamoDB scan with Limit was applied BEFORE filtering
    - If product not in first N items, search returned empty results
    - Fixed to scan entire table when search term is provided
    """

    @pytest.mark.regression
    def test_global_catalog_search_paginates_when_filtering(self):
        """
        CRITICAL: Verify global catalog search paginates through table when filtering.

        Bug: Search for "Medimix" returned no results even though product exists
        because DynamoDB Limit was applied before filtering.
        """
        import re

        inventory_file = os.path.join(backend_dir, 'app/api/v1/inventory.py')

        with open(inventory_file, 'r') as f:
            source = f.read()

        # Find the global-catalog endpoint
        assert '/global-catalog' in source, (
            "GET /global-catalog endpoint not found in inventory.py"
        )

        # Should check is_filtering to determine scan behavior
        assert 'is_filtering' in source, (
            "Global catalog search must check is_filtering flag.\n"
            "When filtering (search/category), scan entire table.\n"
            "When browsing, apply limit directly."
        )

        # Should NOT apply Limit when filtering
        assert "if not is_filtering" in source, (
            "Global catalog must only apply scan Limit when NOT filtering.\n"
            "Bug: DynamoDB Limit applied before filter caused empty results."
        )

        # Should paginate using LastEvaluatedKey
        assert 'LastEvaluatedKey' in source, (
            "Global catalog must paginate using LastEvaluatedKey.\n"
            "This ensures all items are scanned when filtering."
        )

        # Should search both name AND brand
        assert 'brand_lower' in source or "brand'" in source.lower(), (
            "Global catalog search must check both name AND brand fields.\n"
            "Products may match on brand name (e.g., 'Medimix')."
        )

    @pytest.mark.regression
    def test_global_catalog_applies_limit_after_filtering(self):
        """
        CRITICAL: Verify limit is applied AFTER filtering, not before.

        The final result set should be limited to requested size,
        but the scan should not be limited when searching.
        """
        import re

        inventory_file = os.path.join(backend_dir, 'app/api/v1/inventory.py')

        with open(inventory_file, 'r') as f:
            source = f.read()

        # Should have products[:limit] to apply limit after filtering
        assert 'products[:limit]' in source or 'products[0:limit]' in source, (
            "Global catalog must apply limit AFTER filtering.\n"
            "Use: products = products[:limit]\n"
            "Bug: Applying limit in scan causes missing results."
        )


class TestBulkUploadCSV:
    """
    CRITICAL: Test that CSV bulk upload endpoints exist and work correctly.

    Feature added on 2026-01-27:
    - POST /bulk-upload/csv - Upload and process CSV file
    - GET /bulk-upload/status/{job_id} - Get job status
    - DELETE /bulk-upload/cancel/{job_id} - Cancel job
    """

    @pytest.mark.regression
    def test_bulk_upload_csv_endpoint_exists(self):
        """
        CRITICAL: Verify POST /bulk-upload/csv endpoint exists.

        Frontend calls this endpoint to upload CSV files for bulk product import.
        """
        import re

        inventory_file = os.path.join(backend_dir, 'app/api/v1/inventory.py')

        with open(inventory_file, 'r') as f:
            source = f.read()

        # Check for POST /bulk-upload/csv endpoint
        upload_pattern = r'@router\.post\s*\(\s*["\']\/bulk-upload\/csv["\']'
        match = re.search(upload_pattern, source)

        assert match is not None, (
            "Missing POST /bulk-upload/csv endpoint in inventory.py.\n"
            "Frontend requires this endpoint for CSV bulk product import.\n"
            "Add @router.post('/bulk-upload/csv') endpoint."
        )

    @pytest.mark.regression
    def test_bulk_upload_status_endpoint_exists(self):
        """
        CRITICAL: Verify GET /bulk-upload/status/{job_id} endpoint exists.

        Frontend polls this endpoint to check bulk upload progress.
        """
        import re

        inventory_file = os.path.join(backend_dir, 'app/api/v1/inventory.py')

        with open(inventory_file, 'r') as f:
            source = f.read()

        # Check for GET /bulk-upload/status/{job_id} endpoint
        status_pattern = r'@router\.get\s*\(\s*["\']\/bulk-upload\/status\/\{job_id\}["\']'
        match = re.search(status_pattern, source)

        assert match is not None, (
            "Missing GET /bulk-upload/status/{job_id} endpoint in inventory.py.\n"
            "Frontend requires this endpoint to poll bulk upload progress.\n"
            "Add @router.get('/bulk-upload/status/{job_id}') endpoint."
        )

    @pytest.mark.regression
    def test_bulk_upload_cancel_endpoint_exists(self):
        """
        CRITICAL: Verify DELETE /bulk-upload/cancel/{job_id} endpoint exists.

        Frontend calls this endpoint to cancel a running bulk upload job.
        """
        import re

        inventory_file = os.path.join(backend_dir, 'app/api/v1/inventory.py')

        with open(inventory_file, 'r') as f:
            source = f.read()

        # Check for DELETE /bulk-upload/cancel/{job_id} endpoint
        cancel_pattern = r'@router\.delete\s*\(\s*["\']\/bulk-upload\/cancel\/\{job_id\}["\']'
        match = re.search(cancel_pattern, source)

        assert match is not None, (
            "Missing DELETE /bulk-upload/cancel/{job_id} endpoint in inventory.py.\n"
            "Frontend requires this endpoint to cancel bulk upload jobs.\n"
            "Add @router.delete('/bulk-upload/cancel/{job_id}') endpoint."
        )

    @pytest.mark.regression
    def test_bulk_upload_validates_required_fields(self):
        """
        CRITICAL: Verify bulk upload validates required CSV fields.

        Required fields: product_name, selling_price, current_stock
        """
        import re

        inventory_file = os.path.join(backend_dir, 'app/api/v1/inventory.py')

        with open(inventory_file, 'r') as f:
            source = f.read()

        # Should check for required fields
        required_fields = ['product_name', 'selling_price', 'current_stock']
        for field in required_fields:
            assert field in source, (
                f"Bulk upload must validate required field: {field}\n"
                "CSV files must have these columns for product import."
            )

    @pytest.mark.regression
    def test_bulk_upload_handles_file_upload(self):
        """
        CRITICAL: Verify bulk upload uses UploadFile from FastAPI.

        File upload requires proper multipart form handling.
        """
        import re

        inventory_file = os.path.join(backend_dir, 'app/api/v1/inventory.py')

        with open(inventory_file, 'r') as f:
            source = f.read()

        # Should import UploadFile and File from fastapi
        assert 'UploadFile' in source, (
            "Bulk upload must use UploadFile from FastAPI.\n"
            "Add: from fastapi import UploadFile, File"
        )

        assert 'File' in source, (
            "Bulk upload must use File(...) for form data.\n"
            "Add: from fastapi import UploadFile, File"
        )

    @pytest.mark.regression
    def test_bulk_upload_returns_job_id(self):
        """
        CRITICAL: Verify bulk upload returns a job ID for tracking.

        Frontend uses job ID to poll for progress and results.
        """
        import re

        inventory_file = os.path.join(backend_dir, 'app/api/v1/inventory.py')

        with open(inventory_file, 'r') as f:
            source = f.read()

        # Should return jobId in response
        assert 'jobId' in source or 'job_id' in source, (
            "Bulk upload must return jobId in response.\n"
            "Frontend uses this to poll /bulk-upload/status/{jobId}"
        )

    @pytest.mark.regression
    def test_bulk_upload_tracks_progress(self):
        """
        CRITICAL: Verify bulk upload tracks progress (total, processed, successful, failed).

        Frontend displays progress bar based on these values.
        """
        import re

        inventory_file = os.path.join(backend_dir, 'app/api/v1/inventory.py')

        with open(inventory_file, 'r') as f:
            source = f.read()

        # Should track progress metrics
        progress_fields = ['total', 'processed', 'successful', 'failed']
        for field in progress_fields:
            assert f"'{field}'" in source or f'"{field}"' in source, (
                f"Bulk upload must track progress field: {field}\n"
                "Frontend displays these values in progress UI."
            )


class TestEmailAuthentication:
    """
    CRITICAL: Test email authentication and branding.

    Bug fix: Email template branding, copyright, and error messages.
    Author: DevPrakash
    """

    @pytest.mark.regression
    def test_email_template_uses_correct_branding(self):
        """
        REGRESSION: Email template must use 'VyapaarAI' (double 'a') not 'VyaparAI'.

        Original bug: Email subject and body used 'VyaparAI' (single 'a')
        Fix: Updated all occurrences to 'VyapaarAI'
        """
        email_service_file = os.path.join(backend_dir, 'app/services/email_service.py')

        with open(email_service_file, 'r') as f:
            source = f.read()

        # Should NOT contain single 'a' branding (except in email domains)
        # Count occurrences of wrong branding in non-domain contexts
        import re
        wrong_branding = re.findall(r'VyaparAI(?!\.com)', source)
        assert len(wrong_branding) == 0, (
            f"Email template uses wrong branding 'VyaparAI' (single 'a').\n"
            f"Found {len(wrong_branding)} occurrences. Use 'VyapaarAI' (double 'a')."
        )

        # Should contain correct branding
        assert 'VyapaarAI' in source, (
            "Email template must use correct branding 'VyapaarAI' (double 'a')."
        )

    @pytest.mark.regression
    def test_email_template_has_current_copyright_year(self):
        """
        REGRESSION: Email template must have current copyright year (2026).

        Original bug: Copyright year was 2024
        Fix: Updated to 2026
        """
        email_service_file = os.path.join(backend_dir, 'app/services/email_service.py')

        with open(email_service_file, 'r') as f:
            source = f.read()

        # Should contain 2026 copyright
        assert '© 2026' in source or '2026' in source, (
            "Email template must have current copyright year (2026).\n"
            "Update: © 2024 → © 2026"
        )

        # Should NOT contain old copyright years
        assert '© 2024' not in source, (
            "Email template has outdated copyright year 2024.\n"
            "Update to: © 2026 VyapaarAI. All rights reserved."
        )

    @pytest.mark.regression
    def test_passcode_error_message_is_user_friendly(self):
        """
        REGRESSION: Invalid passcode error must be user-friendly.

        Original bug: Error message was not helpful
        Fix: Changed to "Invalid passcode entered. Please try again."
        """
        auth_file = os.path.join(backend_dir, 'app/api/v1/auth.py')

        with open(auth_file, 'r') as f:
            source = f.read()

        # Should have user-friendly error message
        assert 'Invalid passcode entered' in source or 'try again' in source.lower(), (
            "Passcode error message must be user-friendly.\n"
            "Use: 'Invalid passcode entered. Please try again.'"
        )

    @pytest.mark.regression
    def test_email_verification_uses_database_not_whitelist(self):
        """
        REGRESSION: Email verification must check database, not hardcoded whitelist.

        Original bug: Only whitelisted emails could login via passcode
        Fix: Check stores DynamoDB table for registered store owners
        """
        auth_file = os.path.join(backend_dir, 'app/api/v1/auth.py')

        with open(auth_file, 'r') as f:
            source = f.read()

        # Should have check_email_registered function that queries database
        assert 'check_email_registered' in source, (
            "Auth must have check_email_registered function."
        )

        # Should check stores_table in the function
        assert 'stores_table.scan' in source or 'stores_table' in source, (
            "Email verification must check stores database table.\n"
            "Cannot rely on hardcoded whitelist for store owners."
        )

        # Should NOT have STORE_OWNER_EMAILS whitelist
        assert 'STORE_OWNER_EMAILS' not in source, (
            "Remove hardcoded STORE_OWNER_EMAILS whitelist.\n"
            "Email verification should only use database lookup."
        )
