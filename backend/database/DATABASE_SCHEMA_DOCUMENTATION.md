# VyaparAI Database Schema Documentation

## Complete Database Architecture Overview

This document provides a comprehensive overview of all database tables used in the VyaparAI application, their purposes, and when records are created, updated, or deleted.

---

## 1. USER & AUTHENTICATION TABLES

### **users**
**Purpose**: Stores user account information for customers and store owners
**When Created**: When a new user signs up through the app
**When Updated**: Profile updates, password changes, email verification
**When Deleted**: Account deletion (soft delete preferred)
```sql
- id (UUID): Primary key
- email (VARCHAR): Unique email address
- phone (VARCHAR): Phone number for OTP login
- password_hash (VARCHAR): Encrypted password
- full_name (VARCHAR): User's full name
- role (ENUM): 'customer', 'store_owner', 'admin'
- email_verified (BOOLEAN): Email verification status
- phone_verified (BOOLEAN): Phone verification status
- created_at (TIMESTAMP): Account creation time
- updated_at (TIMESTAMP): Last update time
- last_login (TIMESTAMP): Last successful login
- is_active (BOOLEAN): Account active status
```

### **otp_verifications**
**Purpose**: Temporary storage for OTP codes during phone verification
**When Created**: When user requests OTP for login/verification
**When Updated**: Never (create new record for retry)
**When Deleted**: After successful verification or expiry (auto-cleanup after 10 minutes)
```sql
- id (UUID): Primary key
- phone (VARCHAR): Phone number
- otp_code (VARCHAR): 6-digit OTP code
- purpose (ENUM): 'login', 'verification', 'password_reset'
- attempts (INTEGER): Number of verification attempts
- expires_at (TIMESTAMP): OTP expiry time
- verified (BOOLEAN): Verification status
- created_at (TIMESTAMP): OTP generation time
```

---

## 2. STORE MANAGEMENT TABLES

### **stores**
**Purpose**: Main store/shop information and profile
**When Created**: When a store owner completes registration
**When Updated**: Store profile updates, business hours changes, status changes
**When Deleted**: Store closure (soft delete - mark as inactive)
```sql
- id (UUID): Primary key
- store_id (VARCHAR): Unique store identifier (user-friendly)
- store_name (VARCHAR): Store/shop name
- owner_name (VARCHAR): Owner's full name
- email (VARCHAR): Business email
- phone (VARCHAR): Business phone number
- whatsapp_number (VARCHAR): WhatsApp for orders
- address (TEXT): Complete store address
- city (VARCHAR): City
- state (VARCHAR): State
- pincode (VARCHAR): PIN code
- gstin (VARCHAR): GST number (optional)
- store_type (VARCHAR): Type of store (grocery, pharmacy, etc.)
- business_hours (JSONB): Operating hours by day
- delivery_radius_km (DECIMAL): Delivery area radius
- min_order_amount (DECIMAL): Minimum order value
- accepts_online_payment (BOOLEAN): Payment method availability
- status (ENUM): 'active', 'inactive', 'suspended', 'pending_verification'
- verified (BOOLEAN): Store verification status
- rating (DECIMAL): Average customer rating
- total_orders (INTEGER): Total orders processed
- created_at (TIMESTAMP): Registration date
- updated_at (TIMESTAMP): Last profile update
```

### **store_users**
**Purpose**: Links users to stores with specific roles (owner, staff, manager)
**When Created**: When store owner adds staff or during store registration
**When Updated**: Role changes, permission updates
**When Deleted**: When staff is removed from store
```sql
- id (UUID): Primary key
- store_id (UUID): Foreign key to stores
- user_id (UUID): Foreign key to users
- role (ENUM): 'owner', 'manager', 'staff'
- permissions (JSONB): Specific permissions granted
- is_active (BOOLEAN): Active status
- created_at (TIMESTAMP): Association creation
- updated_at (TIMESTAMP): Last update
```

---

## 3. INVENTORY MANAGEMENT TABLES

### **categories**
**Purpose**: Product category hierarchy (Grocery > Rice & Grains > Basmati Rice)
**When Created**: During system setup or when admin adds new category
**When Updated**: Category name changes, reordering
**When Deleted**: Rarely (only if no products associated)
```sql
- id (UUID): Primary key
- name (VARCHAR): Category name
- parent_id (UUID): Parent category for hierarchy
- level (INTEGER): Hierarchy level (0 for root)
- icon_url (VARCHAR): Category icon
- display_order (INTEGER): Display sequence
- is_active (BOOLEAN): Active status
- created_at (TIMESTAMP): Creation time
- updated_at (TIMESTAMP): Last update
```

