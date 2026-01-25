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
- latitude (DECIMAL): GPS latitude (auto-geocoded at registration)
- longitude (DECIMAL): GPS longitude (auto-geocoded at registration)
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

**Geocoding Note**: latitude/longitude are auto-geocoded from address using Google Maps Geocoding API during store registration. These coordinates enable:
- Distance-based store search (Haversine formula)
- Cached coordinate lookup for pincode/landmark searches (avoids repeated API calls)
- GPS-based "stores near me" functionality

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

### **orders** (DynamoDB: vyaparai-orders-prod)
**Purpose**: Customer orders placed with stores
**When Created**: When customer places an order (via Saga pattern with stock reservation)
**When Updated**: Status changes, payment confirmation, delivery updates
**When Deleted**: Never (may be cancelled but not deleted)

**DynamoDB Structure**:
```
Primary Key:
  Partition Key: store_id (String)
  Sort Key: id (String) - order_id

GSIs:
  - customer_id-index: For fetching customer order history
  - status-index: For filtering orders by status
```

**Attributes**:
```sql
- id (String): Order ID (format: ord_{timestamp})
- order_number (String): Human-readable order ID (format: ORD-{timestamp})
- tracking_id (String): Tracking ID (format: TRK-{uuid12})
- store_id (String): Store receiving order
- customer_id (String): Customer placing order
- customer_name (String): Customer name
- customer_phone (String): Contact number
- delivery_address (JSON String): Serialized delivery address from customer profile
- status (String): placed, confirmed, preparing, ready, out_for_delivery, delivered, cancelled
- total_amount (Decimal): Order total including delivery
- payment_method (String): cod, upi, card, wallet
- payment_status (String): pending, paid, failed, refunded
- payment_id (String): Payment gateway transaction ID (for online payments)
- items (List): Order items with quantities and prices
  - product_id (String)
  - product_name (String)
  - quantity (Number)
  - unit_price (Decimal)
  - item_total (Decimal)
  - mrp (Decimal)
- delivery_notes (String): Delivery instructions
- customer_note (String): Order notes
- cancel_reason (String): Cancellation reason (if cancelled)
- channel (String): Order channel (web, app, whatsapp)
- language (String): Customer preferred language
- created_at (String): ISO timestamp
- updated_at (String): ISO timestamp
- estimated_delivery (String): Estimated delivery time
```

**Order Creation - Saga Pattern**:
```
Order creation uses transactional safety via the Saga pattern:

1. STOCK RESERVATION (Atomic)
   - Use DynamoDB TransactWriteItems to deduct stock for ALL items
   - Conditional expressions ensure stock >= requested quantity
   - If ANY item fails: entire transaction rolls back (no partial deduction)

2. ORDER CREATION
   - Create order record in vyaparai-orders-prod
   - Include all item details, customer info, addresses

3. COMPENSATING TRANSACTION (on failure)
   - If order creation fails after stock reservation
   - Automatically restore stock (add back quantities)
   - Log critical error for monitoring

This prevents:
- Overselling due to race conditions
- Orphaned orders without inventory deduction
- Lost inventory (reduced but order not created)
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
- latitude (DECIMAL): GPS latitude (auto-geocoded when address saved)
- longitude (DECIMAL): GPS longitude (auto-geocoded when address saved)
- is_default (BOOLEAN): Default address flag
- created_at (TIMESTAMP): Addition time
- updated_at (TIMESTAMP): Last update
```

**Geocoding Note**: latitude/longitude are auto-geocoded from address using Google Maps Geocoding API when a customer saves an address. These coordinates enable:
- Finding nearby stores from customer's saved address
- Accurate delivery distance calculations
- Pre-computed coordinates avoid API calls during store searches

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

## 11. RBAC & PERMISSIONS TABLES (DynamoDB)

### **vyaparai-permissions-prod**
**Purpose**: Stores individual permission definitions for the RBAC system
**When Created**: System initialization with seeded permissions
**When Updated**: When new features require new permissions
**When Deleted**: Never (may be marked as deprecated)

**DynamoDB Structure**:
```
Primary Key: permission_id (String)
GSI - CategoryIndex:
  - PK: category
  - SK: status
```

**Attributes**:
```
- permission_id (String): Unique identifier (e.g., "PERM_PRODUCT_CREATE")
- name (String): Human-readable name (e.g., "Create Products")
- description (String): Detailed description of permission
- category (String): Permission category (product_management | user_management | role_management | analytics | settings)
- resource (String): Target resource (e.g., "products", "users", "roles")
- action (String): Action type (create | read | update | delete | export | import | configure)
- status (String): active | deprecated
- created_at (String): ISO timestamp
- updated_at (String): ISO timestamp
```

**Seeded Permissions (22 total)**:
- Product Management: CREATE, READ, UPDATE, DELETE, EXPORT, IMPORT_BULK
- User Management: CREATE, READ, UPDATE, DELETE, ASSIGN_ROLES, ASSIGN_PERMISSIONS
- Role Management: CREATE, READ, UPDATE, DELETE
- Analytics: VIEW, REPORTS_GENERATE, REPORTS_EXPORT
- Settings: VIEW, UPDATE, SYSTEM_CONFIG

