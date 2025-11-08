-- Inventory Management Database Schema
-- Version: 1.0
-- Description: Comprehensive inventory management system for VyaparAI

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- 1. CORE PRODUCT HIERARCHY
-- ============================================

-- Categories & Subcategories (Hierarchical)
CREATE TABLE IF NOT EXISTS categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    parent_id UUID REFERENCES categories(id) ON DELETE CASCADE,
    level INTEGER NOT NULL DEFAULT 0,
    icon_url VARCHAR(500),
    display_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_categories_parent ON categories(parent_id);
CREATE INDEX idx_categories_active ON categories(is_active);

-- Brand Master
CREATE TABLE IF NOT EXISTS brands (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL UNIQUE,
    logo_url VARCHAR(500),
    manufacturer VARCHAR(300),
    country_of_origin VARCHAR(100),
    is_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_brands_name ON brands(name);
CREATE INDEX idx_brands_verified ON brands(is_verified);

-- Generic Product Catalog (Master/Template Products)
CREATE TABLE IF NOT EXISTS generic_products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    category_id UUID REFERENCES categories(id),
    subcategory_id UUID REFERENCES categories(id),
    product_type VARCHAR(50) CHECK (product_type IN ('grocery', 'personal_care', 'household', 'pharmacy', 'electronics', 'other')),
    hsn_code VARCHAR(20), -- HSN/SAC code for GST in India
    default_unit VARCHAR(20) CHECK (default_unit IN ('kg', 'g', 'l', 'ml', 'piece', 'pack', 'dozen', 'box', 'bottle', 'can')),
    searchable_keywords TEXT[],
    attributes_template JSONB, -- Defines what attributes this product type should have
    typical_sizes TEXT[], -- Common sizes for this product
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_generic_products_category ON generic_products(category_id);
CREATE INDEX idx_generic_products_name ON generic_products(name);
CREATE INDEX idx_generic_products_keywords ON generic_products USING GIN(searchable_keywords);
CREATE INDEX idx_generic_products_active ON generic_products(is_active);

-- ============================================
-- 2. STORE-SPECIFIC PRODUCT INVENTORY
-- ============================================

-- Store's Actual Products (SKU Level)
CREATE TABLE IF NOT EXISTS store_products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_id UUID NOT NULL, -- From stores table
    generic_product_id UUID REFERENCES generic_products(id),
    sku VARCHAR(100) NOT NULL,
    barcode VARCHAR(100),
    product_name VARCHAR(300) NOT NULL,
    brand_id UUID REFERENCES brands(id),
    
    -- Variants & Specifications
    variant_type VARCHAR(100), -- e.g., "Basmati", "Sona Masoori" for rice
    size DECIMAL(10,3),
    size_unit VARCHAR(20),
    color VARCHAR(50),
    flavor VARCHAR(50),
    
    -- Pricing
    mrp DECIMAL(10,2),
    cost_price DECIMAL(10,2),
    selling_price DECIMAL(10,2) NOT NULL,
    tax_rate DECIMAL(5,2) DEFAULT 0, -- GST percentage
    discount_percentage DECIMAL(5,2) DEFAULT 0,
    
    -- Stock Management
    current_stock DECIMAL(10,3) DEFAULT 0,
    reserved_stock DECIMAL(10,3) DEFAULT 0, -- For pending orders
    min_stock_level DECIMAL(10,3) DEFAULT 0,
    max_stock_level DECIMAL(10,3) DEFAULT 1000,
    reorder_point DECIMAL(10,3) DEFAULT 10,
    reorder_quantity DECIMAL(10,3) DEFAULT 50,
    
    -- Product Details
    description TEXT,
    ingredients TEXT,
    nutritional_info JSONB,
    manufacturer_details JSONB,
    packaging_type VARCHAR(100),
    shelf_life_days INTEGER,
    storage_instructions TEXT,
    
    -- Compliance & Certifications
    fssai_license VARCHAR(100), -- Food Safety India
    certifications TEXT[],
    country_of_origin VARCHAR(100),
    
    -- Status & Metadata
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'discontinued', 'out_of_stock')),
    is_returnable BOOLEAN DEFAULT true,
    is_perishable BOOLEAN DEFAULT false,
    requires_prescription BOOLEAN DEFAULT false,
    weight_in_grams DECIMAL(10,2), -- For shipping calculations
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_stock_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(store_id, sku),
    CONSTRAINT positive_stock CHECK (current_stock >= 0),
    CONSTRAINT positive_price CHECK (selling_price > 0)
);

