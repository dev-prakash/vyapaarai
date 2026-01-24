#!/usr/bin/env python3
"""
Reset Admin Password Script
Safely update admin user password in DynamoDB
"""

import bcrypt
import boto3
from datetime import datetime
import getpass

# DynamoDB setup
dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
users_table = dynamodb.Table('vyaparai-users-prod')

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def reset_password(email: str, new_password: str):
    """Reset password for user"""
    try:
        # Find user by email
        response = users_table.scan(
            FilterExpression='email = :email',
            ExpressionAttributeValues={':email': email}
        )

        if not response.get('Items'):
            print(f"❌ User not found: {email}")
            return False

        user = response['Items'][0]
        user_id = user['id']
        user_role = user.get('role', 'N/A')

        print(f"Found user: {email}")
        print(f"  ID: {user_id}")
        print(f"  Role: {user_role}")
        print(f"  Status: {user.get('status', 'N/A')}")

        # Hash new password
        print("\n🔐 Hashing new password...")
        password_hash = hash_password(new_password)

        # Update password in DynamoDB
        print("💾 Updating password in DynamoDB...")
        users_table.update_item(
            Key={'id': user_id},
            UpdateExpression='SET password_hash = :hash, password_algorithm = :algo, updated_at = :timestamp',
            ExpressionAttributeValues={
                ':hash': password_hash,
                ':algo': 'bcrypt',
                ':timestamp': datetime.utcnow().isoformat()
            }
        )

        print("\n✅ Password updated successfully!")
        print(f"\nYou can now login with:")
        print(f"  Email: {email}")
        print(f"  Password: {new_password}")
        print(f"\nLogin at: https://www.vyapaarai.com/nimdaaccess")

        return True

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return False


if __name__ == '__main__':
    print("=" * 60)
    print("VyapaarAI - Admin Password Reset")
    print("=" * 60)

    # Admin email
    email = input("\nEnter admin email (default: nimda.vai@gmail.com): ").strip()
    if not email:
        email = "nimda.vai@gmail.com"

    # New password (with confirmation)
    while True:
        password1 = getpass.getpass("\nEnter new password (min 8 characters): ")
        if len(password1) < 8:
            print("❌ Password must be at least 8 characters long")
            continue

        password2 = getpass.getpass("Confirm new password: ")
        if password1 != password2:
            print("❌ Passwords do not match")
            continue

        break

    # Confirm action
    print(f"\n⚠️  About to reset password for: {email}")
    confirm = input("Continue? (yes/no): ").strip().lower()

    if confirm != 'yes':
        print("❌ Cancelled")
        exit(0)

    # Reset password
    success = reset_password(email, password1)

    if success:
        exit(0)
    else:
        exit(1)