### **brands**
**Purpose**: Master list of product brands
**When Created**: System setup or when new brand is encountered
**When Updated**: Brand information updates, verification status
**When Deleted**: Never (may be marked inactive)
```sql
- id (UUID): Primary key
- name (VARCHAR): Brand name (Amul, Tata, etc.)
- logo_url (VARCHAR): Brand logo
- manufacturer (VARCHAR): Manufacturer name
- country_of_origin (VARCHAR): Origin country
- is_verified (BOOLEAN): Verification status
- created_at (TIMESTAMP): Creation time
- updated_at (TIMESTAMP): Last update
```

### **generic_products**
**Purpose**: Master catalog of product templates shared across all stores
**When Created**: System setup or admin adds new product type
**When Updated**: Product information corrections, keyword additions
**When Deleted**: Never (central catalog)
```sql
- id (UUID): Primary key
- name (VARCHAR): Generic product name (Rice, Dal, Oil)
- category_id (UUID): Product category
- subcategory_id (UUID): Product subcategory
- product_type (ENUM): grocery, personal_care, household, etc.
- hsn_code (VARCHAR): HSN/SAC code for GST
- default_unit (VARCHAR): Default unit (kg, l, piece)
- searchable_keywords (TEXT[]): Search keywords in multiple languages
- typical_sizes (TEXT[]): Common package sizes
- attributes_template (JSONB): Required attributes for this product
- is_active (BOOLEAN): Active status
- created_at (TIMESTAMP): Creation time
- updated_at (TIMESTAMP): Last update
```

### **store_products**
**Purpose**: Actual products in a store's inventory with specific details
**When Created**: When store owner adds a product to inventory
**When Updated**: Price changes, stock updates, product edits
**When Deleted**: When product is permanently removed from store
```sql
- id (UUID): Primary key
- store_id (UUID): Store owning this product
- generic_product_id (UUID): Link to generic product template
- sku (VARCHAR): Stock keeping unit (unique per store)
- barcode (VARCHAR): Product barcode
- product_name (VARCHAR): Full product name with brand
- brand_id (UUID): Product brand
- variant_type (VARCHAR): Specific variant (Basmati, Sona Masoori)
- size (DECIMAL): Package size
- size_unit (VARCHAR): Unit for size
- mrp (DECIMAL): Maximum retail price
- cost_price (DECIMAL): Purchase cost
- selling_price (DECIMAL): Actual selling price
- tax_rate (DECIMAL): GST percentage
- discount_percentage (DECIMAL): Discount offered
- current_stock (DECIMAL): Available quantity
- reserved_stock (DECIMAL): Stock reserved for pending orders
- min_stock_level (DECIMAL): Reorder alert level
- max_stock_level (DECIMAL): Maximum storage capacity
- status (ENUM): active, inactive, discontinued, out_of_stock
- created_at (TIMESTAMP): Product addition time
- updated_at (TIMESTAMP): Last update
- last_stock_update (TIMESTAMP): Last stock change
```

### **stock_movements**
**Purpose**: Audit trail of all inventory changes
**When Created**: Every time stock quantity changes
**When Updated**: Never (immutable audit log)
**When Deleted**: Never (permanent record)
```sql
- id (UUID): Primary key
- store_product_id (UUID): Product affected
- movement_type (ENUM): purchase, sale, return, adjustment, damage, expiry
- quantity (DECIMAL): Quantity changed (+ for in, - for out)
- balance_after (DECIMAL): Stock level after movement
- reference_type (VARCHAR): Source of change (order, manual, etc.)
- reference_id (VARCHAR): Related transaction ID
- reason (TEXT): Explanation for movement
- performed_by (UUID): User who made the change
- created_at (TIMESTAMP): Movement timestamp
```

### **product_batches**
**Purpose**: Track product batches for expiry management
**When Created**: When receiving stock with batch/expiry information
**When Updated**: Quantity updates as batch is sold
**When Deleted**: When batch is fully consumed or expired
```sql
- id (UUID): Primary key
- store_product_id (UUID): Product reference
- batch_number (VARCHAR): Batch identifier
- quantity (DECIMAL): Original quantity
- remaining_quantity (DECIMAL): Current remaining
- manufacture_date (DATE): Manufacturing date
- expiry_date (DATE): Expiration date
- supplier_id (UUID): Supplier reference
- purchase_price (DECIMAL): Batch purchase price
- created_at (TIMESTAMP): Batch entry time
```