CREATE INDEX idx_store_products_store ON store_products(store_id);
CREATE INDEX idx_store_products_generic ON store_products(store_id, generic_product_id);
CREATE INDEX idx_store_products_status ON store_products(store_id, status);
CREATE INDEX idx_store_products_barcode ON store_products(barcode);
CREATE INDEX idx_store_products_brand ON store_products(brand_id);
CREATE INDEX idx_store_products_name ON store_products(product_name);

-- Computed column for available stock
ALTER TABLE store_products 
ADD COLUMN available_stock DECIMAL(10,3) 
GENERATED ALWAYS AS (current_stock - reserved_stock) STORED;

-- Product Images
CREATE TABLE IF NOT EXISTS product_images (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_product_id UUID REFERENCES store_products(id) ON DELETE CASCADE,
    image_url VARCHAR(500) NOT NULL,
    image_type VARCHAR(20) CHECK (image_type IN ('primary', 'secondary', 'nutrition_label', 'ingredient_list')),
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_product_images_product ON product_images(store_product_id);

-- ============================================
-- 3. INVENTORY TRACKING & MOVEMENT
-- ============================================

-- Stock Movements/Ledger
CREATE TABLE IF NOT EXISTS stock_movements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_product_id UUID REFERENCES store_products(id) ON DELETE CASCADE,
    movement_type VARCHAR(20) CHECK (movement_type IN ('purchase', 'sale', 'return', 'adjustment', 'damage', 'expiry', 'transfer')),
    quantity DECIMAL(10,3) NOT NULL, -- Positive for IN, negative for OUT
    balance_after DECIMAL(10,3) NOT NULL,
    reference_type VARCHAR(50), -- e.g., 'purchase_order', 'sales_order', 'manual_adjustment'
    reference_id VARCHAR(100),
    reason TEXT,
    performed_by UUID, -- user_id
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_stock_movements_product ON stock_movements(store_product_id, created_at DESC);
CREATE INDEX idx_stock_movements_type ON stock_movements(movement_type);
CREATE INDEX idx_stock_movements_reference ON stock_movements(reference_type, reference_id);

-- Batch/Lot Tracking (for expiry management)
CREATE TABLE IF NOT EXISTS product_batches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_product_id UUID REFERENCES store_products(id) ON DELETE CASCADE,
    batch_number VARCHAR(100) NOT NULL,
    quantity DECIMAL(10,3) NOT NULL,
    remaining_quantity DECIMAL(10,3) NOT NULL,
    manufacture_date DATE,
    expiry_date DATE,
    supplier_id UUID, -- References suppliers table
    purchase_price DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT positive_batch_quantity CHECK (remaining_quantity >= 0)
);

CREATE INDEX idx_product_batches_product ON product_batches(store_product_id);
CREATE INDEX idx_product_batches_expiry ON product_batches(expiry_date);
CREATE INDEX idx_product_batches_number ON product_batches(batch_number);

-- ============================================
-- 4. SUPPLIER & PURCHASE MANAGEMENT
-- ============================================

-- Suppliers
CREATE TABLE IF NOT EXISTS suppliers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_id UUID NOT NULL,
    name VARCHAR(200) NOT NULL,
    contact_person VARCHAR(100),
    phone VARCHAR(20),
    email VARCHAR(100),
    address TEXT,
    gstin VARCHAR(20), -- GST Number
    payment_terms VARCHAR(100),
    delivery_lead_time_days INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_suppliers_store ON suppliers(store_id);
CREATE INDEX idx_suppliers_active ON suppliers(store_id, is_active);

-- Purchase Orders
CREATE TABLE IF NOT EXISTS purchase_orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_id UUID NOT NULL,
    supplier_id UUID REFERENCES suppliers(id),
    order_number VARCHAR(100) UNIQUE NOT NULL,
    order_date DATE DEFAULT CURRENT_DATE,
    expected_delivery DATE,
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'sent', 'partial', 'received', 'cancelled')),
    total_amount DECIMAL(10,2),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_purchase_orders_store ON purchase_orders(store_id);
