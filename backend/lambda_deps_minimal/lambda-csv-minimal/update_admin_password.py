#!/usr/bin/env python3

import boto3
import hashlib

# Initialize DynamoDB client
dynamodb = boto3.client('dynamodb')

# Admin credentials
email = "nimda.vai@gmail.com"
password = "Admin123!@#"

# Hash the password with SHA-256
password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()

print(f"Updating admin password for {email}")
print(f"Password hash: {password_hash}")

# Update the user's password hash
response = dynamodb.update_item(
    TableName='vyaparai-users-prod',
    Key={'id': {'S': f'user_{email}'}},
    UpdateExpression='SET password_hash = :hash',
    ExpressionAttributeValues={
        ':hash': {'S': password_hash}
    }
)

print("Password updated successfully!")
print(f"Response: {response}")