### **suppliers**
**Purpose**: Store's supplier/vendor information
**When Created**: When store adds a new supplier
**When Updated**: Supplier details change
**When Deleted**: Soft delete when supplier relationship ends
```sql
- id (UUID): Primary key
- store_id (UUID): Store reference
- name (VARCHAR): Supplier name
- contact_person (VARCHAR): Contact name
- phone (VARCHAR): Phone number
- email (VARCHAR): Email address
- address (TEXT): Supplier address
- gstin (VARCHAR): GST number
- payment_terms (VARCHAR): Payment conditions
- delivery_lead_time_days (INTEGER): Delivery timeline
- is_active (BOOLEAN): Active status
- created_at (TIMESTAMP): Addition time
- updated_at (TIMESTAMP): Last update
```

---

## 4. ORDER MANAGEMENT TABLES

### **orders**
**Purpose**: Customer orders placed with stores
**When Created**: When customer places an order
**When Updated**: Status changes, payment confirmation, delivery updates
**When Deleted**: Never (may be cancelled but not deleted)
```sql
- id (UUID): Primary key
- order_number (VARCHAR): Human-readable order ID
- store_id (UUID): Store receiving order
- customer_id (UUID): Customer placing order
- customer_name (VARCHAR): Customer name
- customer_phone (VARCHAR): Contact number
- customer_email (VARCHAR): Email address
- delivery_address (TEXT): Delivery location
- order_type (ENUM): delivery, pickup, dine_in
- status (ENUM): pending, confirmed, preparing, ready, out_for_delivery, delivered, cancelled
- total_amount (DECIMAL): Order total
- tax_amount (DECIMAL): Total tax
- delivery_charge (DECIMAL): Delivery fee
- discount_amount (DECIMAL): Total discount
- final_amount (DECIMAL): Amount to pay
- payment_method (ENUM): cash, upi, card, wallet
- payment_status (ENUM): pending, paid, failed, refunded
- delivery_date (DATE): Expected delivery
- delivery_time_slot (VARCHAR): Delivery window
- notes (TEXT): Special instructions
- created_at (TIMESTAMP): Order placement time
- updated_at (TIMESTAMP): Last status update
- delivered_at (TIMESTAMP): Actual delivery time
```

### **order_items**
**Purpose**: Individual line items in an order
**When Created**: When order is placed (created with order)
**When Updated**: Quantity adjustments before confirmation
**When Deleted**: Never (part of order history)
```sql
- id (UUID): Primary key
- order_id (UUID): Parent order
- store_product_id (UUID): Product ordered
- product_name (VARCHAR): Product name at time of order
- quantity (DECIMAL): Quantity ordered
- unit_price (DECIMAL): Price per unit
- tax_amount (DECIMAL): Tax for this item
- discount_amount (DECIMAL): Item discount
- total_amount (DECIMAL): Line total
- notes (TEXT): Item-specific notes
- created_at (TIMESTAMP): Addition time
```

### **order_status_history**
**Purpose**: Track order status changes
**When Created**: Every time order status changes
**When Updated**: Never (append-only log)
**When Deleted**: Never
```sql
- id (UUID): Primary key
- order_id (UUID): Order reference
- status (VARCHAR): New status
- changed_by (UUID): User making change
- notes (TEXT): Status change notes
- created_at (TIMESTAMP): Change timestamp
```

---

## 5. PAYMENT & TRANSACTION TABLES

### **payments**
**Purpose**: Payment transactions for orders
**When Created**: When payment is initiated
**When Updated**: Payment status changes
**When Deleted**: Never (financial record)
```sql
- id (UUID): Primary key
- order_id (UUID): Related order
- amount (DECIMAL): Payment amount
- method (ENUM): cash, upi, card, wallet, net_banking
- status (ENUM): pending, success, failed, refunded
- transaction_id (VARCHAR): Payment gateway transaction ID
- gateway_response (JSONB): Gateway response data
- refund_amount (DECIMAL): Refunded amount if any
- refund_reason (TEXT): Refund explanation
- created_at (TIMESTAMP): Payment initiation
- updated_at (TIMESTAMP): Last status update
```

