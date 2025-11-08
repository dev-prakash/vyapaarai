#!/usr/bin/env python3
"""
Test script for bcrypt security implementation
"""

import sys
import os
import hashlib

# Add the deployment package to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'lambda_deployment_linux'))

from utils.password_service import PasswordService

def test_password_service():
    """Test bcrypt password service"""
    print("🔐 Testing PasswordService...")
    
    password = "SecureAdminPassword123!"
    
    # Test hashing
    print("1. Testing password hashing...")
    hashed = PasswordService.hash_password(password)
    assert hashed != password
    assert len(hashed) > 50  # bcrypt hashes are longer than SHA-256
    print(f"   ✅ Hash generated: {hashed[:20]}...")
    
    # Test verification
    print("2. Testing password verification...")
    assert PasswordService.verify_password(password, hashed)
    assert not PasswordService.verify_password("wrong_password", hashed)
    print("   ✅ Password verification works correctly")
    
    # Test SHA-256 detection
    print("3. Testing SHA-256 detection...")
    sha256_hash = "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3"
    assert PasswordService.is_sha256_hash(sha256_hash)
    assert not PasswordService.is_sha256_hash(hashed)
    print("   ✅ SHA-256 detection works correctly")
    
    # Test password strength validation
    print("4. Testing password strength validation...")
    
    # Test weak passwords
    weak_passwords = [
        ("", "Password cannot be empty"),
        ("123", "Password must be at least 8 characters"),
        ("password", "Password must contain at least one uppercase letter"),
        ("PASSWORD", "Password must contain at least one lowercase letter"),
        ("Password", "Password must contain at least one digit"),
        ("Password123", "Password must contain at least one special character"),
    ]
    
    for weak_pass, expected_error in weak_passwords:
        is_valid, error_msg = PasswordService.validate_password_strength(weak_pass)
        assert not is_valid
        assert expected_error in error_msg
        print(f"   ✅ Correctly rejected weak password: '{weak_pass}' - {error_msg}")
    
    # Test strong password
    is_valid, error_msg = PasswordService.validate_password_strength(password)
    assert is_valid
    print(f"   ✅ Strong password accepted: {error_msg}")
    
    print("🎉 All PasswordService tests passed!")

def test_migration():
    """Test SHA-256 to bcrypt migration"""
    print("\n🔄 Testing SHA-256 to bcrypt migration...")
    
    password = "test_password"
    sha256_hash = hashlib.sha256(password.encode()).hexdigest()
    
    # Test migration
    print("1. Testing migration with correct password...")
    bcrypt_hash = PasswordService.migrate_sha256_to_bcrypt(password, sha256_hash)
    assert bcrypt_hash is not None
    assert PasswordService.verify_password(password, bcrypt_hash)
    print(f"   ✅ Migration successful: {bcrypt_hash[:20]}...")
    
    # Test migration with wrong password
    print("2. Testing migration with wrong password...")
    wrong_bcrypt_hash = PasswordService.migrate_sha256_to_bcrypt("wrong_password", sha256_hash)
    assert wrong_bcrypt_hash is None
    print("   ✅ Migration correctly rejected wrong password")
    
    print("🎉 All migration tests passed!")

def test_performance():
    """Test bcrypt performance"""
    print("\n⚡ Testing bcrypt performance...")
    
    import time
    
    password = "PerformanceTestPassword123!"
    
    # Test hashing time
    start_time = time.time()
    hashed = PasswordService.hash_password(password)
    hash_time = time.time() - start_time
    
    print(f"   Hash time: {hash_time:.3f} seconds")
    assert hash_time < 2.0  # Should be reasonable for cost factor 12
    
    # Test verification time
    start_time = time.time()
    is_valid = PasswordService.verify_password(password, hashed)
    verify_time = time.time() - start_time
    
    print(f"   Verify time: {verify_time:.3f} seconds")
    assert is_valid
    assert verify_time < 1.0  # Verification should be faster than hashing
    
    print("🎉 Performance tests passed!")

def main():
    """Run all tests"""
    print("🚀 Starting bcrypt security tests...\n")
    
    try:
        test_password_service()
        test_migration()
        test_performance()
        
        print("\n🎉 ALL TESTS PASSED! 🎉")
        print("\n✅ bcrypt security implementation is working correctly!")
        print("✅ SHA-256 migration support is functional!")
        print("✅ Password strength validation is working!")
        print("✅ Performance is within acceptable limits!")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()



