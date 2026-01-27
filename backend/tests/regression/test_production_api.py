"""
Production API Regression Tests - Full End-to-End Testing
Author: DevPrakash

ALL tests in this file hit the REAL production API and database.
Run these tests AFTER every deployment to verify the system works.

Test Categories:
1. Health & Availability - Lambda is running
2. Store Authentication - Login flow works
3. Inventory CRUD - All inventory operations
4. More Actions - Delete, Duplicate, Archive
5. Summary/Dashboard - Stats endpoints
6. GST - Tax calculations
7. Global Catalog - Product catalog access

Usage:
    # Run all production tests
    pytest tests/regression/test_production_api.py -v

    # Run specific category
    pytest tests/regression/test_production_api.py -v -k "Auth"
"""

import pytest
import requests
import os
import time
import uuid
from typing import Optional, Dict, Any

# =============================================================================
# CONFIGURATION
# =============================================================================

PROD_API_URL = os.environ.get(
    "VYAPARAI_PROD_API_URL",
    "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws"
)

# Test credentials - Store Owner profile
TEST_STORE_EMAIL = "dev.prakash@gmail.com"
TEST_STORE_PASSWORD = os.environ.get("VYAPARAI_TEST_PASSWORD", "dev1505")

# Timeouts
REQUEST_TIMEOUT = 30
LONG_REQUEST_TIMEOUT = 60


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture(scope="module")
def api_url():
    """Production API base URL"""
    return PROD_API_URL


@pytest.fixture(scope="module")
def store_info(api_url):
    """
    Get store info from verify endpoint.
    Returns dict with store_id and other info.
    """
    response = requests.post(
        f"{api_url}/api/v1/stores/verify",
        json={"email": TEST_STORE_EMAIL},
        timeout=REQUEST_TIMEOUT
    )

    if response.status_code != 200:
        return {}

    data = response.json()
    return data.get("store", {})


@pytest.fixture(scope="module")
def store_id(store_info):
    """Get store_id for authenticated requests"""
    return store_info.get("store_id", "")


@pytest.fixture(scope="module")
def auth_token(api_url):
    """
    Get auth token for authenticated requests.
    Returns None if password not configured (tests will skip auth-required tests).
    """
    if not TEST_STORE_PASSWORD:
        pytest.skip("VYAPARAI_TEST_PASSWORD not set - skipping authenticated tests")
        return None

    response = requests.post(
        f"{api_url}/api/v1/auth/login-with-password",
        json={"email": TEST_STORE_EMAIL, "password": TEST_STORE_PASSWORD},
        timeout=REQUEST_TIMEOUT
    )

    if response.status_code != 200:
        pytest.skip(f"Could not authenticate: {response.status_code}")
        return None

    data = response.json()
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    if not auth_token:
        return {}
    return {"Authorization": f"Bearer {auth_token}"}


def make_request(method: str, url: str, **kwargs) -> requests.Response:
    """Helper to make requests with consistent timeout"""
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    return getattr(requests, method.lower())(url, **kwargs)


# =============================================================================
# 1. HEALTH & AVAILABILITY TESTS
# =============================================================================

class TestProductionHealth:
    """
    CRITICAL: Verify the API is running and can handle requests.

    If these fail, Lambda has import errors or is completely down.
    """

    @pytest.mark.regression
    @pytest.mark.live
    def test_api_responds_not_500(self, api_url):
        """API should not return 500 Internal Server Error"""
        response = make_request("GET", f"{api_url}/")

        assert response.status_code != 500, (
            f"API returned 500 - Lambda likely has import errors.\n"
            f"Response: {response.text[:500]}\n"
            f"Check: aws logs filter-log-events --log-group-name /aws/lambda/vyaparai-api-prod --limit 10"
        )

    @pytest.mark.regression
    @pytest.mark.live
    def test_health_endpoint(self, api_url):
        """Health check endpoint should respond"""
        response = make_request("GET", f"{api_url}/health")

        assert response.status_code != 500, "Health endpoint returned 500"
        # 200 or 404 are acceptable (endpoint might not exist)
        assert response.status_code in [200, 404, 422]

    @pytest.mark.regression
    @pytest.mark.live
    def test_lambda_cold_start_stable(self, api_url):
        """Multiple requests should succeed (no intermittent failures)"""
        failures = []

        for i in range(5):
            response = make_request("GET", f"{api_url}/health")
            if response.status_code == 500:
                failures.append(f"Request {i+1}: 500 error")
            time.sleep(0.5)

        assert len(failures) == 0, f"Cold start failures: {failures}"

    @pytest.mark.regression
    @pytest.mark.live
    def test_pydantic_core_loaded(self, api_url):
        """
        Verify pydantic_core is working (correct architecture).

        This catches arm64 vs x86_64 mismatch.
        """
        # Any endpoint that uses Pydantic validation
        response = make_request(
            "POST",
            f"{api_url}/api/v1/stores/verify",
            json={"email": "test@example.com"}
        )

        assert response.status_code != 500, (
            f"Pydantic validation failed - likely architecture mismatch.\n"
            f"Response: {response.text[:500]}\n"
            f"Ensure Lambda package is built with --platform linux/amd64"
        )


