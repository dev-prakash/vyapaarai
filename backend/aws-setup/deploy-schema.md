# PostgreSQL Schema Deployment Instructions

Since direct connection is timing out, here are alternative ways to deploy the schema:

## Option 1: AWS Console Query Editor
1. Go to AWS RDS Console: https://console.aws.amazon.com/rds/
2. Select your database: vyaparai-postgres-prod
3. Click "Query Editor" 
4. Login with:
   - Database: vyaparai
   - Username: vyaparai_admin
   - Password: Bqa6I0TiBb1T4wSImIcdQeLb06dmUrs9
5. Copy and paste the SQL from:
   - `/backend/database/migrations/create_inventory_schema.sql`
   - `/backend/database/seeds/seed_generic_products.sql`

## Option 2: EC2 Bastion (if you have EC2 access)
1. Launch a small EC2 instance in the same VPC
2. Install psql on it
3. Connect from there (will work since it's in same VPC)

## Option 3: Use Lambda to Deploy
The schema can be deployed through your Lambda function since it's already in the VPC.

## For now, we'll proceed without PostgreSQL
The app will work with DynamoDB for:
- Store registration
- Store login
- Orders

PostgreSQL features (inventory management) can be added later.