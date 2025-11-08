-- Seed Data for Generic Products
-- This file populates the generic_products table with common Indian grocery items

-- First, ensure we have the necessary categories
WITH cat_grocery AS (SELECT id FROM categories WHERE name = 'Grocery' AND parent_id IS NULL),
     cat_rice AS (SELECT id FROM categories WHERE name = 'Rice & Grains' AND parent_id = (SELECT id FROM cat_grocery)),
     cat_pulses AS (SELECT id FROM categories WHERE name = 'Pulses & Lentils' AND parent_id = (SELECT id FROM cat_grocery)),
     cat_flour AS (SELECT id FROM categories WHERE name = 'Flour & Atta' AND parent_id = (SELECT id FROM cat_grocery)),
     cat_oil AS (SELECT id FROM categories WHERE name = 'Oil & Ghee' AND parent_id = (SELECT id FROM cat_grocery)),
     cat_spices AS (SELECT id FROM categories WHERE name = 'Spices & Masala' AND parent_id = (SELECT id FROM cat_grocery)),
     cat_sugar AS (SELECT id FROM categories WHERE name = 'Salt & Sugar' AND parent_id = (SELECT id FROM cat_grocery))

-- Insert Generic Products
INSERT INTO generic_products (
    name, 
    category_id, 
    subcategory_id, 
    product_type, 
    hsn_code, 
    default_unit, 
    searchable_keywords, 
    typical_sizes,
    attributes_template
) VALUES

-- Rice Products
('Rice', (SELECT id FROM cat_grocery), (SELECT id FROM cat_rice), 'grocery', '1006', 'kg', 
 ARRAY['rice', 'chawal', 'चावल', 'grain'], 
 ARRAY['1 kg', '5 kg', '10 kg', '25 kg'],
 '{"variant_types": ["Basmati", "Sona Masoori", "Kolam", "HMT", "Ponni", "Jasmine"], "required_fields": ["variant_type", "grain_length", "aging_period"]}'::jsonb),

('Basmati Rice', (SELECT id FROM cat_grocery), (SELECT id FROM cat_rice), 'grocery', '1006', 'kg',
 ARRAY['basmati', 'rice', 'premium rice', 'long grain'],
 ARRAY['1 kg', '5 kg', '10 kg', '20 kg'],
 '{"variant_types": ["Classic", "Premium", "Super", "Dubar"], "required_fields": ["grain_length", "aging_period", "aroma_level"]}'::jsonb),

('Wheat', (SELECT id FROM cat_grocery), (SELECT id FROM cat_rice), 'grocery', '1001', 'kg',
 ARRAY['wheat', 'gehun', 'गेहूं', 'grain'],
 ARRAY['1 kg', '5 kg', '10 kg', '50 kg'],
 '{"variant_types": ["Sharbati", "Lokwan", "MP Wheat"], "required_fields": ["variant_type", "protein_content"]}'::jsonb),

-- Flour Products
('Wheat Flour (Atta)', (SELECT id FROM cat_grocery), (SELECT id FROM cat_flour), 'grocery', '1101', 'kg',
 ARRAY['atta', 'flour', 'wheat flour', 'आटा', 'chakki atta'],
 ARRAY['1 kg', '5 kg', '10 kg'],
 '{"variant_types": ["Whole Wheat", "Multigrain", "Refined"], "required_fields": ["variant_type", "fineness"]}'::jsonb),

('Besan (Gram Flour)', (SELECT id FROM cat_grocery), (SELECT id FROM cat_flour), 'grocery', '1106', 'kg',
 ARRAY['besan', 'gram flour', 'chickpea flour', 'बेसन'],
 ARRAY['500 g', '1 kg', '2 kg'],
 '{"required_fields": ["fineness", "roasted"]}'::jsonb),

('Maida (All Purpose Flour)', (SELECT id FROM cat_grocery), (SELECT id FROM cat_flour), 'grocery', '1101', 'kg',
 ARRAY['maida', 'all purpose flour', 'refined flour', 'मैदा'],
 ARRAY['500 g', '1 kg', '5 kg'],
 '{"required_fields": ["protein_content", "bleached"]}'::jsonb),