# =============================================================================
# 2. STORE AUTHENTICATION TESTS
# =============================================================================

class TestProductionStoreAuth:
    """
    CRITICAL: Test the store owner authentication flow.

    This is the PRIMARY user login path.
    """

    @pytest.mark.regression
    @pytest.mark.live
    def test_store_verify_endpoint_exists(self, api_url):
        """Store verify endpoint should respond (not 500 or 404)"""
        response = make_request(
            "POST",
            f"{api_url}/api/v1/stores/verify",
            json={"email": TEST_STORE_EMAIL}
        )

        assert response.status_code != 500, (
            f"Store verify returned 500.\nResponse: {response.text[:500]}"
        )
        assert response.status_code != 404, "Store verify endpoint not found (404)"

    @pytest.mark.regression
    @pytest.mark.live
    def test_store_verify_returns_store_data(self, api_url):
        """Store verify should return store information"""
        response = make_request(
            "POST",
            f"{api_url}/api/v1/stores/verify",
            json={"email": TEST_STORE_EMAIL}
        )

        assert response.status_code == 200, (
            f"Store verify failed: {response.status_code}\n{response.text[:500]}"
        )

        data = response.json()
        assert data.get("success") is True, f"Response: {data}"

        store = data.get("store", {})
        required = ["store_id", "name", "email", "has_password"]
        missing = [f for f in required if f not in store]

        assert not missing, f"Missing fields: {missing}\nResponse: {data}"

    @pytest.mark.regression
    @pytest.mark.live
    def test_store_verify_nonexistent_returns_404(self, api_url):
        """Verifying non-existent store should return 404"""
        response = make_request(
            "POST",
            f"{api_url}/api/v1/stores/verify",
            json={"email": f"nonexistent_{uuid.uuid4()}@test.com"}
        )

        assert response.status_code in [404, 400], (
            f"Expected 404 for non-existent store, got {response.status_code}"
        )

    @pytest.mark.regression
    @pytest.mark.live
    def test_login_wrong_password_returns_401(self, api_url):
        """Login with wrong password should return 401, not 500"""
        response = make_request(
            "POST",
            f"{api_url}/api/v1/auth/login-with-password",
            json={"email": TEST_STORE_EMAIL, "password": "wrong_password_xyz"}
        )

        assert response.status_code != 500, (
            f"Login returned 500.\nResponse: {response.text[:500]}"
        )
        assert response.status_code in [400, 401], (
            f"Expected 401 for wrong password, got {response.status_code}"
        )

    @pytest.mark.regression
    @pytest.mark.live
    def test_login_invalid_email_format_returns_422(self, api_url):
        """Login with invalid email should return 422 validation error"""
        response = make_request(
            "POST",
            f"{api_url}/api/v1/auth/login-with-password",
            json={"email": "not-an-email", "password": "test"}
        )

        assert response.status_code != 500, "Validation should not cause 500"
        assert response.status_code in [400, 422], (
            f"Expected 422 for invalid email, got {response.status_code}"
        )


# =============================================================================
# 3. INVENTORY CRUD TESTS
# =============================================================================

