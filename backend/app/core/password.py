"""
Password Hashing Utilities for VyaparAI

Provides secure password hashing using bcrypt with configurable work factor.
All password operations should use this module for consistency and security.

Security Features:
- bcrypt algorithm (designed for password hashing)
- Automatic salt generation (built into bcrypt)
- Configurable work factor (cost parameter)
- Timing-safe comparison (built into bcrypt.checkpw)

Usage:
    from app.core.password import hash_password, verify_password

    # Hash a new password
    hashed = hash_password("user_password")

    # Verify password
    is_valid = verify_password("user_password", hashed)
"""

import bcrypt
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Bcrypt work factor (cost parameter)
# Higher = more secure but slower
# 12 is recommended for production (takes ~250ms)
# 10 is acceptable for development (takes ~65ms)
# Range: 4-31 (4 is minimum, 31 takes hours)
BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "12"))

# Validate work factor
if BCRYPT_ROUNDS < 10:
    logger.warning(f"BCRYPT_ROUNDS={BCRYPT_ROUNDS} is below recommended minimum of 10")
if BCRYPT_ROUNDS > 14:
    logger.warning(f"BCRYPT_ROUNDS={BCRYPT_ROUNDS} may cause slow performance")


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password to hash

    Returns:
        Bcrypt hash string (includes algorithm, cost, salt, and hash)

    Raises:
        ValueError: If password is empty or too long (>72 bytes for bcrypt)
    """
    if not password:
        raise ValueError("Password cannot be empty")

    # bcrypt has a 72 byte limit
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        logger.warning("Password exceeds 72 bytes, will be truncated by bcrypt")

    # Generate salt and hash
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(password_bytes, salt)

    # Return as string for storage
    return hashed.decode('utf-8')


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verify a password against a bcrypt hash.

    Args:
        password: Plain text password to verify
        hashed_password: Bcrypt hash to verify against

    Returns:
        True if password matches, False otherwise

    Note:
        This function is timing-safe (bcrypt.checkpw uses constant-time comparison)
    """
    if not password or not hashed_password:
        return False

    try:
        password_bytes = password.encode('utf-8')
        hash_bytes = hashed_password.encode('utf-8')

        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def is_password_hashed_with_bcrypt(hashed: str) -> bool:
    """
    Check if a password hash is bcrypt format.

    Bcrypt hashes start with $2a$, $2b$, or $2y$

    Args:
        hashed: Hash string to check

    Returns:
        True if bcrypt format, False otherwise
    """
    if not hashed:
        return False
    return hashed.startswith(('$2a$', '$2b$', '$2y$'))


def needs_rehash(hashed_password: str) -> bool:
    """
    Check if a password hash needs to be rehashed.

    Reasons to rehash:
    - Not bcrypt (e.g., old SHA-256 hash)
    - Work factor is lower than current BCRYPT_ROUNDS

    Args:
        hashed_password: Existing hash to check

    Returns:
        True if should be rehashed, False otherwise
    """
    if not hashed_password:
        return True

    # Check if it's bcrypt
    if not is_password_hashed_with_bcrypt(hashed_password):
        return True

    # Check work factor (format: $2b$12$...)
    try:
        parts = hashed_password.split('$')
        if len(parts) >= 3:
            current_rounds = int(parts[2])
            return current_rounds < BCRYPT_ROUNDS
    except (ValueError, IndexError):
        return True

    return False


def migrate_sha256_to_bcrypt(password: str, old_hash: str) -> Optional[str]:
    """
    Migrate a SHA-256 hashed password to bcrypt.

    This is a helper for migrating existing users. Call this during login
    when the user provides their password.

    Args:
        password: Plain text password (from user input)
        old_hash: Old SHA-256 hash (format: hash$salt)

    Returns:
        New bcrypt hash if old hash verified, None if verification failed
    """
    # Verify against old SHA-256 format
    try:
        import hashlib
        pwd_hash, salt = old_hash.split('$')
        if hashlib.sha256((password + salt).encode()).hexdigest() == pwd_hash:
            # Password verified, create new bcrypt hash
            logger.info("Migrating password from SHA-256 to bcrypt")
            return hash_password(password)
    except Exception as e:
        logger.error(f"SHA-256 migration error: {e}")

    return None


def get_password_strength(password: str) -> dict:
    """
    Basic password strength check.

    Args:
        password: Password to check

    Returns:
        Dictionary with strength info
    """
    if not password:
        return {"score": 0, "feedback": "Password is empty"}

    score = 0
    feedback = []

    # Length checks
    if len(password) >= 8:
        score += 1
    else:
        feedback.append("Use at least 8 characters")

    if len(password) >= 12:
        score += 1

    # Character variety
    if any(c.isupper() for c in password):
        score += 1
    else:
        feedback.append("Add uppercase letters")

    if any(c.islower() for c in password):
        score += 1
    else:
        feedback.append("Add lowercase letters")

    if any(c.isdigit() for c in password):
        score += 1
    else:
        feedback.append("Add numbers")

    if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        score += 1
    else:
        feedback.append("Add special characters")

    # Score interpretation
    strength = "weak"
    if score >= 5:
        strength = "strong"
    elif score >= 3:
        strength = "medium"

    return {
        "score": score,
        "max_score": 6,
        "strength": strength,
        "feedback": feedback if feedback else ["Password meets requirements"]
    }
