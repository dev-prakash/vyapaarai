-- ============================================
-- VyaparAI Database Reset Script
-- Purpose: Clean all store-specific data for fresh testing
-- Preserves: Generic products, categories, brands, and system settings
-- Deletes: All stores, users, orders, inventory, customers
-- ============================================

-- Disable foreign key checks temporarily (for PostgreSQL)
-- Note: Be very careful with this!
BEGIN;

-- ============================================
-- 1. DELETE PAYMENT & FINANCIAL DATA
-- ============================================
DELETE FROM store_settlements WHERE 1=1;
DELETE FROM payments WHERE 1=1;

-- ============================================
-- 2. DELETE ORDER RELATED DATA
-- ============================================
DELETE FROM order_status_history WHERE 1=1;
DELETE FROM order_items WHERE 1=1;
DELETE FROM orders WHERE 1=1;

-- ============================================
-- 3. DELETE INVENTORY & STOCK DATA
-- ============================================
DELETE FROM product_metrics WHERE 1=1;
DELETE FROM inventory_snapshots WHERE 1=1;
DELETE FROM price_history WHERE 1=1;
DELETE FROM product_offers WHERE 1=1;
DELETE FROM stock_movements WHERE 1=1;
DELETE FROM product_batches WHERE 1=1;
DELETE FROM product_images WHERE 1=1;
DELETE FROM purchase_order_items WHERE 1=1;
DELETE FROM purchase_orders WHERE 1=1;
DELETE FROM suppliers WHERE 1=1;
DELETE FROM store_products WHERE 1=1;

-- ============================================
-- 4. DELETE CUSTOMER DATA
-- ============================================
DELETE FROM customer_addresses WHERE 1=1;
DELETE FROM customers WHERE 1=1;

-- ============================================
-- 5. DELETE COMMUNICATION DATA
-- ============================================
DELETE FROM reviews WHERE 1=1;
DELETE FROM messages WHERE 1=1;
DELETE FROM notifications WHERE 1=1;

-- ============================================
-- 6. DELETE STORE AND USER DATA
-- ============================================
DELETE FROM store_users WHERE 1=1;
DELETE FROM stores WHERE 1=1;
DELETE FROM otp_verifications WHERE 1=1;
DELETE FROM users WHERE role != 'admin'; -- Keep admin users if any

-- ============================================
-- 7. DELETE AUDIT LOGS (Optional - you may want to keep these)
-- ============================================
DELETE FROM audit_logs WHERE entity_type IN ('store', 'order', 'product', 'customer');

-- ============================================
-- 8. RESET SEQUENCES (if using serial/identity columns)
-- ============================================
-- If you have any sequences, reset them here
-- ALTER SEQUENCE stores_id_seq RESTART WITH 1;
-- ALTER SEQUENCE orders_id_seq RESTART WITH 1;

-- ============================================
-- 9. VERIFY WHAT'S LEFT (Should only be system data)
-- ============================================
DO $$
BEGIN
    RAISE NOTICE 'Data cleanup complete. Remaining data:';
    RAISE NOTICE 'Categories: %', (SELECT COUNT(*) FROM categories);
    RAISE NOTICE 'Brands: %', (SELECT COUNT(*) FROM brands);
    RAISE NOTICE 'Generic Products: %', (SELECT COUNT(*) FROM generic_products);
    RAISE NOTICE 'Users: %', (SELECT COUNT(*) FROM users);
    RAISE NOTICE 'Stores: %', (SELECT COUNT(*) FROM stores);
    RAISE NOTICE 'Store Products: %', (SELECT COUNT(*) FROM store_products);
    RAISE NOTICE 'Orders: %', (SELECT COUNT(*) FROM orders);
END $$;

COMMIT;

-- ============================================
-- VERIFICATION QUERIES
-- ============================================
-- Run these queries to verify the cleanup:

SELECT 'Stores' as table_name, COUNT(*) as record_count FROM stores
UNION ALL
SELECT 'Store Products', COUNT(*) FROM store_products
UNION ALL
SELECT 'Orders', COUNT(*) FROM orders
UNION ALL
SELECT 'Order Items', COUNT(*) FROM order_items
UNION ALL
SELECT 'Stock Movements', COUNT(*) FROM stock_movements
UNION ALL
SELECT 'Users (non-admin)', COUNT(*) FROM users WHERE role != 'admin'
UNION ALL
SELECT 'Customers', COUNT(*) FROM customers
UNION ALL
SELECT 'Generic Products', COUNT(*) FROM generic_products
UNION ALL
SELECT 'Categories', COUNT(*) FROM categories
UNION ALL
SELECT 'Brands', COUNT(*) FROM brands;