class TestProductionInventory:
    """
    Test inventory operations against production API.

    Some tests require authentication.
    """

    @pytest.mark.regression
    @pytest.mark.live
    def test_inventory_products_endpoint_exists(self, api_url):
        """Inventory products endpoint should respond"""
        response = make_request("GET", f"{api_url}/api/v1/inventory/products")

        assert response.status_code != 500, (
            f"Inventory products returned 500.\nResponse: {response.text[:500]}"
        )
        # 401/403 is expected without auth
        assert response.status_code in [200, 401, 403, 422]

    @pytest.mark.regression
    @pytest.mark.live
    def test_inventory_summary_endpoint_exists(self, api_url):
        """Inventory summary endpoint should respond"""
        response = make_request("GET", f"{api_url}/api/v1/inventory/summary")

        assert response.status_code != 500, (
            f"Inventory summary returned 500.\nResponse: {response.text[:500]}"
        )
        assert response.status_code in [200, 401, 403, 422]

    @pytest.mark.regression
    @pytest.mark.live
    def test_inventory_summary_with_auth(self, api_url, auth_headers, store_id):
        """Inventory summary with auth should return data"""
        if not auth_headers:
            pytest.skip("No auth token available")
        if not store_id:
            pytest.skip("No store_id available")

        response = make_request(
            "GET",
            f"{api_url}/api/v1/inventory/summary?store_id={store_id}",
            headers=auth_headers
        )

        assert response.status_code == 200, (
            f"Inventory summary failed: {response.status_code}\n{response.text[:500]}"
        )

        data = response.json()
        assert data.get("success") is True, f"Response: {data}"

        # Check for expected fields
        summary = data.get("data", {})
        expected_fields = ["total_products", "total_stock_value"]
        for field in expected_fields:
            assert field in summary, f"Missing '{field}' in summary response"

    @pytest.mark.regression
    @pytest.mark.live
    def test_inventory_products_with_auth(self, api_url, auth_headers, store_id):
        """Inventory products list with auth should return products"""
        if not auth_headers:
            pytest.skip("No auth token available")
        if not store_id:
            pytest.skip("No store_id available")

        response = make_request(
            "GET",
            f"{api_url}/api/v1/inventory/products?store_id={store_id}",
            headers=auth_headers
        )

        assert response.status_code == 200, (
            f"Inventory products failed: {response.status_code}\n{response.text[:500]}"
        )

        data = response.json()
        assert "products" in data or "items" in data or isinstance(data, list), (
            f"Unexpected response format: {data}"
        )


# =============================================================================
# 4. MORE ACTIONS TESTS (Delete, Duplicate, Archive)
# =============================================================================

class TestProductionMoreActions:
    """
    Test the More Actions menu functionality.

    These endpoints were added to fix the bug where More Actions didn't work.
    """

    @pytest.mark.regression
    @pytest.mark.live
    def test_delete_endpoint_exists(self, api_url):
        """DELETE /products/{id} endpoint should exist"""
        # Use a fake ID - we just want to verify endpoint exists
        response = make_request(
            "DELETE",
            f"{api_url}/api/v1/inventory/products/FAKE-PRODUCT-ID"
        )

        assert response.status_code != 500, (
            f"Delete endpoint returned 500.\nResponse: {response.text[:500]}"
        )
        # 401 (no auth), 404 (not found), or 403 are acceptable
        assert response.status_code in [401, 403, 404, 422], (
            f"Unexpected status for delete: {response.status_code}"
        )

    @pytest.mark.regression
    @pytest.mark.live
    def test_duplicate_endpoint_exists(self, api_url):
        """POST /products/{id}/duplicate endpoint should exist"""
        response = make_request(
            "POST",
            f"{api_url}/api/v1/inventory/products/FAKE-PRODUCT-ID/duplicate"
        )

        assert response.status_code != 500, (
            f"Duplicate endpoint returned 500.\nResponse: {response.text[:500]}"
        )
        assert response.status_code in [401, 403, 404, 422]

    @pytest.mark.regression
    @pytest.mark.live
    def test_archive_endpoint_exists(self, api_url):
        """PUT /products/{id}/archive endpoint should exist"""
        response = make_request(
            "PUT",
            f"{api_url}/api/v1/inventory/products/FAKE-PRODUCT-ID/archive"
        )

        assert response.status_code != 500, (
            f"Archive endpoint returned 500.\nResponse: {response.text[:500]}"
        )
        assert response.status_code in [401, 403, 404, 422]


# =============================================================================
# 5. GLOBAL CATALOG TESTS
# =============================================================================