('Sooji/Rava (Semolina)', (SELECT id FROM cat_grocery), (SELECT id FROM cat_flour), 'grocery', '1103', 'kg',
 ARRAY['sooji', 'rava', 'semolina', 'सूजी', 'रवा'],
 ARRAY['500 g', '1 kg', '2 kg'],
 '{"variant_types": ["Fine", "Medium", "Coarse", "Bombay Rava"], "required_fields": ["variant_type", "grain_size"]}'::jsonb),

-- Pulses/Dal Products
('Toor Dal (Arhar Dal)', (SELECT id FROM cat_grocery), (SELECT id FROM cat_pulses), 'grocery', '0713', 'kg',
 ARRAY['toor dal', 'arhar dal', 'pigeon pea', 'तूर दाल', 'अरहर दाल'],
 ARRAY['500 g', '1 kg', '2 kg', '5 kg'],
 '{"variant_types": ["Unpolished", "Single Polish", "Double Polish"], "required_fields": ["variant_type", "origin"]}'::jsonb),

('Moong Dal', (SELECT id FROM cat_grocery), (SELECT id FROM cat_pulses), 'grocery', '0713', 'kg',
 ARRAY['moong dal', 'green gram', 'मूंग दाल', 'yellow lentil'],
 ARRAY['500 g', '1 kg', '2 kg'],
 '{"variant_types": ["Split", "Whole", "Chilka", "Dhuli"], "required_fields": ["variant_type", "split_type"]}'::jsonb),

('Chana Dal', (SELECT id FROM cat_grocery), (SELECT id FROM cat_pulses), 'grocery', '0713', 'kg',
 ARRAY['chana dal', 'bengal gram', 'चना दाल', 'split chickpea'],
 ARRAY['500 g', '1 kg', '2 kg'],
 '{"variant_types": ["Regular", "Desi", "Fine"], "required_fields": ["variant_type", "size"]}'::jsonb),

('Masoor Dal', (SELECT id FROM cat_grocery), (SELECT id FROM cat_pulses), 'grocery', '0713', 'kg',
 ARRAY['masoor dal', 'red lentil', 'मसूर दाल'],
 ARRAY['500 g', '1 kg', '2 kg'],
 '{"variant_types": ["Whole", "Split", "Malka"], "required_fields": ["variant_type", "color"]}'::jsonb),

('Urad Dal', (SELECT id FROM cat_grocery), (SELECT id FROM cat_pulses), 'grocery', '0713', 'kg',
 ARRAY['urad dal', 'black gram', 'उड़द दाल', 'black lentil'],
 ARRAY['500 g', '1 kg', '2 kg'],
 '{"variant_types": ["Whole", "Split", "Chilka", "Dhuli"], "required_fields": ["variant_type", "split_type"]}'::jsonb),

('Rajma (Kidney Beans)', (SELECT id FROM cat_grocery), (SELECT id FROM cat_pulses), 'grocery', '0713', 'kg',
 ARRAY['rajma', 'kidney beans', 'राजमा'],
 ARRAY['500 g', '1 kg', '2 kg'],
 '{"variant_types": ["Chitra", "Kashmiri Red", "Jammu"], "required_fields": ["variant_type", "size", "origin"]}'::jsonb),

('Kabuli Chana (Chickpeas)', (SELECT id FROM cat_grocery), (SELECT id FROM cat_pulses), 'grocery', '0713', 'kg',
 ARRAY['kabuli chana', 'chickpeas', 'chole', 'काबुली चना', 'छोले'],
 ARRAY['500 g', '1 kg', '2 kg'],
 '{"variant_types": ["Small", "Medium", "Large", "Premium"], "required_fields": ["size", "color"]}'::jsonb),

-- Oil Products
('Cooking Oil', (SELECT id FROM cat_grocery), (SELECT id FROM cat_oil), 'grocery', '1507', 'l',
 ARRAY['oil', 'cooking oil', 'तेल', 'edible oil'],
 ARRAY['1 L', '2 L', '5 L', '15 L'],
 '{"variant_types": ["Sunflower", "Mustard", "Groundnut", "Soybean", "Rice Bran", "Coconut", "Palm", "Olive"], "required_fields": ["variant_type", "refined", "cholesterol_free"]}'::jsonb),

('Mustard Oil', (SELECT id FROM cat_grocery), (SELECT id FROM cat_oil), 'grocery', '1514', 'l',
 ARRAY['mustard oil', 'sarson tel', 'सरसों तेल', 'kachi ghani'],
 ARRAY['500 ml', '1 L', '5 L'],
 '{"variant_types": ["Kachi Ghani", "Refined", "Filtered"], "required_fields": ["extraction_method", "pungency"]}'::jsonb),

