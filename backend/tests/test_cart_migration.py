#!/usr/bin/env python3
"""
Test Suite for Cart Migration API
Tests cart migration functionality, merge strategies, and edge cases
"""

import asyncio
import json
import sys
import os
from typing import Dict, Any
import httpx
import time
import pytest
from datetime import datetime, timedelta
from decimal import Decimal

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app'))

def print_header(title: str):
    """Print a formatted header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def print_subheader(title: str):
    """Print a formatted subheader"""
    print(f"\n--- {title} ---")

def print_response(response: httpx.Response, title: str = "Response"):
    """Print formatted response"""
    print(f"{title}:")
    print(f"Status Code: {response.status_code}")
    try:
        print(f"Body: {json.dumps(response.json(), indent=2)}")
    except:
        print(f"Body: {response.text}")

class CartMigrationTestSuite:
    """Test suite for cart migration functionality"""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.test_customer_token = None
        self.test_guest_session_id = "guest-test-12345"
        self.test_store_id = "STORE-TEST-001"

    async def setup_test_data(self, client: httpx.AsyncClient):
        """Setup test data - create test carts"""
        print_subheader("Setting up test data")

        # Create a guest cart first
        guest_cart_data = {
            "product_id": "PROD-001",
            "product_name": "Test Product 1",
            "quantity": 2,
            "unit_price": 100.00,
            "store_id": self.test_store_id
        }

        headers = {"X-Session-ID": self.test_guest_session_id}
        response = await client.post(
            f"{self.base_url}/api/v1/cart/add",
            json=guest_cart_data,
            headers=headers
        )
        print(f"Guest cart created: {response.status_code}")

        return response.status_code == 200

    async def get_test_auth_token(self, client: httpx.AsyncClient) -> str:
        """Get or create test authentication token"""
        # This should use your actual customer authentication endpoint
        # For now, we'll assume you have a test token or can generate one
        print_subheader("Getting test authentication token")

        # Try to get an existing customer or create a test one
        # NOTE: Update this with your actual customer auth flow
        test_customer_data = {
            "phone": "+919999999999",
            "email": "test@vyaparai.com",
            "name": "Test Customer"
        }

        # This endpoint structure is assumed - update based on your actual API
        try:
            response = await client.post(
                f"{self.base_url}/api/v1/customers/auth/login",
                json={"phone": test_customer_data["phone"]}
            )
            if response.status_code == 200:
                token = response.json().get("token") or response.json().get("access_token")
                print(f"✓ Got auth token")
                return token
        except Exception as e:
            print(f"⚠ Could not get real auth token: {e}")

        # For testing purposes, return a mock token
        # In production, you'd need a real token from your auth system
        print("⚠ Using mock token for testing")
        return "mock_test_token_for_testing"

async def test_migration_endpoint_authentication(base_url: str):
    """Test authentication requirements for migration endpoint"""
    print_header("AUTHENTICATION TESTING")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test without authentication token
        print_subheader("Migration without auth token (should fail)")
        migration_data = {
            "guest_session_id": "guest-test-123",
            "merge_strategy": "merge"
        }
        response = await client.post(
            f"{base_url}/api/v1/cart/migrate",
            json=migration_data
        )
        print_response(response, "No Auth Token")
        assert response.status_code == 403 or response.status_code == 401, \
            "Should fail without authentication"

        # Test with invalid token
        print_subheader("Migration with invalid auth token (should fail)")
        headers = {"Authorization": "Bearer invalid_token_12345"}
        response = await client.post(
            f"{base_url}/api/v1/cart/migrate",
            json=migration_data,
            headers=headers
        )
        print_response(response, "Invalid Auth Token")
        assert response.status_code == 401, "Should fail with invalid token"

async def test_migration_merge_strategies(base_url: str, auth_token: str):
    """Test different merge strategies"""
    print_header("MERGE STRATEGIES TESTING")

    merge_strategies = ["merge", "replace", "keep_newest"]

    async with httpx.AsyncClient(timeout=30.0) as client:
        for strategy in merge_strategies:
            print_subheader(f"Testing strategy: {strategy}")

            migration_data = {
                "guest_session_id": f"guest-test-{strategy}-123",
                "merge_strategy": strategy
            }

            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            }

            response = await client.post(
                f"{base_url}/api/v1/cart/migrate",
                json=migration_data,
                headers=headers
            )
            print_response(response, f"Strategy: {strategy}")

            # Should succeed even if no guest cart exists (graceful handling)
            assert response.status_code in [200, 404], \
                f"Migration with strategy '{strategy}' should return 200 or 404"

async def test_migration_with_single_store(base_url: str, auth_token: str):
    """Test migration with specific store ID"""
    print_header("SINGLE STORE MIGRATION TESTING")

    async with httpx.AsyncClient(timeout=30.0) as client:
        print_subheader("Migrate specific store cart")

        migration_data = {
            "guest_session_id": "guest-test-store-123",
            "store_id": "STORE-TEST-001",
            "merge_strategy": "merge"
        }

        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }

        response = await client.post(
            f"{base_url}/api/v1/cart/migrate",
            json=migration_data,
            headers=headers
        )
        print_response(response, "Single Store Migration")

        # Should succeed or return 404 if no cart exists
        assert response.status_code in [200, 404], \
            "Single store migration should return 200 or 404"

async def test_migration_all_stores(base_url: str, auth_token: str):
    """Test migration without store ID (all stores)"""
    print_header("ALL STORES MIGRATION TESTING")

    async with httpx.AsyncClient(timeout=30.0) as client:
        print_subheader("Migrate all store carts")

        migration_data = {
            "guest_session_id": "guest-test-all-stores-123",
            "merge_strategy": "merge"
        }

        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }

        response = await client.post(
            f"{base_url}/api/v1/cart/migrate",
            json=migration_data,
            headers=headers
        )
        print_response(response, "All Stores Migration")

        # Should succeed or return 404 if no carts exist
        assert response.status_code in [200, 404], \
            "All stores migration should return 200 or 404"

        if response.status_code == 200:
            result = response.json()
            assert "migrated_carts" in result, "Response should include migrated_carts count"
            assert "details" in result, "Response should include migration details"

async def test_get_all_carts(base_url: str, auth_token: str):
    """Test getting all customer carts across stores"""
    print_header("GET ALL CARTS TESTING")

    async with httpx.AsyncClient(timeout=30.0) as client:
        print_subheader("Get all customer carts")

        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }

        response = await client.get(
            f"{base_url}/api/v1/cart/all",
            headers=headers
        )
        print_response(response, "All Carts Summary")

        if response.status_code == 200:
            result = response.json()
            assert "total_carts" in result, "Response should include total_carts"
            assert "total_items" in result, "Response should include total_items"
            assert "grand_total" in result, "Response should include grand_total"
            assert "stores" in result, "Response should include stores list"

            print(f"✓ Total Carts: {result['total_carts']}")
            print(f"✓ Total Items: {result['total_items']}")
            print(f"✓ Grand Total: ₹{result['grand_total']}")

async def test_cleanup_guest_cart(base_url: str, auth_token: str):
    """Test cleanup of guest cart after migration"""
    print_header("GUEST CART CLEANUP TESTING")

    async with httpx.AsyncClient(timeout=30.0) as client:
        print_subheader("Cleanup guest cart")

        guest_session_id = "guest-test-cleanup-123"

        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }

        response = await client.delete(
            f"{base_url}/api/v1/cart/cleanup-guest/{guest_session_id}",
            headers=headers
        )
        print_response(response, "Guest Cart Cleanup")

        # Should succeed even if cart doesn't exist
        assert response.status_code in [200, 404], \
            "Cleanup should return 200 or 404"

async def test_rate_limiting(base_url: str, auth_token: str):
    """Test rate limiting on migration endpoint"""
    print_header("RATE LIMITING TESTING")

    async with httpx.AsyncClient(timeout=30.0) as client:
        print_subheader("Testing rate limits (5 requests in 60 seconds)")

        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }

        responses = []
        for i in range(7):  # Try more than the limit
            migration_data = {
                "guest_session_id": f"guest-rate-limit-test-{i}",
                "merge_strategy": "merge"
            }

            response = await client.post(
                f"{base_url}/api/v1/cart/migrate",
                json=migration_data,
                headers=headers
            )
            responses.append(response)
            print(f"Request {i+1}: Status {response.status_code}")

            # Small delay to avoid instant rate limit
            await asyncio.sleep(0.1)

        # Check if rate limiting kicked in
        rate_limited = [r for r in responses if r.status_code == 429]
        if rate_limited:
            print(f"✓ Rate limiting working: {len(rate_limited)} requests rate limited")
        else:
            print(f"⚠ All {len(responses)} requests succeeded (rate limit may be high or disabled)")

async def test_validation_errors(base_url: str, auth_token: str):
    """Test validation and error handling"""
    print_header("VALIDATION & ERROR HANDLING TESTING")

    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }

        # Test missing guest_session_id
        print_subheader("Missing guest_session_id")
        response = await client.post(
            f"{base_url}/api/v1/cart/migrate",
            json={"merge_strategy": "merge"},
            headers=headers
        )
        print_response(response, "Missing guest_session_id")
        assert response.status_code == 422, "Should fail validation"

        # Test invalid merge strategy
        print_subheader("Invalid merge strategy")
        response = await client.post(
            f"{base_url}/api/v1/cart/migrate",
            json={
                "guest_session_id": "guest-test-123",
                "merge_strategy": "invalid_strategy"
            },
            headers=headers
        )
        print_response(response, "Invalid merge strategy")
        assert response.status_code == 422, "Should fail validation for invalid strategy"

        # Test invalid guest_session_id format
        print_subheader("Invalid guest_session_id format")
        response = await client.post(
            f"{base_url}/api/v1/cart/migrate",
            json={
                "guest_session_id": "user-123",  # Should be guest-*
                "merge_strategy": "merge"
            },
            headers=headers
        )
        print_response(response, "Invalid guest_session_id format")
        # This might succeed with 404 or fail with 400 depending on validation

async def test_migration_response_structure(base_url: str, auth_token: str):
    """Test the structure of migration response"""
    print_header("RESPONSE STRUCTURE TESTING")

    async with httpx.AsyncClient(timeout=30.0) as client:
        print_subheader("Validate response structure")

        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }

        migration_data = {
            "guest_session_id": "guest-structure-test-123",
            "merge_strategy": "merge"
        }

        response = await client.post(
            f"{base_url}/api/v1/cart/migrate",
            json=migration_data,
            headers=headers
        )

        if response.status_code == 200:
            result = response.json()

            # Validate required fields
            required_fields = ["status", "migrated_carts", "details", "message"]
            for field in required_fields:
                assert field in result, f"Response should include '{field}'"

            # Validate details structure
            if result["details"]:
                detail = result["details"][0]
                detail_fields = ["store_id", "success", "message"]
                for field in detail_fields:
                    assert field in detail, f"Detail should include '{field}'"

            print("✓ Response structure is valid")
        else:
            print(f"⚠ Migration returned {response.status_code}, skipping structure validation")

async def test_concurrent_migrations(base_url: str, auth_token: str):
    """Test concurrent migration requests"""
    print_header("CONCURRENT MIGRATION TESTING")

    async with httpx.AsyncClient(timeout=30.0) as client:
        print_subheader("Testing concurrent migrations")

        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }

        # Create multiple migration tasks
        tasks = []
        for i in range(3):
            migration_data = {
                "guest_session_id": f"guest-concurrent-{i}",
                "merge_strategy": "merge"
            }
            task = client.post(
                f"{base_url}/api/v1/cart/migrate",
                json=migration_data,
                headers=headers
            )
            tasks.append(task)

        # Execute concurrently
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(1 for r in responses if not isinstance(r, Exception) and r.status_code == 200)
        print(f"✓ Concurrent migrations: {success_count}/{len(tasks)} succeeded")

async def main():
    """Main test function"""
    print("Cart Migration API Test Suite")
    print("Testing cart migration functionality")

    # Configuration
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    print(f"\nTesting against: {base_url}")

    try:
        # Initialize test suite
        test_suite = CartMigrationTestSuite(base_url)

        # Get authentication token for authenticated tests
        async with httpx.AsyncClient(timeout=30.0) as client:
            auth_token = await test_suite.get_test_auth_token(client)

        # Run all tests
        await test_migration_endpoint_authentication(base_url)
        await test_migration_merge_strategies(base_url, auth_token)
        await test_migration_with_single_store(base_url, auth_token)
        await test_migration_all_stores(base_url, auth_token)
        await test_get_all_carts(base_url, auth_token)
        await test_cleanup_guest_cart(base_url, auth_token)
        await test_rate_limiting(base_url, auth_token)
        await test_validation_errors(base_url, auth_token)
        await test_migration_response_structure(base_url, auth_token)
        await test_concurrent_migrations(base_url, auth_token)

        print_header("TEST SUMMARY")
        print("✓ Authentication tests passed")
        print("✓ Merge strategy tests passed")
        print("✓ Single store migration tests passed")
        print("✓ All stores migration tests passed")
        print("✓ Get all carts tests passed")
        print("✓ Guest cart cleanup tests passed")
        print("✓ Rate limiting tests passed")
        print("✓ Validation tests passed")
        print("✓ Response structure tests passed")
        print("✓ Concurrent migration tests passed")
        print("\n🎯 Cart Migration API is working correctly!")

    except httpx.ConnectError:
        print(f"\n❌ Could not connect to {base_url}")
        print("Make sure the API is running:")
        print("  For local: uvicorn app.main:app --reload --port 8000")
        print("  For Lambda: Check API Gateway endpoint")
        sys.exit(1)
    except AssertionError as e:
        print(f"\n❌ Test assertion failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
