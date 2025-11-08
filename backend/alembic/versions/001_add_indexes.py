"""Add database indexes for performance

Revision ID: 001
Create Date: 2024-01-20
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Orders table indexes
    op.create_index('idx_orders_store_created', 'orders', ['store_id', 'created_at'])
    op.create_index('idx_orders_customer_phone', 'orders', ['customer_phone'])
    op.create_index('idx_orders_status', 'orders', ['status'])
    op.create_index('idx_orders_date', 'orders', ['created_at'])
    op.create_index('idx_orders_payment_method', 'orders', ['payment_method'])
    
    # Customers table indexes
    op.create_index('idx_customers_phone', 'customers', ['phone'])
    op.create_index('idx_customers_store', 'customers', ['store_id'])
    op.create_index('idx_customers_name', 'customers', ['name'])
    op.create_index('idx_customers_email', 'customers', ['email'])
    op.create_index('idx_customers_created_at', 'customers', ['created_at'])
    
    # Products table indexes
    op.create_index('idx_products_barcode', 'products', ['barcode'])
    op.create_index('idx_products_store_category', 'products', ['store_id', 'category'])
    op.create_index('idx_products_low_stock', 'products', ['store_id', 'current_stock'])
    op.create_index('idx_products_name', 'products', ['name'])
    op.create_index('idx_products_brand', 'products', ['brand'])
    op.create_index('idx_products_is_active', 'products', ['is_active'])
    
    # Stock transactions table indexes
    op.create_index('idx_stock_transactions_product', 'stock_transactions', ['product_id'])
    op.create_index('idx_stock_transactions_store', 'stock_transactions', ['store_id'])
    op.create_index('idx_stock_transactions_created', 'stock_transactions', ['created_at'])
    op.create_index('idx_stock_transactions_operation', 'stock_transactions', ['operation'])
    
    # Customer credit transactions table indexes
    op.create_index('idx_customer_credit_customer', 'customer_credit_transactions', ['customer_id'])
    op.create_index('idx_customer_credit_store', 'customer_credit_transactions', ['store_id'])
    op.create_index('idx_customer_credit_created', 'customer_credit_transactions', ['created_at'])
    op.create_index('idx_customer_credit_type', 'customer_credit_transactions', ['transaction_type'])
    
    # Product categories table indexes
    op.create_index('idx_product_categories_store', 'product_categories', ['store_id'])
    op.create_index('idx_product_categories_name', 'product_categories', ['name'])
    op.create_index('idx_product_categories_parent', 'product_categories', ['parent_category_id'])
    
    # Purchase orders table indexes
    op.create_index('idx_purchase_orders_store', 'purchase_orders', ['store_id'])
    op.create_index('idx_purchase_orders_status', 'purchase_orders', ['status'])
    op.create_index('idx_purchase_orders_created', 'purchase_orders', ['created_at'])
    op.create_index('idx_purchase_orders_supplier', 'purchase_orders', ['supplier_name'])
    
    # Purchase order items table indexes
    op.create_index('idx_purchase_order_items_po', 'purchase_order_items', ['purchase_order_id'])
    op.create_index('idx_purchase_order_items_product', 'purchase_order_items', ['product_id'])
    
    # Users table indexes
    op.create_index('idx_users_store', 'users', ['store_id'])
    op.create_index('idx_users_phone', 'users', ['phone'])
    op.create_index('idx_users_role', 'users', ['role'])
    
    # Stores table indexes
    op.create_index('idx_stores_owner_phone', 'stores', ['owner_phone'])
    op.create_index('idx_stores_is_active', 'stores', ['is_active'])

def downgrade():
    # Drop indexes in reverse order
    # Stores
    op.drop_index('idx_stores_is_active')
    op.drop_index('idx_stores_owner_phone')
    
    # Users
    op.drop_index('idx_users_role')
    op.drop_index('idx_users_phone')
    op.drop_index('idx_users_store')
    
    # Purchase order items
    op.drop_index('idx_purchase_order_items_product')
    op.drop_index('idx_purchase_order_items_po')
    
    # Purchase orders
    op.drop_index('idx_purchase_orders_supplier')
    op.drop_index('idx_purchase_orders_created')
    op.drop_index('idx_purchase_orders_status')
    op.drop_index('idx_purchase_orders_store')
    
    # Product categories
    op.drop_index('idx_product_categories_parent')
    op.drop_index('idx_product_categories_name')
    op.drop_index('idx_product_categories_store')
    
    # Customer credit transactions
    op.drop_index('idx_customer_credit_type')
    op.drop_index('idx_customer_credit_created')
    op.drop_index('idx_customer_credit_store')
    op.drop_index('idx_customer_credit_customer')
    
    # Stock transactions
    op.drop_index('idx_stock_transactions_operation')
    op.drop_index('idx_stock_transactions_created')
    op.drop_index('idx_stock_transactions_store')
    op.drop_index('idx_stock_transactions_product')
    
    # Products
    op.drop_index('idx_products_is_active')
    op.drop_index('idx_products_brand')
    op.drop_index('idx_products_name')
    op.drop_index('idx_products_low_stock')
    op.drop_index('idx_products_store_category')
    op.drop_index('idx_products_barcode')
    
    # Customers
    op.drop_index('idx_customers_created_at')
    op.drop_index('idx_customers_email')
    op.drop_index('idx_customers_name')
    op.drop_index('idx_customers_store')
    op.drop_index('idx_customers_phone')
    
    # Orders
    op.drop_index('idx_orders_payment_method')
    op.drop_index('idx_orders_date')
    op.drop_index('idx_orders_status')
    op.drop_index('idx_orders_customer_phone')
    op.drop_index('idx_orders_store_created')