('Ghee', (SELECT id FROM cat_grocery), (SELECT id FROM cat_oil), 'grocery', '0405', 'kg',
 ARRAY['ghee', 'desi ghee', 'घी', 'clarified butter'],
 ARRAY['200 ml', '500 ml', '1 L', '5 L'],
 '{"variant_types": ["Cow Ghee", "Buffalo Ghee", "Mixed"], "required_fields": ["source", "granulation"]}'::jsonb),

('Coconut Oil', (SELECT id FROM cat_grocery), (SELECT id FROM cat_oil), 'grocery', '1513', 'l',
 ARRAY['coconut oil', 'nariyal tel', 'नारियल तेल'],
 ARRAY['200 ml', '500 ml', '1 L'],
 '{"variant_types": ["Virgin", "Refined", "Cold Pressed"], "required_fields": ["extraction_method", "organic"]}'::jsonb),

-- Spices
('Turmeric Powder', (SELECT id FROM cat_grocery), (SELECT id FROM cat_spices), 'grocery', '0910', 'g',
 ARRAY['turmeric', 'haldi', 'हल्दी', 'turmeric powder'],
 ARRAY['50 g', '100 g', '200 g', '500 g'],
 '{"required_fields": ["curcumin_content", "origin", "processing_method"]}'::jsonb),

('Red Chilli Powder', (SELECT id FROM cat_grocery), (SELECT id FROM cat_spices), 'grocery', '0904', 'g',
 ARRAY['chilli powder', 'lal mirch', 'लाल मिर्च', 'red chilli'],
 ARRAY['50 g', '100 g', '200 g', '500 g'],
 '{"variant_types": ["Kashmiri", "Guntur", "Byadgi", "Regular"], "required_fields": ["variant_type", "heat_level", "color_value"]}'::jsonb),

('Coriander Powder', (SELECT id FROM cat_grocery), (SELECT id FROM cat_spices), 'grocery', '0909', 'g',
 ARRAY['coriander powder', 'dhania powder', 'धनिया पाउडर'],
 ARRAY['50 g', '100 g', '200 g', '500 g'],
 '{"required_fields": ["fineness", "aroma_strength"]}'::jsonb),

('Cumin Seeds', (SELECT id FROM cat_grocery), (SELECT id FROM cat_spices), 'grocery', '0909', 'g',
 ARRAY['cumin', 'jeera', 'जीरा', 'cumin seeds'],
 ARRAY['50 g', '100 g', '200 g'],
 '{"variant_types": ["Black Cumin", "Regular"], "required_fields": ["whole_or_powder", "origin"]}'::jsonb),

('Garam Masala', (SELECT id FROM cat_grocery), (SELECT id FROM cat_spices), 'grocery', '0910', 'g',
 ARRAY['garam masala', 'गरम मसाला', 'spice mix'],
 ARRAY['50 g', '100 g', '200 g'],
 '{"required_fields": ["ingredients_list", "spice_level"]}'::jsonb),

-- Salt & Sugar
('Salt', (SELECT id FROM cat_grocery), (SELECT id FROM cat_sugar), 'grocery', '2501', 'kg',
 ARRAY['salt', 'namak', 'नमक'],
 ARRAY['500 g', '1 kg', '2 kg'],
 '{"variant_types": ["Iodized", "Rock Salt", "Sea Salt", "Black Salt", "Pink Salt"], "required_fields": ["variant_type", "iodine_content"]}'::jsonb),

('Sugar', (SELECT id FROM cat_grocery), (SELECT id FROM cat_sugar), 'grocery', '1701', 'kg',
 ARRAY['sugar', 'chini', 'चीनी', 'shakar'],
 ARRAY['500 g', '1 kg', '2 kg', '5 kg'],
 '{"variant_types": ["White", "Brown", "Powdered", "Organic"], "required_fields": ["variant_type", "crystal_size"]}'::jsonb),

('Jaggery (Gur)', (SELECT id FROM cat_grocery), (SELECT id FROM cat_sugar), 'grocery', '1701', 'kg',
 ARRAY['jaggery', 'gur', 'गुड़', 'bella'],
 ARRAY['250 g', '500 g', '1 kg'],
 '{"variant_types": ["Ball", "Powder", "Cube", "Organic"], "required_fields": ["form", "color", "source"]}'::jsonb),