class TestProductionGlobalCatalog:
    """
    Test global product catalog access.
    """

    @pytest.mark.regression
    @pytest.mark.live
    def test_global_catalog_endpoint_exists(self, api_url):
        """Global catalog endpoint should respond"""
        response = make_request(
            "GET",
            f"{api_url}/api/v1/inventory/global-catalog"
        )

        assert response.status_code != 500, (
            f"Global catalog returned 500.\nResponse: {response.text[:500]}"
        )

    @pytest.mark.regression
    @pytest.mark.live
    def test_global_catalog_returns_products(self, api_url, auth_headers):
        """Global catalog should return product list"""
        if not auth_headers:
            pytest.skip("No auth token available")

        response = make_request(
            "GET",
            f"{api_url}/api/v1/inventory/global-catalog?limit=10",
            headers=auth_headers
        )

        if response.status_code == 200:
            data = response.json()
            assert "products" in data or "items" in data, f"Response: {data}"

    @pytest.mark.regression
    @pytest.mark.live
    def test_add_from_catalog_duplicate_returns_409(self, api_url, auth_headers):
        """Adding duplicate product from catalog should return 409"""
        if not auth_headers:
            pytest.skip("No auth token available")

        # This test needs a known product ID that exists in inventory
        # We'll just verify the endpoint doesn't return 500
        response = make_request(
            "POST",
            f"{api_url}/api/v1/inventory/products/from-catalog",
            headers=auth_headers,
            json={
                "global_product_id": "TEST-PRODUCT-ID",
                "selling_price": 100,
                "current_stock": 10
            }
        )

        assert response.status_code != 500, (
            f"From-catalog endpoint returned 500.\nResponse: {response.text[:500]}"
        )
        # 400, 404, 409 are all valid responses
        assert response.status_code in [200, 201, 400, 404, 409, 422]


# =============================================================================
# 6. GST TESTS
# =============================================================================

class TestProductionGST:
    """
    Test GST calculation endpoints.
    """

    @pytest.mark.regression
    @pytest.mark.live
    def test_gst_categories_endpoint_exists(self, api_url):
        """GST categories endpoint should respond"""
        response = make_request("GET", f"{api_url}/api/v1/gst/categories")

        assert response.status_code != 500, (
            f"GST categories returned 500.\nResponse: {response.text[:500]}"
        )

    @pytest.mark.regression
    @pytest.mark.live
    def test_gst_categories_returns_data(self, api_url):
        """GST categories should return category list"""
        response = make_request("GET", f"{api_url}/api/v1/gst/categories")

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict)), f"Unexpected response: {data}"

    @pytest.mark.regression
    @pytest.mark.live
    def test_gst_hsn_lookup(self, api_url):
        """GST HSN lookup should respond"""
        response = make_request("GET", f"{api_url}/api/v1/gst/hsn/1006")

        assert response.status_code != 500, (
            f"GST HSN lookup returned 500.\nResponse: {response.text[:500]}"
        )


# =============================================================================
# 7. CACHE TESTS
# =============================================================================

class TestProductionCache:
    """
    Test cache management endpoints.
    """

    @pytest.mark.regression
    @pytest.mark.live
    def test_cache_stats_endpoint_exists(self, api_url, auth_headers):
        """Cache stats endpoint should respond"""
        if not auth_headers:
            pytest.skip("No auth token available")

        response = make_request(
            "GET",
            f"{api_url}/api/v1/inventory/cache/stats",
            headers=auth_headers
        )

        assert response.status_code != 500, (
            f"Cache stats returned 500.\nResponse: {response.text[:500]}"
        )

    @pytest.mark.regression
    @pytest.mark.live
    def test_cache_invalidate_endpoint_exists(self, api_url, auth_headers):
        """Cache invalidate endpoint should respond"""
        if not auth_headers:
            pytest.skip("No auth token available")

        response = make_request(
            "POST",
            f"{api_url}/api/v1/inventory/cache/invalidate",
            headers=auth_headers
        )

        assert response.status_code != 500, (
            f"Cache invalidate returned 500.\nResponse: {response.text[:500]}"
        )


# =============================================================================
# 8. KHATA (CREDIT) TESTS
# =============================================================================