CREATE INDEX idx_purchase_orders_supplier ON purchase_orders(supplier_id);
CREATE INDEX idx_purchase_orders_status ON purchase_orders(status);
CREATE INDEX idx_purchase_orders_number ON purchase_orders(order_number);

-- Purchase Order Items
CREATE TABLE IF NOT EXISTS purchase_order_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    purchase_order_id UUID REFERENCES purchase_orders(id) ON DELETE CASCADE,
    store_product_id UUID REFERENCES store_products(id),
    quantity_ordered DECIMAL(10,3) NOT NULL,
    quantity_received DECIMAL(10,3) DEFAULT 0,
    unit_price DECIMAL(10,2) NOT NULL,
    tax_amount DECIMAL(10,2) DEFAULT 0,
    total_amount DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_po_items_order ON purchase_order_items(purchase_order_id);
CREATE INDEX idx_po_items_product ON purchase_order_items(store_product_id);

-- ============================================
-- 5. PRICE HISTORY & OFFERS
-- ============================================

-- Price History
CREATE TABLE IF NOT EXISTS price_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_product_id UUID REFERENCES store_products(id) ON DELETE CASCADE,
    old_price DECIMAL(10,2),
    new_price DECIMAL(10,2),
    price_type VARCHAR(20) CHECK (price_type IN ('mrp', 'cost_price', 'selling_price')),
    changed_by UUID,
    reason VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_price_history_product ON price_history(store_product_id, created_at DESC);

-- Product Offers/Promotions
CREATE TABLE IF NOT EXISTS product_offers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_id UUID NOT NULL,
    store_product_id UUID REFERENCES store_products(id) ON DELETE CASCADE,
    offer_type VARCHAR(20) CHECK (offer_type IN ('percentage', 'flat', 'bogo', 'bundle')),
    offer_value DECIMAL(10,2),
    min_quantity INTEGER DEFAULT 1,
    max_discount DECIMAL(10,2),
    valid_from TIMESTAMP,
    valid_until TIMESTAMP,
    terms_conditions TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_product_offers_store ON product_offers(store_id);
CREATE INDEX idx_product_offers_product ON product_offers(store_product_id);
CREATE INDEX idx_product_offers_active ON product_offers(is_active, valid_from, valid_until);

-- ============================================
-- 6. ANALYTICS & REPORTING TABLES
-- ============================================

-- Inventory Snapshots (for historical tracking)
CREATE TABLE IF NOT EXISTS inventory_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_id UUID NOT NULL,
    snapshot_date DATE NOT NULL,
    total_products INTEGER,
    total_stock_value DECIMAL(12,2),
    low_stock_items INTEGER,
    out_of_stock_items INTEGER,
    snapshot_data JSONB, -- Detailed breakdown
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(store_id, snapshot_date)
);

CREATE INDEX idx_inventory_snapshots_store ON inventory_snapshots(store_id, snapshot_date DESC);

-- Product Performance Metrics
CREATE TABLE IF NOT EXISTS product_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_product_id UUID REFERENCES store_products(id) ON DELETE CASCADE,
    period DATE NOT NULL,
    units_sold DECIMAL(10,3),
    revenue DECIMAL(10,2),
    profit_margin DECIMAL(5,2),
    stock_turnover_ratio DECIMAL(5,2),
    days_inventory_outstanding INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(store_product_id, period)
);

CREATE INDEX idx_product_metrics_product ON product_metrics(store_product_id, period DESC);

-- ============================================
-- 7. TRIGGERS FOR AUTOMATIC UPDATES
-- ============================================