-- Tea & Coffee
('Tea', (SELECT id FROM cat_grocery), (SELECT id FROM cat_grocery), 'grocery', '0902', 'g',
 ARRAY['tea', 'chai', 'चाय', 'chai patti'],
 ARRAY['50 g', '100 g', '250 g', '500 g', '1 kg'],
 '{"variant_types": ["Black Tea", "Green Tea", "Masala Tea", "Premium"], "required_fields": ["variant_type", "leaf_grade", "origin"]}'::jsonb),

('Coffee', (SELECT id FROM cat_grocery), (SELECT id FROM cat_grocery), 'grocery', '0901', 'g',
 ARRAY['coffee', 'कॉफी', 'instant coffee'],
 ARRAY['50 g', '100 g', '200 g', '500 g'],
 '{"variant_types": ["Instant", "Filter", "Ground", "Beans"], "required_fields": ["variant_type", "roast_level", "blend"]}'::jsonb),

-- Dairy Products
('Milk', (SELECT id FROM cat_grocery), (SELECT id FROM cat_grocery), 'grocery', '0401', 'l',
 ARRAY['milk', 'दूध', 'doodh'],
 ARRAY['500 ml', '1 L'],
 '{"variant_types": ["Full Cream", "Toned", "Double Toned", "Skimmed"], "required_fields": ["fat_content", "pasteurized"]}'::jsonb),

('Paneer', (SELECT id FROM cat_grocery), (SELECT id FROM cat_grocery), 'grocery', '0406', 'g',
 ARRAY['paneer', 'पनीर', 'cottage cheese'],
 ARRAY['200 g', '500 g', '1 kg'],
 '{"variant_types": ["Regular", "Low Fat", "Malai"], "required_fields": ["fat_content", "texture"]}'::jsonb),

('Butter', (SELECT id FROM cat_grocery), (SELECT id FROM cat_grocery), 'grocery', '0405', 'g',
 ARRAY['butter', 'मक्खन', 'makkhan'],
 ARRAY['100 g', '200 g', '500 g'],
 '{"variant_types": ["Salted", "Unsalted", "White"], "required_fields": ["salt_content", "fat_content"]}'::jsonb),

-- Snacks & Biscuits
('Biscuits', (SELECT id FROM cat_grocery), (SELECT id FROM cat_grocery), 'grocery', '1905', 'g',
 ARRAY['biscuits', 'बिस्कुट', 'cookies'],
 ARRAY['50 g', '100 g', '200 g', '400 g'],
 '{"variant_types": ["Cream", "Glucose", "Marie", "Digestive", "Cookies"], "required_fields": ["flavor", "sugar_content"]}'::jsonb),

('Namkeen', (SELECT id FROM cat_grocery), (SELECT id FROM cat_grocery), 'grocery', '2008', 'g',
 ARRAY['namkeen', 'नमकीन', 'mixture', 'bhujia'],
 ARRAY['200 g', '400 g', '1 kg'],
 '{"variant_types": ["Bhujia", "Mixture", "Sev", "Chivda"], "required_fields": ["spice_level", "main_ingredient"]}'::jsonb),

('Chips', (SELECT id FROM cat_grocery), (SELECT id FROM cat_grocery), 'grocery', '2005', 'g',
 ARRAY['chips', 'चिप्स', 'wafers'],
 ARRAY['25 g', '50 g', '100 g', '200 g'],
 '{"variant_types": ["Potato", "Banana", "Tapioca"], "required_fields": ["flavor", "cut_style"]}'::jsonb),

-- Instant Food
('Noodles', (SELECT id FROM cat_grocery), (SELECT id FROM cat_grocery), 'grocery', '1902', 'g',
 ARRAY['noodles', 'नूडल्स', 'instant noodles', 'maggi'],
 ARRAY['70 g', '140 g', '280 g', '560 g'],
 '{"variant_types": ["Masala", "Chicken", "Vegetables", "Atta"], "required_fields": ["flavor", "cooking_time"]}'::jsonb),