### **store_settlements**
**Purpose**: Store payment settlements and payouts
**When Created**: Daily/weekly settlement cycles
**When Updated**: Settlement status updates
**When Deleted**: Never
```sql
- id (UUID): Primary key
- store_id (UUID): Store reference
- settlement_date (DATE): Settlement date
- total_orders (INTEGER): Orders in period
- total_amount (DECIMAL): Total sales
- commission_amount (DECIMAL): Platform commission
- settlement_amount (DECIMAL): Amount to pay store
- status (ENUM): pending, processing, completed, failed
- bank_reference (VARCHAR): Bank transaction reference
- created_at (TIMESTAMP): Settlement creation
- updated_at (TIMESTAMP): Status update
```

---

## 6. CUSTOMER MANAGEMENT TABLES

### **customers**
**Purpose**: Customer profiles and preferences
**When Created**: First order or registration
**When Updated**: Profile updates, address changes
**When Deleted**: Account deletion request
```sql
- id (UUID): Primary key
- user_id (UUID): Link to users table
- preferred_stores (UUID[]): Favorite stores
- default_address (TEXT): Primary delivery address
- loyalty_points (INTEGER): Accumulated points
- total_orders (INTEGER): Lifetime orders
- total_spent (DECIMAL): Lifetime spending
- created_at (TIMESTAMP): First interaction
- updated_at (TIMESTAMP): Last update
```

### **customer_addresses**
**Purpose**: Multiple delivery addresses per customer
**When Created**: When customer adds new address
**When Updated**: Address edits
**When Deleted**: When customer removes address
```sql
- id (UUID): Primary key
- customer_id (UUID): Customer reference
- address_type (ENUM): home, work, other
- address_line1 (VARCHAR): Street address
- address_line2 (VARCHAR): Additional address
- city (VARCHAR): City
- state (VARCHAR): State
- pincode (VARCHAR): PIN code
- landmark (VARCHAR): Nearby landmark
- is_default (BOOLEAN): Default address flag
- created_at (TIMESTAMP): Addition time
- updated_at (TIMESTAMP): Last update
```

---

## 7. ANALYTICS & REPORTING TABLES

### **inventory_snapshots**
**Purpose**: Daily inventory value tracking
**When Created**: Automated daily job at midnight
**When Updated**: Never (historical record)
**When Deleted**: After retention period (e.g., 2 years)
```sql
- id (UUID): Primary key
- store_id (UUID): Store reference
- snapshot_date (DATE): Snapshot date
- total_products (INTEGER): Product count
- total_stock_value (DECIMAL): Inventory value
- low_stock_items (INTEGER): Low stock count
- out_of_stock_items (INTEGER): Out of stock count
- snapshot_data (JSONB): Detailed breakdown
- created_at (TIMESTAMP): Creation time
```

### **product_metrics**
**Purpose**: Product performance analytics
**When Created**: Daily aggregation job
**When Updated**: Never (historical data)
**When Deleted**: After retention period
```sql
- id (UUID): Primary key
- store_product_id (UUID): Product reference
- period (DATE): Metric date
- units_sold (DECIMAL): Quantity sold
- revenue (DECIMAL): Total revenue
- profit_margin (DECIMAL): Profit percentage
- stock_turnover_ratio (DECIMAL): Inventory turnover
- days_inventory_outstanding (INTEGER): Stock holding days
- created_at (TIMESTAMP): Calculation time
```

---

## 8. MARKETING & PROMOTIONS TABLES

### **product_offers**
**Purpose**: Store promotions and discounts
**When Created**: Store creates new offer
**When Updated**: Offer modifications
**When Deleted**: Offer expiry or manual removal
```sql
- id (UUID): Primary key
- store_id (UUID): Store reference
- store_product_id (UUID): Product (null for store-wide)
- offer_type (ENUM): percentage, flat, bogo, bundle
- offer_value (DECIMAL): Discount value
- min_quantity (INTEGER): Minimum purchase quantity
- max_discount (DECIMAL): Maximum discount cap
- valid_from (TIMESTAMP): Start date
- valid_until (TIMESTAMP): End date
- terms_conditions (TEXT): Offer terms
- is_active (BOOLEAN): Active status
- created_at (TIMESTAMP): Creation time
```

