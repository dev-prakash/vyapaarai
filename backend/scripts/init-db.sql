-- Create tables if not exists
CREATE TABLE IF NOT EXISTS stores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(20) UNIQUE NOT NULL,
    address JSONB,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name_json JSONB NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    unit VARCHAR(10),
    category VARCHAR(50),
    brand VARCHAR(50),
    popularity INTEGER DEFAULT 0
);

-- Insert test store
INSERT INTO stores (id, name, phone, address)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'Test Kirana Store',
    '+919876543210',
    '{"street": "MG Road", "city": "Mumbai", "state": "Maharashtra", "pincode": "400001"}'
) ON CONFLICT (phone) DO NOTHING;

-- Insert test products
INSERT INTO products (name_json, price, unit, category, brand) VALUES
('{"en": "Rice", "hi": "चावल"}', 60.00, 'kg', 'Grains', 'India Gate'),
('{"en": "Wheat Flour", "hi": "आटा"}', 45.00, 'kg', 'Grains', 'Aashirvaad'),
('{"en": "Oil", "hi": "तेल"}', 150.00, 'litre', 'Cooking', 'Fortune'),
('{"en": "Milk", "hi": "दूध"}', 56.00, 'litre', 'Dairy', 'Amul'),
('{"en": "Sugar", "hi": "चीनी"}', 42.00, 'kg', 'Essentials', 'Madhur')
ON CONFLICT DO NOTHING;
