"""
Centralized Input Validation and Sanitization for VyaparAI

Provides:
- String sanitization to prevent XSS and injection attacks
- Phone number validation (Indian format)
- Email validation
- Common validators for Pydantic models
- Input length limits

Usage:
    from app.core.validation import (
        sanitize_string, validate_phone_indian, validate_email,
        PhoneValidator, EmailValidator, SafeStringValidator
    )
"""

import re
import html
import logging
from typing import Optional, Any
from pydantic import validator

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Maximum lengths for various fields
MAX_NAME_LENGTH = 100
MAX_EMAIL_LENGTH = 254
MAX_PHONE_LENGTH = 15
MAX_ADDRESS_LENGTH = 500
MAX_DESCRIPTION_LENGTH = 2000
MAX_MESSAGE_LENGTH = 5000
MAX_SEARCH_QUERY_LENGTH = 200

# Indian phone regex patterns
INDIAN_PHONE_REGEX = re.compile(r'^(?:\+91|91)?[6-9]\d{9}$')
INTERNATIONAL_PHONE_REGEX = re.compile(r'^\+[1-9]\d{1,14}$')

# Email regex (RFC 5322 simplified)
EMAIL_REGEX = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
)

# Dangerous patterns to detect/block
SQL_INJECTION_PATTERNS = [
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|TRUNCATE)\b)",
    r"(--|\#|\/\*|\*\/)",
    r"(\b(OR|AND)\b\s+\d+\s*=\s*\d+)",
]

NOSQL_INJECTION_PATTERNS = [
    r"\$where",
    r"\$gt|\$lt|\$ne|\$eq|\$regex",
    r"\{.*\$.*\}",
]

XSS_PATTERNS = [
    r"<script[^>]*>",
    r"javascript:",
    r"on\w+\s*=",
    r"<iframe[^>]*>",
]


# =============================================================================
# Sanitization Functions
# =============================================================================

def sanitize_string(
    value: str,
    max_length: int = MAX_MESSAGE_LENGTH,
    strip: bool = True,
    escape_html: bool = True,
    allow_newlines: bool = True
) -> str:
    """
    Sanitize a string input to prevent XSS and injection attacks.

    Args:
        value: Input string to sanitize
        max_length: Maximum allowed length
        strip: Whether to strip whitespace
        escape_html: Whether to HTML-escape special characters
        allow_newlines: Whether to preserve newlines

    Returns:
        Sanitized string
    """
    if not value:
        return ""

    if not isinstance(value, str):
        value = str(value)

    # Strip whitespace
    if strip:
        value = value.strip()

    # Truncate to max length
    if len(value) > max_length:
        value = value[:max_length]
        logger.warning(f"Input truncated from {len(value)} to {max_length} characters")

    # Remove null bytes
    value = value.replace('\x00', '')

    # Handle newlines
    if not allow_newlines:
        value = value.replace('\n', ' ').replace('\r', '')

    # HTML escape to prevent XSS
    if escape_html:
        value = html.escape(value, quote=True)

    return value


def sanitize_for_search(query: str) -> str:
    """
    Sanitize a search query string.

    Args:
        query: Search query input

    Returns:
        Sanitized search query
    """
    if not query:
        return ""

    # Basic sanitization
    query = sanitize_string(
        query,
        max_length=MAX_SEARCH_QUERY_LENGTH,
        escape_html=False,  # Don't escape for search
        allow_newlines=False
    )

    # Remove special regex characters that could cause issues
    special_chars = r'[]{}()*+?\\^$|'
    for char in special_chars:
        query = query.replace(char, '')

    return query


def sanitize_html_content(content: str) -> str:
    """
    Sanitize content that may contain HTML.
    Escapes all HTML tags to prevent XSS.

    Args:
        content: Content that may contain HTML

    Returns:
        Sanitized content with escaped HTML
    """
    if not content:
        return ""

    return html.escape(content, quote=True)


def remove_control_characters(value: str) -> str:
    """
    Remove control characters from a string.

    Args:
        value: Input string

    Returns:
        String with control characters removed
    """
    if not value:
        return ""

    # Remove ASCII control characters (except newline, tab)
    return ''.join(
        char for char in value
        if ord(char) >= 32 or char in '\n\t'
    )


# =============================================================================
# Validation Functions
# =============================================================================

def validate_phone_indian(phone: str) -> tuple[bool, str]:
    """
    Validate an Indian phone number.

    Args:
        phone: Phone number to validate

    Returns:
        Tuple of (is_valid, normalized_phone_or_error)
    """
    if not phone:
        return False, "Phone number is required"

    # Remove spaces, dashes, parentheses
    cleaned = re.sub(r'[\s\-\(\)]', '', phone)

    # Check if it matches Indian format
    if INDIAN_PHONE_REGEX.match(cleaned):
        # Normalize to +91 format
        if cleaned.startswith('+91'):
            return True, cleaned
        elif cleaned.startswith('91') and len(cleaned) == 12:
            return True, '+' + cleaned
        else:
            return True, '+91' + cleaned

    # Check international format
    if INTERNATIONAL_PHONE_REGEX.match(cleaned):
        return True, cleaned

    return False, "Invalid phone number format. Use +91XXXXXXXXXX for Indian numbers."