### **notifications**
**Purpose**: Customer notifications and alerts
**When Created**: System events, marketing campaigns
**When Updated**: Read status changes
**When Deleted**: After retention period
```sql
- id (UUID): Primary key
- user_id (UUID): Recipient user
- type (ENUM): order_update, promotion, system, reminder
- title (VARCHAR): Notification title
- message (TEXT): Notification content
- data (JSONB): Additional data
- is_read (BOOLEAN): Read status
- sent_via (ENUM): push, sms, email, in_app
- created_at (TIMESTAMP): Send time
- read_at (TIMESTAMP): Read timestamp
```

---

## 9. SYSTEM & CONFIGURATION TABLES

### **app_settings**
**Purpose**: Application configuration and feature flags
**When Created**: System initialization
**When Updated**: Admin configuration changes
**When Deleted**: Never
```sql
- id (UUID): Primary key
- key (VARCHAR): Setting key
- value (JSONB): Setting value
- category (VARCHAR): Setting category
- description (TEXT): Setting description
- updated_by (UUID): Last updater
- created_at (TIMESTAMP): Creation time
- updated_at (TIMESTAMP): Last update
```

### **audit_logs**
**Purpose**: System-wide audit trail
**When Created**: Critical operations (login, payments, etc.)
**When Updated**: Never (immutable)
**When Deleted**: After legal retention period
```sql
- id (UUID): Primary key
- user_id (UUID): Acting user
- action (VARCHAR): Action performed
- entity_type (VARCHAR): Affected entity type
- entity_id (VARCHAR): Affected entity ID
- old_values (JSONB): Previous state
- new_values (JSONB): New state
- ip_address (VARCHAR): User IP
- user_agent (TEXT): Browser/app info
- created_at (TIMESTAMP): Action timestamp
```

---

## 10. COMMUNICATION TABLES

### **messages**
**Purpose**: Store-customer communication
**When Created**: Message sent via chat/WhatsApp
**When Updated**: Read status, delivery status
**When Deleted**: After retention period
```sql
- id (UUID): Primary key
- conversation_id (UUID): Conversation thread
- sender_id (UUID): Sender user
- receiver_id (UUID): Receiver user
- message_type (ENUM): text, image, order_update
- content (TEXT): Message content
- media_url (VARCHAR): Attached media
- is_read (BOOLEAN): Read status
- created_at (TIMESTAMP): Send time
- read_at (TIMESTAMP): Read time
```

### **reviews**
**Purpose**: Customer reviews and ratings
**When Created**: After order delivery
**When Updated**: Review edits (within time limit)
**When Deleted**: Violation of guidelines
```sql
- id (UUID): Primary key
- order_id (UUID): Related order
- store_id (UUID): Reviewed store
- customer_id (UUID): Reviewer
- rating (INTEGER): Star rating (1-5)
- review_text (TEXT): Review content
- is_verified_purchase (BOOLEAN): Purchase verification
- helpful_count (INTEGER): Helpful votes
- created_at (TIMESTAMP): Review time
- updated_at (TIMESTAMP): Edit time
```

---

## Database Relationships Summary

1. **User → Store**: Many-to-many through store_users
2. **Store → Products**: One-to-many (store_products)
3. **Generic Product → Store Products**: One-to-many
4. **Order → Order Items**: One-to-many
5. **Store → Orders**: One-to-many
6. **Customer → Orders**: One-to-many
7. **Product → Stock Movements**: One-to-many
8. **Store → Suppliers**: One-to-many

---

## Data Retention Policies

- **Financial Records**: 7 years (legal requirement)
- **Order History**: 3 years
- **Audit Logs**: 2 years
- **Analytics Data**: 1 year detailed, 3 years aggregated
- **Messages**: 6 months
- **OTP Records**: 24 hours
- **Session Data**: 30 days

---

## Performance Indexes

Key indexes for optimal performance:
- stores(store_id, status)
- store_products(store_id, status, sku)
- orders(store_id, created_at, status)
- stock_movements(store_product_id, created_at)
- generic_products(searchable_keywords) - GIN index
- users(email, phone)

---

## Security Considerations

1. **PII Encryption**: Customer phone, email encrypted at rest
2. **Password Security**: bcrypt hashing with salt
3. **Row-Level Security**: Store data isolation by store_id
4. **Audit Trail**: All critical operations logged
5. **Soft Deletes**: Most deletions are soft (mark inactive)
6. **Data Masking**: Sensitive data masked in logs

---

This documentation represents the complete database schema for VyaparAI as of the current implementation.