('Pasta', (SELECT id FROM cat_grocery), (SELECT id FROM cat_grocery), 'grocery', '1902', 'g',
 ARRAY['pasta', 'पास्ता', 'macaroni', 'spaghetti'],
 ARRAY['250 g', '500 g', '1 kg'],
 '{"variant_types": ["Penne", "Fusilli", "Macaroni", "Spaghetti"], "required_fields": ["shape", "cooking_time"]}'::jsonb),

('Ready Mix', (SELECT id FROM cat_grocery), (SELECT id FROM cat_grocery), 'grocery', '2106', 'g',
 ARRAY['ready mix', 'instant mix', 'रेडी मिक्स'],
 ARRAY['200 g', '500 g', '1 kg'],
 '{"variant_types": ["Dosa", "Idli", "Dhokla", "Gulab Jamun", "Upma"], "required_fields": ["dish_type", "preparation_time"]}'::jsonb),

-- Personal Care Products (Basic)
('Soap', (SELECT id FROM cat_grocery), (SELECT id FROM cat_grocery), 'personal_care', '3401', 'piece',
 ARRAY['soap', 'साबुन', 'bathing soap', 'bath soap'],
 ARRAY['75 g', '100 g', '125 g', '150 g'],
 '{"variant_types": ["Beauty", "Herbal", "Antibacterial", "Moisturizing"], "required_fields": ["skin_type", "fragrance"]}'::jsonb),

('Toothpaste', (SELECT id FROM cat_grocery), (SELECT id FROM cat_grocery), 'personal_care', '3306', 'g',
 ARRAY['toothpaste', 'टूथपेस्ट', 'dental cream'],
 ARRAY['50 g', '100 g', '150 g', '200 g'],
 '{"variant_types": ["Regular", "Gel", "Herbal", "Whitening", "Sensitive"], "required_fields": ["fluoride_content", "flavor"]}'::jsonb),

('Shampoo', (SELECT id FROM cat_grocery), (SELECT id FROM cat_grocery), 'personal_care', '3305', 'ml',
 ARRAY['shampoo', 'शैम्पू'],
 ARRAY['100 ml', '200 ml', '340 ml', '650 ml', '1 L'],
 '{"variant_types": ["Anti-Dandruff", "Smooth & Silky", "Hair Fall", "Damage Repair"], "required_fields": ["hair_type", "ingredients"]}'::jsonb),

('Hair Oil', (SELECT id FROM cat_grocery), (SELECT id FROM cat_grocery), 'personal_care', '3305', 'ml',
 ARRAY['hair oil', 'तेल', 'केश तेल'],
 ARRAY['100 ml', '200 ml', '300 ml', '500 ml'],
 '{"variant_types": ["Coconut", "Almond", "Amla", "Herbal"], "required_fields": ["main_ingredient", "benefits"]}'::jsonb),

-- Cleaning Products
('Detergent Powder', (SELECT id FROM cat_grocery), (SELECT id FROM cat_grocery), 'household', '3402', 'kg',
 ARRAY['detergent', 'washing powder', 'डिटर्जेंट', 'surf'],
 ARRAY['500 g', '1 kg', '2 kg', '4 kg'],
 '{"variant_types": ["Top Load", "Front Load", "Hand Wash"], "required_fields": ["suitable_for", "fragrance"]}'::jsonb),

('Dishwash Liquid', (SELECT id FROM cat_grocery), (SELECT id FROM cat_grocery), 'household', '3402', 'ml',
 ARRAY['dishwash', 'dish soap', 'बर्तन साबुन'],
 ARRAY['250 ml', '500 ml', '750 ml', '1 L'],
 '{"variant_types": ["Gel", "Liquid", "Powder"], "required_fields": ["grease_cutting", "fragrance"]}'::jsonb),

('Floor Cleaner', (SELECT id FROM cat_grocery), (SELECT id FROM cat_grocery), 'household', '3402', 'l',
 ARRAY['floor cleaner', 'phenyl', 'फर्श क्लीनर'],
 ARRAY['500 ml', '1 L', '2 L', '5 L'],
 '{"variant_types": ["Disinfectant", "Herbal", "Citrus"], "required_fields": ["germ_kill_percentage", "fragrance"]}'::jsonb)

ON CONFLICT DO NOTHING;

-- Index creation commented out (needs immutable function)
-- CREATE INDEX IF NOT EXISTS idx_generic_products_search 
-- ON generic_products USING gin(to_tsvector('english', name || ' ' || coalesce(array_to_string(searchable_keywords, ' '), '')));