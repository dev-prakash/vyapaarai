-- VyaparAI PostgreSQL Analytics Schema
-- Migration: 001_create_tables.sql
-- Description: Creates the complete analytics schema for VyaparAI

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- ============================================================================
-- MASTER DATA TABLES
-- ============================================================================

-- Stores table (master data)
CREATE TABLE stores (
    store_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    owner_id VARCHAR(50) NOT NULL,
    address JSONB NOT NULL DEFAULT '{}',
    contact_info JSONB NOT NULL DEFAULT '{}',
    settings JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Products table (catalog)
CREATE TABLE products (
    product_id VARCHAR(50) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    store_id VARCHAR(50) NOT NULL REFERENCES stores(store_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    brand VARCHAR(100),
    price DECIMAL(10,2) NOT NULL,
    unit VARCHAR(50) NOT NULL,
    stock_quantity INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- ORDER ARCHIVE TABLE
-- ============================================================================

-- Order archive table (completed orders for analytics)
CREATE TABLE order_archive (
    order_id VARCHAR(50) PRIMARY KEY,
    customer_phone VARCHAR(20) NOT NULL,
    store_id VARCHAR(50) NOT NULL REFERENCES stores(store_id),
    items JSONB NOT NULL DEFAULT '[]',
    total_amount DECIMAL(10,2) NOT NULL,
    status VARCHAR(20) NOT NULL,
    channel VARCHAR(20) NOT NULL,
    language VARCHAR(10) NOT NULL,
    intent VARCHAR(50) NOT NULL,
    confidence DECIMAL(5,4) NOT NULL,
    entities JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    cancelled_at TIMESTAMP WITH TIME ZONE,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- ============================================================================
-- ANALYTICS TABLES
-- ============================================================================

-- Daily store metrics
CREATE TABLE daily_store_metrics (
    store_id VARCHAR(50) NOT NULL REFERENCES stores(store_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    total_orders INTEGER DEFAULT 0,
    total_revenue DECIMAL(12,2) DEFAULT 0,
    completed_orders INTEGER DEFAULT 0,
    cancelled_orders INTEGER DEFAULT 0,
    unique_customers INTEGER DEFAULT 0,
    avg_order_value DECIMAL(10,2) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (store_id, date)
);

-- Customer analytics
CREATE TABLE customer_analytics (
    customer_phone VARCHAR(20) PRIMARY KEY,
    total_orders INTEGER DEFAULT 0,
    total_spent DECIMAL(12,2) DEFAULT 0,
    avg_order_value DECIMAL(10,2) DEFAULT 0,
    first_order_date TIMESTAMP WITH TIME ZONE,
    last_order_date TIMESTAMP WITH TIME ZONE,
    completed_orders INTEGER DEFAULT 0,
    cancelled_orders INTEGER DEFAULT 0,
    preferred_language VARCHAR(10),
    preferred_channel VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Product analytics
CREATE TABLE product_analytics (
    product_name VARCHAR(255) NOT NULL,
    store_id VARCHAR(50) NOT NULL REFERENCES stores(store_id) ON DELETE CASCADE,
    total_orders INTEGER DEFAULT 0,
    total_quantity INTEGER DEFAULT 0,
    total_revenue DECIMAL(12,2) DEFAULT 0,
    avg_price DECIMAL(10,2) DEFAULT 0,
    first_ordered_date TIMESTAMP WITH TIME ZONE,
    last_ordered_date TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (product_name, store_id)
);

-- ============================================================================
-- INVENTORY MANAGEMENT
-- ============================================================================

-- Inventory table
CREATE TABLE inventory (
    inventory_id VARCHAR(50) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    store_id VARCHAR(50) NOT NULL REFERENCES stores(store_id) ON DELETE CASCADE,
    product_id VARCHAR(50) NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL DEFAULT 0,
    reserved_quantity INTEGER DEFAULT 0,
    min_stock_level INTEGER DEFAULT 0,
    max_stock_level INTEGER,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(store_id, product_id)
);

-- Inventory transactions
CREATE TABLE inventory_transactions (
    transaction_id VARCHAR(50) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    store_id VARCHAR(50) NOT NULL REFERENCES stores(store_id),
    product_id VARCHAR(50) NOT NULL REFERENCES products(product_id),
    transaction_type VARCHAR(20) NOT NULL, -- 'in', 'out', 'adjustment', 'reserved', 'released'
    quantity INTEGER NOT NULL,
    order_id VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- PRICING AND DISCOUNTS
-- ============================================================================

-- Pricing rules
CREATE TABLE pricing_rules (
    rule_id VARCHAR(50) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    store_id VARCHAR(50) NOT NULL REFERENCES stores(store_id) ON DELETE CASCADE,
    rule_name VARCHAR(255) NOT NULL,
    rule_type VARCHAR(50) NOT NULL, -- 'discount', 'markup', 'bulk_pricing'
    conditions JSONB NOT NULL DEFAULT '{}',
    actions JSONB NOT NULL DEFAULT '{}',
    priority INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    valid_from TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    valid_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- CUSTOMER FEEDBACK AND RATINGS
-- ============================================================================

-- Customer feedback
CREATE TABLE customer_feedback (
    feedback_id VARCHAR(50) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    order_id VARCHAR(50) NOT NULL,
    customer_phone VARCHAR(20) NOT NULL,
    store_id VARCHAR(50) NOT NULL REFERENCES stores(store_id),
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    feedback_text TEXT,
    category VARCHAR(50), -- 'delivery', 'product_quality', 'service', 'app_experience'
    sentiment VARCHAR(20), -- 'positive', 'negative', 'neutral'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- NOTIFICATIONS AND COMMUNICATIONS
-- ============================================================================

-- Notifications table
CREATE TABLE notifications (
    notification_id VARCHAR(50) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    customer_phone VARCHAR(20) NOT NULL,
    store_id VARCHAR(50) NOT NULL REFERENCES stores(store_id),
    notification_type VARCHAR(50) NOT NULL, -- 'order_status', 'promotion', 'reminder'
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    channel VARCHAR(20) NOT NULL, -- 'sms', 'whatsapp', 'push'
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'sent', 'delivered', 'failed'
    order_id VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    sent_at TIMESTAMP WITH TIME ZONE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Stores indexes
CREATE INDEX idx_stores_owner_id ON stores(owner_id);
CREATE INDEX idx_stores_status ON stores(status);
CREATE INDEX idx_stores_created_at ON stores(created_at);

-- Products indexes
CREATE INDEX idx_products_store_id ON products(store_id);
CREATE INDEX idx_products_category ON products(category);
CREATE INDEX idx_products_brand ON products(brand);
CREATE INDEX idx_products_status ON products(status);
CREATE INDEX idx_products_name_gin ON products USING gin(name gin_trgm_ops);
CREATE INDEX idx_products_metadata_gin ON products USING gin(metadata);

-- Order archive indexes
CREATE INDEX idx_order_archive_customer_phone ON order_archive(customer_phone);
CREATE INDEX idx_order_archive_store_id ON order_archive(store_id);
CREATE INDEX idx_order_archive_status ON order_archive(status);
CREATE INDEX idx_order_archive_channel ON order_archive(channel);
CREATE INDEX idx_order_archive_language ON order_archive(language);
CREATE INDEX idx_order_archive_intent ON order_archive(intent);
CREATE INDEX idx_order_archive_created_at ON order_archive(created_at);
CREATE INDEX idx_order_archive_completed_at ON order_archive(completed_at);
CREATE INDEX idx_order_archive_store_date ON order_archive(store_id, DATE(created_at));

-- Daily store metrics indexes
CREATE INDEX idx_daily_store_metrics_date ON daily_store_metrics(date);
CREATE INDEX idx_daily_store_metrics_store_date ON daily_store_metrics(store_id, date);

-- Customer analytics indexes
CREATE INDEX idx_customer_analytics_total_spent ON customer_analytics(total_spent);
CREATE INDEX idx_customer_analytics_last_order_date ON customer_analytics(last_order_date);

-- Product analytics indexes
CREATE INDEX idx_product_analytics_store_id ON product_analytics(store_id);
CREATE INDEX idx_product_analytics_total_revenue ON product_analytics(total_revenue);
CREATE INDEX idx_product_analytics_last_ordered_date ON product_analytics(last_ordered_date);

-- Inventory indexes
CREATE INDEX idx_inventory_store_product ON inventory(store_id, product_id);
CREATE INDEX idx_inventory_low_stock ON inventory(store_id) WHERE quantity <= min_stock_level;

-- Inventory transactions indexes
CREATE INDEX idx_inventory_transactions_store_id ON inventory_transactions(store_id);
CREATE INDEX idx_inventory_transactions_product_id ON inventory_transactions(product_id);
CREATE INDEX idx_inventory_transactions_order_id ON inventory_transactions(order_id);
CREATE INDEX idx_inventory_transactions_created_at ON inventory_transactions(created_at);

-- Pricing rules indexes
CREATE INDEX idx_pricing_rules_store_id ON pricing_rules(store_id);
CREATE INDEX idx_pricing_rules_active ON pricing_rules(store_id) WHERE is_active = true;
CREATE INDEX idx_pricing_rules_validity ON pricing_rules(valid_from, valid_until);

-- Customer feedback indexes
CREATE INDEX idx_customer_feedback_order_id ON customer_feedback(order_id);
CREATE INDEX idx_customer_feedback_customer_phone ON customer_feedback(customer_phone);
CREATE INDEX idx_customer_feedback_store_id ON customer_feedback(store_id);
CREATE INDEX idx_customer_feedback_rating ON customer_feedback(rating);
CREATE INDEX idx_customer_feedback_sentiment ON customer_feedback(sentiment);

-- Notifications indexes
CREATE INDEX idx_notifications_customer_phone ON notifications(customer_phone);
CREATE INDEX idx_notifications_store_id ON notifications(store_id);
CREATE INDEX idx_notifications_status ON notifications(status);
CREATE INDEX idx_notifications_type ON notifications(notification_type);
CREATE INDEX idx_notifications_created_at ON notifications(created_at);

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Store performance view
CREATE VIEW store_performance AS
SELECT 
    s.store_id,
    s.name as store_name,
    COUNT(DISTINCT oa.customer_phone) as total_customers,
    COUNT(oa.order_id) as total_orders,
    SUM(oa.total_amount) as total_revenue,
    AVG(oa.total_amount) as avg_order_value,
    COUNT(CASE WHEN oa.status = 'completed' THEN 1 END) as completed_orders,
    COUNT(CASE WHEN oa.status = 'cancelled' THEN 1 END) as cancelled_orders,
    ROUND(
        COUNT(CASE WHEN oa.status = 'completed' THEN 1 END) * 100.0 / COUNT(oa.order_id), 2
    ) as completion_rate
FROM stores s
LEFT JOIN order_archive oa ON s.store_id = oa.store_id
WHERE oa.created_at >= NOW() - INTERVAL '30 days'
GROUP BY s.store_id, s.name;

-- Top products view
CREATE VIEW top_products AS
SELECT 
    pa.product_name,
    pa.store_id,
    s.name as store_name,
    pa.total_orders,
    pa.total_quantity,
    pa.total_revenue,
    pa.avg_price,
    ROUND(pa.total_revenue / NULLIF(pa.total_orders, 0), 2) as revenue_per_order
FROM product_analytics pa
JOIN stores s ON pa.store_id = s.store_id
WHERE pa.total_orders > 0
ORDER BY pa.total_revenue DESC;

-- Customer lifetime value view
CREATE VIEW customer_lifetime_value AS
SELECT 
    ca.customer_phone,
    ca.total_orders,
    ca.total_spent,
    ca.avg_order_value,
    ca.first_order_date,
    ca.last_order_date,
    EXTRACT(DAYS FROM (ca.last_order_date - ca.first_order_date)) as customer_lifetime_days,
    ROUND(ca.total_spent / NULLIF(EXTRACT(DAYS FROM (ca.last_order_date - ca.first_order_date)), 0), 2) as daily_value
FROM customer_analytics ca
WHERE ca.total_orders > 0;

-- ============================================================================
-- FUNCTIONS AND TRIGGERS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Function to calculate order total
CREATE OR REPLACE FUNCTION calculate_order_total(order_items JSONB, store_id_param VARCHAR(50))
RETURNS DECIMAL(10,2) AS $$
DECLARE
    total DECIMAL(10,2) := 0;
    item JSONB;
    product_price DECIMAL(10,2);
    item_quantity INTEGER;
BEGIN
    FOR item IN SELECT * FROM jsonb_array_elements(order_items)
    LOOP
        item_quantity := (item->>'quantity')::INTEGER;
        
        -- Get product price from products table
        SELECT price INTO product_price
        FROM products
        WHERE store_id = store_id_param 
        AND LOWER(name) = LOWER(item->>'product')
        LIMIT 1;
        
        -- Use default price if product not found
        IF product_price IS NULL THEN
            product_price := 50.0; -- Default price
        END IF;
        
        total := total + (product_price * item_quantity);
    END LOOP;
    
    RETURN total;
END;
$$ LANGUAGE plpgsql;

-- Function to update inventory on order
CREATE OR REPLACE FUNCTION update_inventory_on_order()
RETURNS TRIGGER AS $$
DECLARE
    item JSONB;
    product_id_val VARCHAR(50);
    item_quantity INTEGER;
BEGIN
    -- Only process completed orders
    IF NEW.status = 'completed' AND OLD.status != 'completed' THEN
        FOR item IN SELECT * FROM jsonb_array_elements(NEW.items)
        LOOP
            item_quantity := (item->>'quantity')::INTEGER;
            
            -- Get product_id from products table
            SELECT product_id INTO product_id_val
            FROM products
            WHERE store_id = NEW.store_id 
            AND LOWER(name) = LOWER(item->>'product')
            LIMIT 1;
            
            IF product_id_val IS NOT NULL THEN
                -- Update inventory
                UPDATE inventory 
                SET quantity = quantity - item_quantity,
                    last_updated = NOW()
                WHERE store_id = NEW.store_id 
                AND product_id = product_id_val;
                
                -- Record transaction
                INSERT INTO inventory_transactions (
                    store_id, product_id, transaction_type, quantity, order_id, notes
                ) VALUES (
                    NEW.store_id, product_id_val, 'out', item_quantity, NEW.order_id, 
                    'Order completion'
                );
            END IF;
        END LOOP;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to update analytics on order completion
CREATE OR REPLACE FUNCTION update_analytics_on_order()
RETURNS TRIGGER AS $$
BEGIN
    -- Update daily store metrics
    INSERT INTO daily_store_metrics (
        store_id, date, total_orders, total_revenue, completed_orders, cancelled_orders, unique_customers
    ) VALUES (
        NEW.store_id, DATE(NEW.created_at), 1, 
        CASE WHEN NEW.status = 'completed' THEN NEW.total_amount ELSE 0 END,
        CASE WHEN NEW.status = 'completed' THEN 1 ELSE 0 END,
        CASE WHEN NEW.status = 'cancelled' THEN 1 ELSE 0 END,
        1
    )
    ON CONFLICT (store_id, date) DO UPDATE SET
        total_orders = daily_store_metrics.total_orders + 1,
        total_revenue = daily_store_metrics.total_revenue + 
            CASE WHEN NEW.status = 'completed' THEN NEW.total_amount ELSE 0 END,
        completed_orders = daily_store_metrics.completed_orders + 
            CASE WHEN NEW.status = 'completed' THEN 1 ELSE 0 END,
        cancelled_orders = daily_store_metrics.cancelled_orders + 
            CASE WHEN NEW.status = 'cancelled' THEN 1 ELSE 0 END,
        unique_customers = CASE 
            WHEN NEW.customer_phone NOT IN (
                SELECT DISTINCT customer_phone 
                FROM order_archive 
                WHERE store_id = NEW.store_id AND DATE(created_at) = DATE(NEW.created_at)
            ) THEN daily_store_metrics.unique_customers + 1
            ELSE daily_store_metrics.unique_customers
        END,
        updated_at = NOW();
    
    -- Update customer analytics
    INSERT INTO customer_analytics (
        customer_phone, total_orders, total_spent, avg_order_value, 
        first_order_date, last_order_date, completed_orders, cancelled_orders
    ) VALUES (
        NEW.customer_phone, 1, 
        CASE WHEN NEW.status = 'completed' THEN NEW.total_amount ELSE 0 END,
        CASE WHEN NEW.status = 'completed' THEN NEW.total_amount ELSE 0 END,
        NEW.created_at, NEW.created_at,
        CASE WHEN NEW.status = 'completed' THEN 1 ELSE 0 END,
        CASE WHEN NEW.status = 'cancelled' THEN 1 ELSE 0 END
    )
    ON CONFLICT (customer_phone) DO UPDATE SET
        total_orders = customer_analytics.total_orders + 1,
        total_spent = customer_analytics.total_spent + 
            CASE WHEN NEW.status = 'completed' THEN NEW.total_amount ELSE 0 END,
        avg_order_value = (customer_analytics.total_spent + 
            CASE WHEN NEW.status = 'completed' THEN NEW.total_amount ELSE 0 END) / 
            (customer_analytics.total_orders + 1),
        first_order_date = CASE 
            WHEN customer_analytics.first_order_date IS NULL THEN NEW.created_at
            ELSE customer_analytics.first_order_date
        END,
        last_order_date = NEW.created_at,
        completed_orders = customer_analytics.completed_orders + 
            CASE WHEN NEW.status = 'completed' THEN 1 ELSE 0 END,
        cancelled_orders = customer_analytics.cancelled_orders + 
            CASE WHEN NEW.status = 'cancelled' THEN 1 ELSE 0 END,
        updated_at = NOW();
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Updated timestamp triggers
CREATE TRIGGER update_stores_updated_at BEFORE UPDATE ON stores
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_products_updated_at BEFORE UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_daily_store_metrics_updated_at BEFORE UPDATE ON daily_store_metrics
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_customer_analytics_updated_at BEFORE UPDATE ON customer_analytics
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_product_analytics_updated_at BEFORE UPDATE ON product_analytics
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_pricing_rules_updated_at BEFORE UPDATE ON pricing_rules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Order processing triggers
CREATE TRIGGER update_inventory_on_order_completion
    AFTER UPDATE ON order_archive
    FOR EACH ROW EXECUTE FUNCTION update_inventory_on_order();

CREATE TRIGGER update_analytics_on_order_insert
    AFTER INSERT ON order_archive
    FOR EACH ROW EXECUTE FUNCTION update_analytics_on_order();

-- ============================================================================
-- SAMPLE DATA (OPTIONAL)
-- ============================================================================

-- Insert sample store
INSERT INTO stores (store_id, name, owner_id, address, contact_info, settings) VALUES
('store_001', 'Mumbai Grocery Store', 'owner_001', 
 '{"street": "123 Main Street", "city": "Mumbai", "state": "Maharashtra", "pincode": "400001"}',
 '{"phone": "+91-9876543210", "email": "store@mumbaigrocery.com"}',
 '{"delivery_radius": 5, "min_order_amount": 100, "delivery_fee": 20}');

-- Insert sample products
INSERT INTO products (store_id, name, category, brand, price, unit, stock_quantity) VALUES
('store_001', 'Basmati Rice', 'Grains', 'India Gate', 120.00, 'kg', 50),
('store_001', 'Refined Oil', 'Cooking Oil', 'Fortune', 150.00, 'liter', 30),
('store_001', 'Milk', 'Dairy', 'Amul', 60.00, 'liter', 100),
('store_001', 'Bread', 'Bakery', 'Britannia', 35.00, 'pack', 25),
('store_001', 'Sugar', 'Essentials', 'Local', 45.00, 'kg', 40);

-- Insert sample inventory
INSERT INTO inventory (store_id, product_id, quantity, min_stock_level, max_stock_level)
SELECT 'store_001', product_id, stock_quantity, 10, stock_quantity * 2
FROM products WHERE store_id = 'store_001';

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE stores IS 'Master data for stores';
COMMENT ON TABLE products IS 'Product catalog for each store';
COMMENT ON TABLE order_archive IS 'Completed orders for analytics';
COMMENT ON TABLE daily_store_metrics IS 'Daily aggregated metrics per store';
COMMENT ON TABLE customer_analytics IS 'Customer behavior and value analytics';
COMMENT ON TABLE product_analytics IS 'Product performance analytics';
COMMENT ON TABLE inventory IS 'Current inventory levels';
COMMENT ON TABLE inventory_transactions IS 'Inventory movement history';
COMMENT ON TABLE pricing_rules IS 'Dynamic pricing and discount rules';
COMMENT ON TABLE customer_feedback IS 'Customer feedback and ratings';
COMMENT ON TABLE notifications IS 'Customer communication history';

COMMENT ON VIEW store_performance IS 'Store performance summary view';
COMMENT ON VIEW top_products IS 'Top performing products view';
COMMENT ON VIEW customer_lifetime_value IS 'Customer lifetime value analysis';

COMMENT ON FUNCTION calculate_order_total IS 'Calculates order total using product prices';
COMMENT ON FUNCTION update_inventory_on_order IS 'Updates inventory when order is completed';
COMMENT ON FUNCTION update_analytics_on_order IS 'Updates analytics tables on order completion';