### **vyaparai-roles-prod**
**Purpose**: Stores role definitions with associated permissions
**When Created**: System initialization with default roles
**When Updated**: When role permissions are modified
**When Deleted**: Never for system roles; custom roles can be deleted

**DynamoDB Structure**:
```
Primary Key: role_id (String)
GSI - HierarchyIndex:
  - PK: status
  - SK: hierarchy_level
```

**Attributes**:
```
- role_id (String): Unique identifier (e.g., "ROLE_SUPER_ADMIN")
- role_name (String): Human-readable name
- description (String): Role description
- permissions (StringSet): List of permission IDs or ["*"] for all
- hierarchy_level (Number): 1-100 (lower = higher privilege)
- is_system_role (Boolean): System roles cannot be deleted
- status (String): active | inactive
- created_at (String): ISO timestamp
- updated_at (String): ISO timestamp
```

**Seeded Roles (5 total)**:
1. ROLE_SUPER_ADMIN (Level 1) - All permissions
2. ROLE_ADMIN (Level 10) - Product, user, analytics, settings
3. ROLE_STORE_MANAGER (Level 20) - Product read/update, analytics
4. ROLE_CATALOG_EDITOR (Level 30) - Product CRUD + export
5. ROLE_VIEWER (Level 50) - Read-only access

### **vyaparai-user-permissions-prod**
**Purpose**: Junction table tracking user-permission assignments with audit trail
**When Created**: When permissions are assigned to users
**When Updated**: Never (create new record for changes)
**When Deleted**: When permission is revoked

**DynamoDB Structure**:
```
Primary Key: assignment_id (String) - Format: {user_id}#{permission_id}
GSI1 - UserPermissionsIndex:
  - PK: user_id
  - SK: assignment_type
GSI2 - PermissionUsersIndex:
  - PK: permission_id
```

**Attributes**:
```
- assignment_id (String): Composite key
- user_id (String): User identifier
- permission_id (String): Permission identifier
- granted_by (String): User ID who granted permission
- assignment_type (String): direct | role_inherited | override
- expires_at (String): Optional expiration timestamp
- assigned_at (String): ISO timestamp
```

---

## 12. BULK IMPORT SYSTEM TABLES (DynamoDB)

### **vyaparai-import-jobs-prod**
**Purpose**: Manages async CSV import job lifecycle and status tracking
**When Created**: When admin uploads CSV for bulk product import
**When Updated**: Throughout job processing (status, progress updates)
**When Deleted**: Auto-cleanup after 30 days via TTL

**DynamoDB Structure**:
```
Primary Key: job_id (String)
GSI - created_by_user_id_gsi-index: For listing user's jobs
GSI - status_gsi-index: For monitoring jobs by status
GSI - job_type_gsi: For filtering by import type
TTL Attribute: ttl (auto-delete after 30 days)
```

**Attributes**:
```
- job_id (String): Unique identifier (e.g., "admin_import_20250106_abc123")
- job_type (String): admin_product_import | store_inventory_upload
- store_id (String): Store ID for inventory uploads (null for admin imports)
- created_by_user_id (String): User who created the job
- created_by_email (String): Email of job creator
- status (String): queued | processing | completed | completed_with_errors | failed | cancelled
- status_history (List): Array of status transitions with timestamps
- created_at (String): Job creation timestamp
- started_at (String): Processing start timestamp
- completed_at (String): Job completion timestamp
- estimated_completion_at (String): Estimated finish time
- total_rows (Number): Total CSV rows
- processed_rows (Number): Rows processed so far
- successful_count (Number): Successfully imported products
- duplicate_count (Number): Skipped duplicates
- error_count (Number): Rows with errors
- skipped_count (Number): Skipped rows
- s3_bucket (String): S3 bucket containing CSV
- s3_input_key (String): S3 key for input CSV
- s3_error_report_key (String): S3 key for error report CSV
- input_filename (String): Original filename
- input_file_size_bytes (Number): File size
- input_row_count_estimate (Number): Estimated row count
- import_options (Map): Configuration options
  - skip_duplicates (Boolean)
  - auto_verify (Boolean)
  - default_verification_status (String)
  - process_images (Boolean)
  - default_region (String)
  - match_strategy (String): strict | fuzzy
  - notification_email (String)
- recent_errors (List): Last 10 error records
- processing_lambda_arn (String): Lambda function processing job
- processing_start_memory_mb (Number): Lambda memory allocated
- processing_duration_seconds (Number): Total processing time
- checkpoint (Map): Resume point for long-running jobs
  - last_processed_row (Number)
- ttl (Number): Unix timestamp for auto-deletion
```

**Job Lifecycle**:
1. QUEUED - Job created, waiting for processing
2. PROCESSING - Lambda function actively processing CSV
3. COMPLETED - All rows processed successfully
4. COMPLETED_WITH_ERRORS - Finished but some rows had errors
5. FAILED - Critical error occurred, job aborted
6. CANCELLED - User cancelled the job