-- Function to update timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply update trigger to relevant tables
CREATE TRIGGER update_categories_updated_at BEFORE UPDATE ON categories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_brands_updated_at BEFORE UPDATE ON brands
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_generic_products_updated_at BEFORE UPDATE ON generic_products
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_store_products_updated_at BEFORE UPDATE ON store_products
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_suppliers_updated_at BEFORE UPDATE ON suppliers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_purchase_orders_updated_at BEFORE UPDATE ON purchase_orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to track stock movements
CREATE OR REPLACE FUNCTION track_stock_movement()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.current_stock != NEW.current_stock THEN
        INSERT INTO stock_movements (
            store_product_id,
            movement_type,
            quantity,
            balance_after,
            reference_type,
            reason
        ) VALUES (
            NEW.id,
            'adjustment',
            NEW.current_stock - OLD.current_stock,
            NEW.current_stock,
            'direct_update',
            'Stock updated directly'
        );
        NEW.last_stock_update = CURRENT_TIMESTAMP;
    END IF;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER track_stock_changes AFTER UPDATE ON store_products
    FOR EACH ROW EXECUTE FUNCTION track_stock_movement();

-- ============================================
-- 8. VIEWS FOR COMMON QUERIES
-- ============================================

-- View for products with low stock
CREATE OR REPLACE VIEW low_stock_products AS
SELECT 
    sp.*,
    b.name as brand_name,
    gp.name as generic_product_name,
    c.name as category_name
FROM store_products sp
LEFT JOIN brands b ON sp.brand_id = b.id
LEFT JOIN generic_products gp ON sp.generic_product_id = gp.id
LEFT JOIN categories c ON gp.category_id = c.id
WHERE sp.current_stock <= sp.min_stock_level
AND sp.status = 'active';

-- View for product inventory summary
CREATE OR REPLACE VIEW inventory_summary AS
SELECT 
    sp.store_id,
    COUNT(DISTINCT sp.id) as total_products,
    SUM(sp.current_stock * sp.selling_price) as total_stock_value,
    COUNT(CASE WHEN sp.current_stock = 0 THEN 1 END) as out_of_stock_count,
    COUNT(CASE WHEN sp.current_stock <= sp.min_stock_level AND sp.current_stock > 0 THEN 1 END) as low_stock_count
FROM store_products sp
WHERE sp.status = 'active'
GROUP BY sp.store_id;

-- ============================================
-- 9. SEED DATA FOR GENERIC PRODUCTS
-- ============================================

-- Insert sample categories
INSERT INTO categories (id, name, parent_id, level, display_order) VALUES
(uuid_generate_v4(), 'Grocery', NULL, 0, 1),
(uuid_generate_v4(), 'Personal Care', NULL, 0, 2),
(uuid_generate_v4(), 'Household', NULL, 0, 3),
(uuid_generate_v4(), 'Pharmacy', NULL, 0, 4),
(uuid_generate_v4(), 'Beverages', NULL, 0, 5)
ON CONFLICT DO NOTHING;

-- Insert subcategories (will need parent_id from above)
WITH grocery_cat AS (SELECT id FROM categories WHERE name = 'Grocery' AND parent_id IS NULL)
INSERT INTO categories (name, parent_id, level, display_order) VALUES
('Rice & Grains', (SELECT id FROM grocery_cat), 1, 1),
('Pulses & Lentils', (SELECT id FROM grocery_cat), 1, 2),
('Flour & Atta', (SELECT id FROM grocery_cat), 1, 3),
('Oil & Ghee', (SELECT id FROM grocery_cat), 1, 4),
('Spices & Masala', (SELECT id FROM grocery_cat), 1, 5),
('Salt & Sugar', (SELECT id FROM grocery_cat), 1, 6),
('Dry Fruits & Nuts', (SELECT id FROM grocery_cat), 1, 7)
ON CONFLICT DO NOTHING;

-- Insert sample brands
INSERT INTO brands (name, manufacturer, country_of_origin, is_verified) VALUES
('Aashirvaad', 'ITC Limited', 'India', true),
('Fortune', 'Adani Wilmar', 'India', true),
('Tata Sampann', 'Tata Consumer Products', 'India', true),
('India Gate', 'KRBL Limited', 'India', true),
('Patanjali', 'Patanjali Ayurved', 'India', true),
('Amul', 'Gujarat Cooperative Milk Marketing Federation', 'India', true),
('Britannia', 'Britannia Industries', 'India', true),
('Parle', 'Parle Products', 'India', true),
('Nestle', 'Nestle India', 'India', true),
('Haldiram', 'Haldiram Snacks', 'India', true)
ON CONFLICT (name) DO NOTHING;

-- Grant permissions (adjust based on your user setup)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_app_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_app_user;