def validate_email(email: str) -> tuple[bool, str]:
    """
    Validate an email address.

    Args:
        email: Email to validate

    Returns:
        Tuple of (is_valid, normalized_email_or_error)
    """
    if not email:
        return False, "Email is required"

    email = email.strip().lower()

    if len(email) > MAX_EMAIL_LENGTH:
        return False, f"Email must be less than {MAX_EMAIL_LENGTH} characters"

    if not EMAIL_REGEX.match(email):
        return False, "Invalid email format"

    return True, email


def check_injection_patterns(value: str) -> tuple[bool, Optional[str]]:
    """
    Check if a string contains potential injection patterns.

    Args:
        value: String to check

    Returns:
        Tuple of (is_safe, detected_pattern_type)
    """
    if not value:
        return True, None

    value_upper = value.upper()

    # Check SQL injection patterns
    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, value_upper, re.IGNORECASE):
            logger.warning(f"Potential SQL injection detected: {pattern}")
            return False, "sql_injection"

    # Check NoSQL injection patterns
    for pattern in NOSQL_INJECTION_PATTERNS:
        if re.search(pattern, value, re.IGNORECASE):
            logger.warning(f"Potential NoSQL injection detected: {pattern}")
            return False, "nosql_injection"

    # Check XSS patterns
    for pattern in XSS_PATTERNS:
        if re.search(pattern, value, re.IGNORECASE):
            logger.warning(f"Potential XSS detected: {pattern}")
            return False, "xss"

    return True, None


def validate_store_id(store_id: str) -> tuple[bool, str]:
    """
    Validate a store ID format.

    Args:
        store_id: Store ID to validate

    Returns:
        Tuple of (is_valid, store_id_or_error)
    """
    if not store_id:
        return False, "Store ID is required"

    store_id = store_id.strip()

    # Check format: alphanumeric with hyphens/underscores
    if not re.match(r'^[A-Za-z0-9_\-]{1,50}$', store_id):
        return False, "Invalid store ID format"

    return True, store_id


def validate_order_id(order_id: str) -> tuple[bool, str]:
    """
    Validate an order ID format.

    Args:
        order_id: Order ID to validate

    Returns:
        Tuple of (is_valid, order_id_or_error)
    """
    if not order_id:
        return False, "Order ID is required"

    order_id = order_id.strip()

    # Check format: UUID or custom format
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    custom_pattern = r'^[A-Za-z0-9_\-]{1,100}$'

    if re.match(uuid_pattern, order_id, re.IGNORECASE) or re.match(custom_pattern, order_id):
        return True, order_id

    return False, "Invalid order ID format"


def validate_quantity(quantity: Any, min_val: int = 1, max_val: int = 10000) -> tuple[bool, int]:
    """
    Validate a quantity value.

    Args:
        quantity: Quantity to validate
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Tuple of (is_valid, quantity_or_error_code)
    """
    try:
        qty = int(quantity)
        if qty < min_val:
            return False, -1  # Below minimum
        if qty > max_val:
            return False, -2  # Above maximum
        return True, qty
    except (ValueError, TypeError):
        return False, 0  # Invalid type


def validate_price(price: Any, max_price: float = 10000000.0) -> tuple[bool, float]:
    """
    Validate a price value.

    Args:
        price: Price to validate
        max_price: Maximum allowed price

    Returns:
        Tuple of (is_valid, price_or_error_code)
    """
    try:
        p = float(price)
        if p < 0:
            return False, -1.0  # Negative price
        if p > max_price:
            return False, -2.0  # Above maximum
        return True, round(p, 2)  # Round to 2 decimal places
    except (ValueError, TypeError):
        return False, 0.0  # Invalid type


# =============================================================================
# Pydantic Validator Helpers
# =============================================================================

def phone_validator(v: str) -> str:
    """Pydantic validator for phone numbers."""
    if not v:
        raise ValueError("Phone number is required")
    is_valid, result = validate_phone_indian(v)
    if not is_valid:
        raise ValueError(result)
    return result


def email_validator(v: str) -> str:
    """Pydantic validator for email addresses."""
    if not v:
        raise ValueError("Email is required")
    is_valid, result = validate_email(v)
    if not is_valid:
        raise ValueError(result)
    return result


def safe_string_validator(
    max_length: int = MAX_MESSAGE_LENGTH,
    allow_empty: bool = False
):
    """
    Factory for safe string validators.

    Usage:
        class MyModel(BaseModel):
            name: str

            _validate_name = validator('name', allow_reuse=True)(
                safe_string_validator(max_length=100)
            )
    """
    def validate(v: str) -> str:
        if not v and not allow_empty:
            raise ValueError("This field cannot be empty")

        if v:
            # Check for injection patterns
            is_safe, threat_type = check_injection_patterns(v)
            if not is_safe:
                raise ValueError(f"Invalid input detected: {threat_type}")

            # Sanitize
            v = sanitize_string(v, max_length=max_length)

        return v

    return validate


def store_id_validator(v: str) -> str:
    """Pydantic validator for store IDs."""
    is_valid, result = validate_store_id(v)
    if not is_valid:
        raise ValueError(result)
    return result


def order_id_validator(v: str) -> str:
    """Pydantic validator for order IDs."""
    is_valid, result = validate_order_id(v)
    if not is_valid:
        raise ValueError(result)
    return result
