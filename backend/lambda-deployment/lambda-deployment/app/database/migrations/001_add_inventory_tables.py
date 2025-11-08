"""Add inventory management tables"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid
from datetime import datetime

def upgrade():
    # Create products table
    op.create_table(
        'products',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('store_id', sa.String(50), nullable=False, default='STORE-001'),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('category', sa.String(100), nullable=False),
        sa.Column('subcategory', sa.String(100)),
        sa.Column('price', sa.Decimal(10, 2), nullable=False),
        sa.Column('mrp', sa.Decimal(10, 2)),
        sa.Column('cost_price', sa.Decimal(10, 2)),
        sa.Column('current_stock', sa.Integer(), default=0),
        sa.Column('min_stock_level', sa.Integer(), default=10),
        sa.Column('max_stock_level', sa.Integer(), default=1000),
        sa.Column('unit', sa.String(20), default='piece'),
        sa.Column('brand', sa.String(100)),
        sa.Column('barcode', sa.String(50)),
        sa.Column('sku', sa.String(50)),
        sa.Column('status', sa.String(20), default='active'),
        sa.Column('is_featured', sa.Boolean(), default=False),
        sa.Column('is_available', sa.Boolean(), default=True),
        sa.Column('supplier_name', sa.String(200)),
        sa.Column('supplier_contact', sa.String(50)),
        sa.Column('supplier_email', sa.String(100)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now())
    )
    
    # Create stock movements table
    op.create_table(
        'stock_movements',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('product_id', sa.String(50), nullable=False),
        sa.Column('store_id', sa.String(50), nullable=False, default='STORE-001'),
        sa.Column('movement_type', sa.String(20), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('previous_stock', sa.Integer(), nullable=False),
        sa.Column('new_stock', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(200)),
        sa.Column('reference_id', sa.String(50)),
        sa.Column('reference_type', sa.String(50)),
        sa.Column('created_by', sa.String(100)),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )
    
    # Add indexes for better performance
    op.create_index('idx_products_store_id', 'products', ['store_id'])
    op.create_index('idx_products_category', 'products', ['category'])
    op.create_index('idx_products_status', 'products', ['status'])
    op.create_index('idx_stock_movements_product_id', 'stock_movements', ['product_id'])
    op.create_index('idx_stock_movements_store_id', 'stock_movements', ['store_id'])
    op.create_index('idx_stock_movements_created_at', 'stock_movements', ['created_at'])
    
    # Add sample products
    op.execute("""
        INSERT INTO products (id, name, description, category, subcategory, price, mrp, cost_price, current_stock, min_stock_level, max_stock_level, unit, brand, sku, status, supplier_name) VALUES
        ('prod-001', 'Basmati Rice 1kg', 'Premium quality basmati rice', 'Grains', 'Rice', 150.00, 180.00, 120.00, 50, 10, 200, 'kg', 'Royal', 'RICE-BASMATI-1KG', 'active', 'Grain Suppliers Ltd'),
        ('prod-002', 'Toor Dal 1kg', 'Organic toor dal', 'Pulses', 'Dal', 120.00, 140.00, 90.00, 30, 5, 100, 'kg', 'Organic', 'PULSE-TOOR-1KG', 'active', 'Organic Foods'),
        ('prod-003', 'Sunflower Oil 1L', 'Pure sunflower cooking oil', 'Oil', 'Cooking Oil', 180.00, 200.00, 150.00, 25, 8, 80, 'liter', 'Nature Fresh', 'OIL-SUNFLOWER-1L', 'active', 'Oil Distributors'),
        ('prod-004', 'Turmeric Powder 100g', 'Pure turmeric powder', 'Spices', 'Powder', 45.00, 50.00, 35.00, 40, 10, 150, 'packet', 'Spice Master', 'SPICE-TURMERIC-100G', 'active', 'Spice Traders'),
        ('prod-005', 'Onions 1kg', 'Fresh red onions', 'Vegetables', 'Root Vegetables', 35.00, 40.00, 25.00, 2, 5, 50, 'kg', 'Fresh Farm', 'VEG-ONION-1KG', 'active', 'Local Farmers'),
        ('prod-006', 'Tomatoes 1kg', 'Fresh red tomatoes', 'Vegetables', 'Fruits', 45.00, 50.00, 30.00, 0, 5, 40, 'kg', 'Fresh Farm', 'VEG-TOMATO-1KG', 'active', 'Local Farmers'),
        ('prod-007', 'Wheat Flour 2kg', 'Whole wheat flour', 'Grains', 'Flour', 80.00, 90.00, 60.00, 15, 8, 100, 'kg', 'Aashirvaad', 'GRAIN-WHEAT-2KG', 'active', 'Flour Mills'),
        ('prod-008', 'Sugar 1kg', 'Refined white sugar', 'Essentials', 'Sweeteners', 45.00, 50.00, 35.00, 60, 10, 150, 'kg', 'Tata', 'ESS-SUGAR-1KG', 'active', 'Sugar Suppliers'),
        ('prod-009', 'Salt 1kg', 'Iodized table salt', 'Essentials', 'Seasonings', 20.00, 25.00, 15.00, 80, 10, 200, 'kg', 'Tata', 'ESS-SALT-1KG', 'active', 'Salt Traders'),
        ('prod-010', 'Milk 1L', 'Fresh cow milk', 'Dairy', 'Milk', 60.00, 65.00, 45.00, 10, 5, 30, 'liter', 'Amul', 'DAIRY-MILK-1L', 'active', 'Dairy Farm')
    """)
    
    # Add initial stock movements for sample products
    op.execute("""
        INSERT INTO stock_movements (id, product_id, movement_type, quantity, previous_stock, new_stock, reason, reference_type, created_by) VALUES
        ('mov-001', 'prod-001', 'in', 50, 0, 50, 'Initial stock', 'initial', 'system'),
        ('mov-002', 'prod-002', 'in', 30, 0, 30, 'Initial stock', 'initial', 'system'),
        ('mov-003', 'prod-003', 'in', 25, 0, 25, 'Initial stock', 'initial', 'system'),
        ('mov-004', 'prod-004', 'in', 40, 0, 40, 'Initial stock', 'initial', 'system'),
        ('mov-005', 'prod-005', 'in', 20, 0, 20, 'Initial stock', 'initial', 'system'),
        ('mov-006', 'prod-006', 'in', 15, 0, 15, 'Initial stock', 'initial', 'system'),
        ('mov-007', 'prod-007', 'in', 15, 0, 15, 'Initial stock', 'initial', 'system'),
        ('mov-008', 'prod-008', 'in', 60, 0, 60, 'Initial stock', 'initial', 'system'),
        ('mov-009', 'prod-009', 'in', 80, 0, 80, 'Initial stock', 'initial', 'system'),
        ('mov-010', 'prod-010', 'in', 10, 0, 10, 'Initial stock', 'initial', 'system'),
        ('mov-011', 'prod-005', 'out', 18, 20, 2, 'Sales', 'order', 'system'),
        ('mov-012', 'prod-006', 'out', 15, 15, 0, 'Sales', 'order', 'system')
    """)

def downgrade():
    # Drop indexes
    op.drop_index('idx_products_store_id', 'products')
    op.drop_index('idx_products_category', 'products')
    op.drop_index('idx_products_status', 'products')
    op.drop_index('idx_stock_movements_product_id', 'stock_movements')
    op.drop_index('idx_stock_movements_store_id', 'stock_movements')
    op.drop_index('idx_stock_movements_created_at', 'stock_movements')
    
    # Drop tables
    op.drop_table('stock_movements')
    op.drop_table('products')
