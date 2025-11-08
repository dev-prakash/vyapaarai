#!/usr/bin/env python3

import bcrypt

# The stored password hash from DynamoDB
stored_hash = "$2b$12$zBAC2W078EqJNGPgZsY9X.4I/sMzloqVtCF40BS1k0z7xRNydBFsy"
test_password = "Admin123!@#"

print("Testing password verification...")
print(f"Stored hash: {stored_hash}")
print(f"Test password: {test_password}")

# Test password verification
result = bcrypt.checkpw(test_password.encode('utf-8'), stored_hash.encode('utf-8'))
print(f"Password verification result: {result}")

# Also test creating a new hash with the same password
new_hash = bcrypt.hashpw(test_password.encode('utf-8'), bcrypt.gensalt())
print(f"New hash for same password: {new_hash.decode('utf-8')}")

# Verify the new hash works
new_result = bcrypt.checkpw(test_password.encode('utf-8'), new_hash)
print(f"New hash verification result: {new_result}")