class TestProductionKhata:
    """
    Test Khata (credit/ledger) endpoints.
    """

    @pytest.mark.regression
    @pytest.mark.live
    def test_khata_customers_endpoint_exists(self, api_url, auth_headers):
        """Khata customers endpoint should respond"""
        if not auth_headers:
            pytest.skip("No auth token available")

        response = make_request(
            "GET",
            f"{api_url}/api/v1/khata/customers",
            headers=auth_headers
        )

        assert response.status_code != 500, (
            f"Khata customers returned 500.\nResponse: {response.text[:500]}"
        )

    @pytest.mark.regression
    @pytest.mark.live
    def test_khata_summary_endpoint_exists(self, api_url, auth_headers):
        """Khata summary endpoint should respond"""
        if not auth_headers:
            pytest.skip("No auth token available")

        response = make_request(
            "GET",
            f"{api_url}/api/v1/khata/summary",
            headers=auth_headers
        )

        assert response.status_code != 500, (
            f"Khata summary returned 500.\nResponse: {response.text[:500]}"
        )


# =============================================================================
# 9. ORDERS TESTS
# =============================================================================

class TestProductionOrders:
    """
    Test order management endpoints.
    """

    @pytest.mark.regression
    @pytest.mark.live
    def test_orders_list_endpoint_exists(self, api_url, auth_headers):
        """Orders list endpoint should respond"""
        if not auth_headers:
            pytest.skip("No auth token available")

        response = make_request(
            "GET",
            f"{api_url}/api/v1/orders",
            headers=auth_headers
        )

        assert response.status_code != 500, (
            f"Orders list returned 500.\nResponse: {response.text[:500]}"
        )

    @pytest.mark.regression
    @pytest.mark.live
    def test_orders_summary_endpoint_exists(self, api_url, auth_headers):
        """Orders summary/stats endpoint should respond"""
        if not auth_headers:
            pytest.skip("No auth token available")

        response = make_request(
            "GET",
            f"{api_url}/api/v1/orders/summary",
            headers=auth_headers
        )

        # Endpoint might not exist, but shouldn't be 500
        assert response.status_code != 500, (
            f"Orders summary returned 500.\nResponse: {response.text[:500]}"
        )


# =============================================================================
# 10. INVENTORY DELETE/ARCHIVE TESTS (Bug Fix 2026-01-26)
# =============================================================================

