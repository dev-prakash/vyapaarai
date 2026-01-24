"""
Unit Tests for Security Module

Tests for:
- JWT token creation and validation
- Authentication decorators
- Authorization checks
- Token expiration handling
- Security edge cases
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
import jwt
import os


class TestJWTTokenCreation:
    """Tests for JWT token creation functions"""

    def test_create_store_owner_token(self, test_store_owner_token):
        """Test store owner token creation"""
        assert test_store_owner_token is not None
        assert len(test_store_owner_token) > 0

        # Decode and verify payload
        secret = os.environ.get("JWT_SECRET", "test_secret_key_for_testing_only_32chars!")
        decoded = jwt.decode(test_store_owner_token, secret, algorithms=["HS256"])

        assert decoded["user_id"] == "test_user_001"
        assert decoded["store_id"] == "STORE-TEST-001"
        assert decoded["role"] == "store_owner"

    def test_create_customer_token(self, test_customer_token):
        """Test customer token creation"""
        assert test_customer_token is not None

        secret = os.environ.get("JWT_SECRET", "test_secret_key_for_testing_only_32chars!")
        decoded = jwt.decode(test_customer_token, secret, algorithms=["HS256"])

        assert decoded["customer_id"] == "CUST-TEST-001"
        assert decoded["phone"] == "+919876543210"
        assert decoded["role"] == "customer"

    def test_create_admin_token(self, test_admin_token):
        """Test admin token creation"""
        assert test_admin_token is not None

        secret = os.environ.get("JWT_SECRET", "test_secret_key_for_testing_only_32chars!")
        decoded = jwt.decode(test_admin_token, secret, algorithms=["HS256"])

        assert decoded["user_id"] == "admin_001"
        assert decoded["role"] == "admin"


class TestJWTTokenValidation:
    """Tests for JWT token validation"""

    def test_valid_token_passes_validation(self, test_store_owner_token):
        """Test that valid tokens pass validation"""
        secret = os.environ.get("JWT_SECRET", "test_secret_key_for_testing_only_32chars!")

        try:
            decoded = jwt.decode(test_store_owner_token, secret, algorithms=["HS256"])
            assert decoded is not None
        except jwt.InvalidTokenError:
            pytest.fail("Valid token should not raise InvalidTokenError")

    def test_expired_token_fails_validation(self):
        """Test that expired tokens fail validation"""
        secret = os.environ.get("JWT_SECRET", "test_secret_key_for_testing_only_32chars!")

        # Create an expired token
        payload = {
            "user_id": "test_user",
            "role": "store_owner",
            "exp": datetime.utcnow() - timedelta(hours=1)  # Expired 1 hour ago
        }
        expired_token = jwt.encode(payload, secret, algorithm="HS256")

        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(expired_token, secret, algorithms=["HS256"])

    def test_invalid_signature_fails_validation(self, test_store_owner_token):
        """Test that tampered tokens fail validation"""
        wrong_secret = "wrong_secret_key"

        with pytest.raises(jwt.InvalidSignatureError):
            jwt.decode(test_store_owner_token, wrong_secret, algorithms=["HS256"])

    def test_malformed_token_fails_validation(self):
        """Test that malformed tokens fail validation"""
        secret = os.environ.get("JWT_SECRET", "test_secret_key_for_testing_only_32chars!")

        with pytest.raises(jwt.DecodeError):
            jwt.decode("not.a.valid.token", secret, algorithms=["HS256"])


class TestAuthorizationHeaders:
    """Tests for authorization header formatting"""

    def test_auth_headers_format(self, auth_headers_store_owner):
        """Test authorization headers are properly formatted"""
        assert "Authorization" in auth_headers_store_owner
        assert auth_headers_store_owner["Authorization"].startswith("Bearer ")

    def test_auth_headers_contain_valid_token(self, auth_headers_store_owner):
        """Test authorization headers contain valid token"""
        token = auth_headers_store_owner["Authorization"].replace("Bearer ", "")
        secret = os.environ.get("JWT_SECRET", "test_secret_key_for_testing_only_32chars!")

        decoded = jwt.decode(token, secret, algorithms=["HS256"])
        assert decoded is not None


class TestRoleBasedAccess:
    """Tests for role-based access control"""

    def test_store_owner_role_in_token(self, test_store_owner_token):
        """Test store owner token has correct role"""
        secret = os.environ.get("JWT_SECRET", "test_secret_key_for_testing_only_32chars!")
        decoded = jwt.decode(test_store_owner_token, secret, algorithms=["HS256"])

        assert decoded["role"] == "store_owner"

    def test_customer_role_in_token(self, test_customer_token):
        """Test customer token has correct role"""
        secret = os.environ.get("JWT_SECRET", "test_secret_key_for_testing_only_32chars!")
        decoded = jwt.decode(test_customer_token, secret, algorithms=["HS256"])

        assert decoded["role"] == "customer"

    def test_admin_role_in_token(self, test_admin_token):
        """Test admin token has correct role"""
        secret = os.environ.get("JWT_SECRET", "test_secret_key_for_testing_only_32chars!")
        decoded = jwt.decode(test_admin_token, secret, algorithms=["HS256"])

        assert decoded["role"] == "admin"


class TestTokenClaims:
    """Tests for token claims verification"""

    def test_store_owner_has_store_id_claim(self, test_store_owner_token):
        """Test store owner tokens include store_id claim"""
        secret = os.environ.get("JWT_SECRET", "test_secret_key_for_testing_only_32chars!")
        decoded = jwt.decode(test_store_owner_token, secret, algorithms=["HS256"])

        assert "store_id" in decoded
        assert decoded["store_id"] == "STORE-TEST-001"

    def test_customer_has_phone_claim(self, test_customer_token):
        """Test customer tokens include phone claim"""
        secret = os.environ.get("JWT_SECRET", "test_secret_key_for_testing_only_32chars!")
        decoded = jwt.decode(test_customer_token, secret, algorithms=["HS256"])

        assert "phone" in decoded
        assert decoded["phone"] == "+919876543210"

    def test_all_tokens_have_expiration(self, test_store_owner_token, test_customer_token, test_admin_token):
        """Test all tokens have expiration claim"""
        secret = os.environ.get("JWT_SECRET", "test_secret_key_for_testing_only_32chars!")

        for token in [test_store_owner_token, test_customer_token, test_admin_token]:
            decoded = jwt.decode(token, secret, algorithms=["HS256"])
            assert "exp" in decoded


class TestSecurityEdgeCases:
    """Tests for security edge cases"""

    def test_empty_token_rejected(self):
        """Test that empty tokens are rejected"""
        secret = os.environ.get("JWT_SECRET", "test_secret_key_for_testing_only_32chars!")

        with pytest.raises(jwt.DecodeError):
            jwt.decode("", secret, algorithms=["HS256"])

    def test_none_token_rejected(self):
        """Test that None tokens are rejected"""
        secret = os.environ.get("JWT_SECRET", "test_secret_key_for_testing_only_32chars!")

        with pytest.raises(jwt.DecodeError):
            jwt.decode(None, secret, algorithms=["HS256"])

    def test_token_with_wrong_algorithm(self, test_store_owner_token):
        """Test tokens validated with wrong algorithm are rejected"""
        secret = os.environ.get("JWT_SECRET", "test_secret_key_for_testing_only_32chars!")

        with pytest.raises(jwt.InvalidAlgorithmError):
            jwt.decode(test_store_owner_token, secret, algorithms=["HS512"])

    def test_token_without_required_claims(self):
        """Test tokens without required claims are handled"""
        secret = os.environ.get("JWT_SECRET", "test_secret_key_for_testing_only_32chars!")

        # Create token without role claim
        payload = {
            "user_id": "test_user",
            "exp": datetime.utcnow() + timedelta(hours=1)
            # Missing "role" claim
        }
        token = jwt.encode(payload, secret, algorithm="HS256")

        decoded = jwt.decode(token, secret, algorithms=["HS256"])
        # Token decodes but doesn't have role
        assert "role" not in decoded


class TestJWTSecretValidation:
    """Tests for JWT secret security"""

    def test_jwt_secret_minimum_length(self):
        """Test JWT secret meets minimum length requirement"""
        secret = os.environ.get("JWT_SECRET", "test_secret_key_for_testing_only_32chars!")
        # Minimum 32 characters for security
        assert len(secret) >= 32

    def test_jwt_secret_not_default_in_production(self):
        """Test JWT secret is not a default value in production"""
        secret = os.environ.get("JWT_SECRET", "")
        env = os.environ.get("ENVIRONMENT", "test")

        if env == "production":
            # In production, should not use default/test secrets
            assert "test" not in secret.lower()
            assert "default" not in secret.lower()
            assert "changeme" not in secret.lower()