**Checkpoint/Resume System**:
- For large CSV files (>5000 rows), processing may exceed Lambda timeout
- Checkpoint saves progress (last_processed_row) to DynamoDB
- Lambda re-invokes itself with checkpoint to resume processing
- Ensures no data loss for large imports

---

## 13. TRANSLATION & CACHING TABLES (DynamoDB)

### **vyaparai-translation-cache-prod**
**Purpose**: Caches translated text to reduce Google Translate API costs
**When Created**: After first translation of a text string
**When Updated**: Never (cache is immutable)
**When Deleted**: Auto-cleanup after 30 days via TTL

**DynamoDB Structure**:
```
Primary Key: cacheKey (String) - Format: {sourceText}__{sourceLanguage}__{targetLanguage}
TTL Attribute: ttl (auto-delete after 30 days)
```

**Attributes**:
```
- cacheKey (String): Composite key (e.g., "tata salt__en__hi")
- sourceText (String): Original text in source language
- translatedText (String): Translated text
- sourceLanguage (String): Source language code (default: "en")
- targetLanguage (String): Target language code (e.g., "hi", "ta", "mr")
- timestamp (String): Cache creation timestamp
- ttl (Number): Unix timestamp for expiration
```

**Cache Strategy**:
- Before calling Google Translate API, check cache for existing translation
- Cache hit: Return cached translation (no API cost)
- Cache miss: Call API, store result, return translation
- TTL: 30 days ensures fresh translations while minimizing API costs
- Key normalization: Convert to lowercase, trim whitespace for consistency

**Supported Languages**:
- en (English), hi (Hindi), mr (Marathi), ta (Tamil), te (Telugu), bn (Bengali)
- And additional languages as configured

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
9. **User → Roles**: Many-to-many through user-permissions (RBAC)
10. **Role → Permissions**: Many-to-many (stored as StringSet in roles)
11. **User → Permissions**: Many-to-many through user-permissions (direct assignment)

---

## Data Retention Policies

- **Financial Records**: 7 years (legal requirement)
- **Order History**: 3 years
- **Audit Logs**: 2 years
- **Analytics Data**: 1 year detailed, 3 years aggregated
- **Messages**: 6 months
- **OTP Records**: 24 hours
- **Session Data**: 30 days
- **Import Jobs**: 30 days (auto-cleanup via TTL)
- **Translation Cache**: 30 days (auto-cleanup via TTL)

---

## Performance Indexes

Key indexes for optimal performance:
- stores(store_id, status)
- stores(latitude, longitude) - For geo-spatial queries
- stores(pincode) - For pincode-based coordinate caching
- store_products(store_id, status, sku)
- orders(store_id, created_at, status)
- stock_movements(store_product_id, created_at)
- generic_products(searchable_keywords) - GIN index
- users(email, phone)
- customer_addresses(customer_id, latitude, longitude)

**DynamoDB GSIs**:
- permissions: CategoryIndex (category + status)
- roles: HierarchyIndex (status + hierarchy_level)
- user-permissions: UserPermissionsIndex (user_id + assignment_type), PermissionUsersIndex (permission_id)
- import-jobs: created_by_user_id_gsi, status_gsi, job_type_gsi

---

## Security Considerations

1. **PII Encryption**: Customer phone, email encrypted at rest
2. **Password Security**: bcrypt hashing with salt
3. **Row-Level Security**: Store data isolation by store_id
4. **Audit Trail**: All critical operations logged
5. **Soft Deletes**: Most deletions are soft (mark inactive)
6. **Data Masking**: Sensitive data masked in logs
7. **RBAC Enforcement**: Permission checks at API layer
8. **TTL Auto-Cleanup**: Automatic removal of temporary data
9. **Hierarchy Protection**: Role hierarchy prevents privilege escalation

---

## Database Technology Stack

**PostgreSQL (RDS)**: Used for relational data (users, stores, products, orders, inventory)
**DynamoDB**: Used for high-throughput, flexible schema data (RBAC, import jobs, translation cache)
**Hybrid Strategy**: Combines strengths of both databases for optimal performance

**PostgreSQL Tables**: ~40+ tables for core business logic
**DynamoDB Tables**: 5 tables for scalable, high-throughput operations
  - vyaparai-users-prod
  - vyaparai-permissions-prod
  - vyaparai-roles-prod
  - vyaparai-user-permissions-prod
  - vyaparai-import-jobs-prod
  - vyaparai-translation-cache-prod
  - vyaparai-stores-prod (and others)

---

**Last Updated**: December 12, 2025
**Document Version**: 2.2.0
**Status**: Comprehensive - All tables documented including RBAC, import-jobs, translation-cache, geocoding fields, and order transaction patterns

This documentation now represents the **complete** database schema for VyaparAI including:
- All 5 RBAC/System tables (permissions, roles, user-permissions, import-jobs, translation-cache)
- Geocoding fields (latitude/longitude) on stores and customer_addresses for location-based search
- Order transaction patterns with Saga pattern for stock reservation