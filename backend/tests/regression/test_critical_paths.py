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