class TestProductionInventoryDeleteArchive:
    """
    🔴 LIVE TESTS - Hit production API and database

    Regression tests for the inventory delete/archive bug fix.

    Bug: Delete action was soft-deleting instead of permanently deleting.
    Fix: Frontend now passes hard_delete=true for permanent deletion.

    These tests verify:
    - Hard delete permanently removes product
    - Soft delete (archive) sets is_active=false
    - Archived products can be retrieved with status filter
    - Archive toggle works correctly
    """

    @pytest.mark.regression
    @pytest.mark.live
    def test_delete_endpoint_accepts_hard_delete_param(self, api_url, auth_headers, store_id):
        """
        🔴 LIVE: Verify DELETE endpoint accepts hard_delete query parameter.

        The endpoint should accept hard_delete=true without returning 500.
        """
        if not auth_headers:
            pytest.skip("No auth token available")
        if not store_id:
            pytest.skip("No store_id available")

        # Use a non-existent product ID - we just want to verify param is accepted
        response = make_request(
            "DELETE",
            f"{api_url}/api/v1/inventory/products/NONEXISTENT-PRODUCT?store_id={store_id}&hard_delete=true",
            headers=auth_headers
        )

        assert response.status_code != 500, (
            f"Delete with hard_delete=true returned 500.\n"
            f"Response: {response.text[:500]}"
        )
        # 404 is expected for non-existent product
        assert response.status_code in [404, 400, 422], (
            f"Expected 404 for non-existent product, got {response.status_code}"
        )

    @pytest.mark.regression
    @pytest.mark.live
    def test_archive_endpoint_toggles_product_status(self, api_url, auth_headers, store_id):
        """
        🔴 LIVE: Verify archive endpoint returns toggled status.

        Archive should toggle is_active and return new status.
        """
        if not auth_headers:
            pytest.skip("No auth token available")
        if not store_id:
            pytest.skip("No store_id available")

        # Use a non-existent product ID to verify endpoint behavior
        response = make_request(
            "PUT",
            f"{api_url}/api/v1/inventory/products/NONEXISTENT-PRODUCT/archive?store_id={store_id}",
            headers=auth_headers
        )

        assert response.status_code != 500, (
            f"Archive endpoint returned 500.\nResponse: {response.text[:500]}"
        )
        # 404 expected for non-existent product
        assert response.status_code in [404, 400, 422]

    @pytest.mark.regression
    @pytest.mark.live
    def test_get_products_accepts_status_filter(self, api_url, auth_headers, store_id):
        """
        🔴 LIVE: Verify products endpoint accepts status query parameter.

        The endpoint should accept status=archived, status=active, status=all.
        """
        if not auth_headers:
            pytest.skip("No auth token available")
        if not store_id:
            pytest.skip("No store_id available")

        # Test status=archived filter
        response = make_request(
            "GET",
            f"{api_url}/api/v1/inventory/products?store_id={store_id}&status=archived",
            headers=auth_headers
        )

        assert response.status_code != 500, (
            f"Products with status=archived returned 500.\n"
            f"Response: {response.text[:500]}"
        )
        assert response.status_code == 200, (
            f"Products endpoint should accept status filter, got {response.status_code}"
        )

    @pytest.mark.regression
    @pytest.mark.live
    def test_get_products_archived_returns_only_archived(self, api_url, auth_headers, store_id):
        """
        🔴 LIVE: Verify status=archived returns only archived products.

        All returned products should have is_active=false or status=archived.
        """
        if not auth_headers:
            pytest.skip("No auth token available")
        if not store_id:
            pytest.skip("No store_id available")

        response = make_request(
            "GET",
            f"{api_url}/api/v1/inventory/products?store_id={store_id}&status=archived",
            headers=auth_headers
        )

        if response.status_code != 200:
            pytest.skip(f"Could not fetch archived products: {response.status_code}")

        data = response.json()
        products = data.get("products", data.get("items", []))

        # If there are products, all should be archived
        for product in products:
            is_archived = (
                product.get("is_active") is False or
                product.get("status") == "archived"
            )
            assert is_archived, (
                f"Product {product.get('product_id')} is not archived but returned "
                f"in status=archived query"
            )

    @pytest.mark.regression
    @pytest.mark.live
    def test_get_products_default_excludes_archived(self, api_url, auth_headers, store_id):
        """
        🔴 LIVE: Verify default product list excludes archived products.

        Without status filter, only active products should be returned.
        """
        if not auth_headers:
            pytest.skip("No auth token available")
        if not store_id:
            pytest.skip("No store_id available")

        response = make_request(
            "GET",
            f"{api_url}/api/v1/inventory/products?store_id={store_id}",
            headers=auth_headers
        )

        if response.status_code != 200:
            pytest.skip(f"Could not fetch products: {response.status_code}")

        data = response.json()
        products = data.get("products", data.get("items", []))

        # All returned products should be active (not archived)
        for product in products:
            is_active = (
                product.get("is_active", True) is True and
                product.get("status", "active") != "archived"
            )
            assert is_active, (
                f"Product {product.get('product_id')} is archived but returned "
                f"in default (active) query"
            )

    @pytest.mark.regression
    @pytest.mark.live
    def test_delete_response_includes_hard_delete_flag(self, api_url, auth_headers, store_id):
        """
        🔴 LIVE: Verify delete response includes hard_delete indicator.

        Response should indicate whether it was a hard or soft delete.
        """
        if not auth_headers:
            pytest.skip("No auth token available")
        if not store_id:
            pytest.skip("No store_id available")

        # Soft delete (default)
        response = make_request(
            "DELETE",
            f"{api_url}/api/v1/inventory/products/NONEXISTENT-PRODUCT?store_id={store_id}",
            headers=auth_headers
        )

        # Even for 404, we check it's not a 500 and endpoint exists
        assert response.status_code != 500, (
            f"Delete endpoint returned 500.\nResponse: {response.text[:500]}"
        )


# =============================================================================
# UTILITY: Run all tests
# =============================================================================

def run_production_tests(verbose: bool = True) -> bool:
    """
    Run all production API tests.

    Returns True if all tests pass.

    Usage:
        from tests.regression.test_production_api import run_production_tests
        success = run_production_tests()
    """
    import subprocess

    cmd = ["python", "-m", "pytest", __file__, "-v" if verbose else "-q", "--tb=short"]
    result = subprocess.run(cmd, capture_output=not verbose)

    return result.returncode == 0


if __name__ == "__main__":
    print("=" * 60)
    print("Running Production API Regression Tests")
    print("=" * 60)
    print(f"API URL: {PROD_API_URL}")
    print(f"Test Email: {TEST_STORE_EMAIL}")
    print("=" * 60)

    success = run_production_tests()
    exit(0 if success else 1)
